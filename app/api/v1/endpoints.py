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
async def apply_corrections(
    project_id: str,
    request: "CorrectionBatchRequest",
    auth_data: dict = Depends(get_current_user_and_db),
):
    """
    배치 보정 API — 여러 연산을 하나의 세션으로 적용.
    보정 후 자동으로 IFC 재생성 및 이력 저장.
    """
    from app.schemas.correction import CorrectionBatchRequest, CorrectionSessionResponse, CorrectionPatchResponse

    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    geom_path = str(OUTPUT_ROOT / "projects" / project_id / "page0_rooms.json")
    if not os.path.exists(geom_path):
        raise HTTPException(status_code=404, detail="Geometry data not available")

    with open(geom_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    import uuid
    from correction.patch import CorrectionSession
    from correction.operations import (
        change_room_type, move_wall, add_wall, delete_wall,
        merge_rooms, split_room, move_opening,
        place_leak_source, paint_damage_zone, delete_room,
    )
    from correction.rebuild import rebuild_after_correction
    from domain.models import RoomKind

    session = CorrectionSession(
        session_id=str(uuid.uuid4())[:8],
        case_id=request.case_id,
    )

    # 연산 디스패치
    op_dispatch = {
        "change_room_type": lambda p, params, author: change_room_type(
            p, room_id=params["room_id"],
            new_kind=RoomKind(params["new_kind"]), author=author,
        ),
        "move_wall": lambda p, params, author: move_wall(
            p, wall_id=params["wall_id"],
            new_p1=params["new_p1"], new_p2=params["new_p2"], author=author,
        ),
        "add_wall": lambda p, params, author: add_wall(
            p, p1=params["p1"], p2=params["p2"], author=author,
        ),
        "delete_wall": lambda p, params, author: delete_wall(
            p, wall_id=params["wall_id"], author=author,
        ),
        "merge_rooms": lambda p, params, author: merge_rooms(
            p, room_id_a=params["room_id_a"], room_id_b=params["room_id_b"],
            merged_kind=params.get("merged_kind"), author=author,
        ),
        "split_room": lambda p, params, author: split_room(
            p, room_id=params["room_id"],
            split_axis=params.get("split_axis", "vertical"),
            split_ratio=params.get("split_ratio", 0.5), author=author,
        ),
        "move_opening": lambda p, params, author: move_opening(
            p, room_id=params["room_id"], opening_idx=params["opening_idx"],
            new_p1=params["new_p1"], new_p2=params["new_p2"], author=author,
        ),
        "place_leak_source": lambda p, params, author: place_leak_source(
            p, point=params["point"], room_id=params.get("room_id"),
            description=params.get("description", ""), author=author,
        ),
        "paint_damage_zone": lambda p, params, author: paint_damage_zone(
            p, damage_type=params["damage_type"], severity=params["severity"],
            polygon=params["polygon"], room_id=params.get("room_id"),
            description=params.get("description", ""), author=author,
        ),
        "delete_room": lambda p, params, author: delete_room(
            p, room_id=params["room_id"], author=author,
        ),
    }

    for op in request.operations:
        handler = op_dispatch.get(op.operation)
        if not handler:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {op.operation}")
        patch = handler(payload, op.params, op.author)
        if patch:
            session.patches.append(patch)

    # 재빌드
    project_dir = str(OUTPUT_ROOT / "projects" / project_id)
    payload = rebuild_after_correction(payload, session, output_dir=project_dir)

    # DB 상태 업데이트
    ifc_path = payload.get("_rebuilt_ifc", "")
    if ifc_path:
        db.table("projects").update({
            "status": "completed",
            "ifc_url": ifc_path,
        }).eq("id", project_id).execute()

    return {
        "status": "success",
        "session_id": session.session_id,
        "patches_applied": session.patch_count,
        "correction_source": session.correction_source,
        "operation_summary": session.operation_summary,
    }


@router.get("/projects/{project_id}/correction/history")
async def get_correction_history(
    project_id: str,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """프로젝트의 보정 이력 조회"""
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    from correction.history import list_sessions, get_correction_stats

    project_dir = str(OUTPUT_ROOT / "projects" / project_id)
    sessions = list_sessions(project_dir)
    stats = get_correction_stats(project_dir)

    return {
        "sessions": sessions,
        "stats": stats,
    }

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


# ================================================================
# Incident Semantics API (Phase 5)
# ================================================================

from app.schemas.incident import (
    IncidentCreateRequest,
    IncidentResponse,
    AnnotationCreateRequest,
    AnnotationResponse,
)


def _incident_json_path(project_id: str) -> str:
    return str(OUTPUT_ROOT / "projects" / project_id / "incident.json")


@router.post("/projects/{project_id}/incident", response_model=IncidentResponse)
async def create_incident(
    project_id: str,
    request: IncidentCreateRequest,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """프로젝트에 인시던트 데이터를 생성/저장"""
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    from domain.models import (
        LeakCase, LeakSource, DamageZone, SuspectedPath,
        IncidentAnnotation, Point, DamageType, Severity,
    )
    from scene.serializer import save_leak_case, leak_case_to_dict

    # Pydantic → domain model 변환
    case = LeakCase(
        case_id=request.case_id,
        customer_name=request.customer_name,
        address=request.address,
        incident_date=request.incident_date,
        description=request.description,
        leak_sources=[
            LeakSource(
                point=Point(x=s.point.x, y=s.point.y),
                room_id=s.room_id,
                confidence=s.confidence,
                description=s.description,
            )
            for s in request.leak_sources
        ],
        damage_zones=[
            DamageZone(
                id=dz.id,
                damage_type=DamageType(dz.damage_type),
                severity=Severity(dz.severity),
                polygon=[Point(x=p.x, y=p.y) for p in dz.polygon],
                room_id=dz.room_id,
                floor_level=dz.floor_level,
                surface_area_m2=dz.surface_area_m2,
                description=dz.description,
                photos=dz.photos,
            )
            for dz in request.damage_zones
        ],
        suspected_paths=[
            SuspectedPath(
                waypoints=[Point(x=p.x, y=p.y) for p in sp.waypoints],
                room_ids=sp.room_ids,
                description=sp.description,
            )
            for sp in request.suspected_paths
        ],
        annotations=[
            IncidentAnnotation(
                id=i + 1,
                anchor_point=Point(x=a.anchor_point.x, y=a.anchor_point.y),
                anchor_room_id=a.anchor_room_id,
                text=a.text,
                category=a.category,
                attached_photo=a.attached_photo,
            )
            for i, a in enumerate(request.annotations)
        ],
    )

    path = _incident_json_path(project_id)
    save_leak_case(case, path)

    case_dict = leak_case_to_dict(case)
    return IncidentResponse(
        case_id=case.case_id,
        version=case.version,
        created_at=case.created_at,
        updated_at=case.updated_at,
        customer_name=case.customer_name,
        leak_sources_count=len(case.leak_sources),
        damage_zones_count=len(case.damage_zones),
        annotations_count=len(case.annotations),
        data=case_dict,
    )


@router.get("/projects/{project_id}/incident", response_model=IncidentResponse)
async def get_incident(
    project_id: str,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """프로젝트의 인시던트 데이터 조회"""
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    path = _incident_json_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No incident data for this project")

    from scene.serializer import load_leak_case, leak_case_to_dict

    case = load_leak_case(path)
    case_dict = leak_case_to_dict(case)

    return IncidentResponse(
        case_id=case.case_id,
        version=case.version,
        created_at=case.created_at,
        updated_at=case.updated_at,
        customer_name=case.customer_name,
        leak_sources_count=len(case.leak_sources),
        damage_zones_count=len(case.damage_zones),
        annotations_count=len(case.annotations),
        data=case_dict,
    )


@router.put("/projects/{project_id}/incident", response_model=IncidentResponse)
async def update_incident(
    project_id: str,
    request: IncidentCreateRequest,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """프로젝트의 인시던트 데이터 갱신 (버전 자동 증가)"""
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    path = _incident_json_path(project_id)

    from domain.models import (
        LeakCase, LeakSource, DamageZone, SuspectedPath,
        IncidentAnnotation, Point, DamageType, Severity,
    )
    from scene.serializer import save_leak_case, load_leak_case, leak_case_to_dict

    # 기존 버전 로드 (있으면)
    old_version = 0
    old_created = ""
    if os.path.exists(path):
        old_case = load_leak_case(path)
        old_version = old_case.version
        old_created = old_case.created_at

    case = LeakCase(
        case_id=request.case_id,
        customer_name=request.customer_name,
        address=request.address,
        incident_date=request.incident_date,
        description=request.description,
        version=old_version,
        created_at=old_created,
        leak_sources=[
            LeakSource(
                point=Point(x=s.point.x, y=s.point.y),
                room_id=s.room_id,
                confidence=s.confidence,
                description=s.description,
            )
            for s in request.leak_sources
        ],
        damage_zones=[
            DamageZone(
                id=dz.id,
                damage_type=DamageType(dz.damage_type),
                severity=Severity(dz.severity),
                polygon=[Point(x=p.x, y=p.y) for p in dz.polygon],
                room_id=dz.room_id,
                floor_level=dz.floor_level,
                surface_area_m2=dz.surface_area_m2,
                description=dz.description,
                photos=dz.photos,
            )
            for dz in request.damage_zones
        ],
        suspected_paths=[
            SuspectedPath(
                waypoints=[Point(x=p.x, y=p.y) for p in sp.waypoints],
                room_ids=sp.room_ids,
                description=sp.description,
            )
            for sp in request.suspected_paths
        ],
        annotations=[
            IncidentAnnotation(
                id=i + 1,
                anchor_point=Point(x=a.anchor_point.x, y=a.anchor_point.y),
                anchor_room_id=a.anchor_room_id,
                text=a.text,
                category=a.category,
                attached_photo=a.attached_photo,
            )
            for i, a in enumerate(request.annotations)
        ],
    )
    case.bump_version()

    save_leak_case(case, path)
    case_dict = leak_case_to_dict(case)

    return IncidentResponse(
        case_id=case.case_id,
        version=case.version,
        created_at=case.created_at,
        updated_at=case.updated_at,
        customer_name=case.customer_name,
        leak_sources_count=len(case.leak_sources),
        damage_zones_count=len(case.damage_zones),
        annotations_count=len(case.annotations),
        data=case_dict,
    )


@router.post("/projects/{project_id}/incident/annotations", response_model=AnnotationResponse)
async def add_annotation(
    project_id: str,
    request: AnnotationCreateRequest,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """인시던트에 어노테이션(사진/메모) 추가"""
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    path = _incident_json_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No incident data. Create incident first.")

    from scene.serializer import load_leak_case, save_leak_case
    from scene.annotations import attach_photo, attach_note
    from domain.models import Point

    case = load_leak_case(path)
    anchor = Point(x=request.anchor_point.x, y=request.anchor_point.y)

    if request.attached_photo:
        ann = attach_photo(
            case, request.attached_photo, anchor,
            room_id=request.anchor_room_id, text=request.text,
        )
    else:
        ann = attach_note(
            case, request.text, anchor,
            room_id=request.anchor_room_id, category=request.category,
        )

    save_leak_case(case, path)

    return AnnotationResponse(
        id=ann.id,
        anchor_point={"x": ann.anchor_point.x, "y": ann.anchor_point.y},
        anchor_room_id=ann.anchor_room_id,
        text=ann.text,
        category=ann.category,
        attached_photo=ann.attached_photo,
        created_at=ann.created_at,
    )


@router.delete("/projects/{project_id}/incident/annotations/{annotation_id}")
async def delete_annotation(
    project_id: str,
    annotation_id: int,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """인시던트에서 어노테이션 삭제"""
    db = auth_data["db"]
    res = db.table("projects").select("id").eq("id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    path = _incident_json_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No incident data")

    from scene.serializer import load_leak_case, save_leak_case
    from scene.annotations import remove_annotation

    case = load_leak_case(path)
    removed = remove_annotation(case, annotation_id)

    if not removed:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} not found")

    save_leak_case(case, path)
    return {"status": "success", "message": f"Annotation {annotation_id} deleted", "version": case.version}

