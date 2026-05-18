import uuid
import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app.schemas.tasks import TaskResponse, TaskStatus
from app.worker.tasks import process_pdf_task
from celery.result import AsyncResult
from fastapi import Depends
from app.api.deps import get_current_user_and_db

router = APIRouter()

UPLOAD_DIR = "uploads"

@router.post("/convert", response_model=TaskResponse)
async def convert_pdf(
    file: UploadFile = File(...),
    auth_data: dict = Depends(get_current_user_and_db)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    user_id = auth_data["user_id"]
    db = auth_data["db"]
    
    file_extension = os.path.splitext(file.filename)[1]
    
    # Insert record into Supabase projects table
    response = db.table("projects").insert({
        "user_id": user_id,
        "original_filename": file.filename,
        "status": "pending"
    }).execute()
    
    if not response.data:
         raise HTTPException(status_code=500, detail="Failed to create project record in DB")
         
    project_id = response.data[0]["id"]
    saved_file_name = f"{project_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, saved_file_name)
    
    # 1. 파일 저장
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Update DB status to processing
    db.table("projects").update({"status": "processing"}).eq("id", project_id).execute()
    
    # 2. Celery Task 호출
    task = process_pdf_task.delay(file_path, project_id)
    
    return TaskResponse(
        task_id=task.id,
        status="accepted",
        message=f"File uploaded. Processing started with Task ID: {task.id}"
    )

@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    res = AsyncResult(task_id)
    
    status = res.status
    progress = 0.0
    result = None
    error = None
    
    if status == "PROGRESS":
        progress = res.info.get("progress", 0.0)
    elif status == "SUCCESS":
        progress = 100.0
        result = res.result
    elif status == "FAILURE":
        error = str(res.result)
        
    return TaskStatus(
        task_id=task_id,
        status=status,
        progress=progress,
        result=result,
        error=error
    )

from pipeline.paths import OUTPUT_ROOT
import json

@router.get("/projects/{project_id}/geometry")
async def get_project_geometry(project_id: str, auth_data: dict = Depends(get_current_user_and_db)):
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    geom_path = OUTPUT_ROOT / "projects" / project_id / "page0_rooms.json"
    if not geom_path.exists():
        raise HTTPException(status_code=404, detail="Geometry data not available yet")
        
    with open(geom_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    return data

@router.post("/projects/{project_id}/correction")
async def save_correction(project_id: str, request_data: dict, auth_data: dict = Depends(get_current_user_and_db)):
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    geom_path = str(OUTPUT_ROOT / "projects" / project_id / "page0_rooms.json")
    
    # Save the new payload
    with open(geom_path, "w", encoding="utf-8") as f:
        json.dump(request_data, f, indent=2)

    # Trigger IFC rebuild
    from parser.export_ifc import build_ifc_from_meta
    ifc_path = str(OUTPUT_ROOT / "projects" / project_id / "page0_result.ifc")
    build_ifc_from_meta(request_data, out_ifc=ifc_path, out_meta=ifc_path + ".meta.json")
    
    # Update DB with new ifc path (if needed)
    db.table("projects").update({
        "status": "completed",
        "ifc_url": ifc_path
    }).eq("id", project_id).execute()

    return {"status": "success", "message": "Correction applied and IFC rebuilt"}

@router.get("/projects/{project_id}/compliance-report")
async def get_compliance_report(project_id: str, auth_data: dict = Depends(get_current_user_and_db)):
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    comp_path = OUTPUT_ROOT / "projects" / project_id / "page0_compliance.json"
    if not comp_path.exists():
        raise HTTPException(status_code=404, detail="Compliance data not available yet")
        
    with open(comp_path, "r", encoding="utf-8") as f:
        compliance_data = json.load(f)
        
    from compliance.evaluator import evaluate_project
    from compliance.gemini_adapter import llm_adapter
    
    # 1. Deterministic Evaluation
    report = evaluate_project(compliance_data)
    
    # 2. SLM Mock Inference
    slm_reasoning = llm_adapter.generate_compliance_reasoning(
        slm_prompt_context=report["slm_prompt_context"],
        geometry_data=compliance_data
    )
    
    report["slm_assessment"] = slm_reasoning
    
    return report

@router.get("/projects/{project_id}/download-ifc")
async def download_ifc(project_id: str, auth_data: dict = Depends(get_current_user_and_db)):
    db = auth_data["db"]
    res = db.table("projects").select("id, ifc_url").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    project = res.data[0]
    ifc_path = project.get("ifc_url")

    if not ifc_path or not os.path.exists(ifc_path):
        # Fallback to default output path
        ifc_path = str(OUTPUT_ROOT / "projects" / project_id / "page0_result.ifc")
        if not os.path.exists(ifc_path):
            raise HTTPException(status_code=404, detail="IFC file not found on server")

    return FileResponse(
        path=ifc_path,
        media_type="application/octet-stream",
        filename=f"project_{project_id}.ifc"
    )
