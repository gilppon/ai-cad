import uuid
import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
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
