import uuid
import os
import json
import logging
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Request

from pipeline.paths import OUTPUT_ROOT
from fastapi.responses import FileResponse
from app.schemas.tasks import TaskResponse, TaskStatus
from app.schemas.correction import CorrectionBatchRequest, OfflineSyncRequest, OfflineSyncResponse
from app.schemas.incident import (
    IncidentCreateRequest,
    IncidentResponse,
    AnnotationCreateRequest,
    AnnotationResponse,
    IncidentPinUpdateRequest,
)
from app.worker.tasks import process_pdf_task
from celery.result import AsyncResult
from fastapi import Depends
from app.api.deps import get_current_user_and_db, get_supabase_client, require_project

# Stripe 결제 및 다국어(i18n) 통합 모듈 임포트
from app.services.payment import StripePaymentService, CircuitBreakerOpenException
from app.schemas.payment import CheckoutSessionRequest, CheckoutSessionResponse, PaymentWebhookPayload, PaymentStatusResponse
from app.schemas.quotation import QuotationDocument
from app.services.i18n import JPTranslationEngine

router = APIRouter()

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"


def _is_safe_path_segment(segment: str) -> bool:
    """
    URL 경로 세그먼트의 파일시스템 안전성 검증 (SP1/S-5).
    '.', '..', 구분자('/','\\'), 드라이브 접두어(':')는 명시적으로 거부한다.
    Path(...).name 기반 검사만으로는 '..' 정규화 우회가 가능하므로 화이트리스트형 검사를 사용.
    """
    return (
        bool(segment)
        and segment not in (".", "..")
        and "/" not in segment
        and "\\" not in segment
        and ":" not in segment
    )


_LAW_MANIFEST_CACHE = None


def _load_law_manifest() -> dict:
    """
    법령 판본 매니페스트 로더 (SP2/L-4).
    data/laws/manifest.json이 고정한 판본 정보를 체크시트·견적서에 명시하기 위해 사용한다.
    """
    global _LAW_MANIFEST_CACHE
    if _LAW_MANIFEST_CACHE is None:
        manifest_path = Path(__file__).resolve().parents[3] / "data" / "laws" / "manifest.json"
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                _LAW_MANIFEST_CACHE = json.load(f)
        except Exception as e:
            logger.warning(f"Law manifest not loadable at {manifest_path}: {e}")
            _LAW_MANIFEST_CACHE = {}
    return _LAW_MANIFEST_CACHE


def _legal_basis_note() -> str:
    """체크시트 표기용 근거 법령·판본 문자열 생성 (SP2/L-4)."""
    manifest = _load_law_manifest()
    laws = manifest.get("laws", [])
    if not laws:
        return ""
    parts = [f"{l.get('title_ja', '?')}({l.get('law_num_ja', '?')})" for l in laws]
    retrieved = manifest.get("retrieved_at", "")
    note = "根拠法令: " + "・".join(parts)
    if retrieved:
        note += f" / 法令データ取得日: {retrieved}"
    return note

@router.post("/convert", response_model=TaskResponse)
async def convert_pdf(
    file: UploadFile = File(...),
    auth_data: dict = Depends(get_current_user_and_db)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    user_id = auth_data["user_id"]
    db = auth_data["db"]
    
    # [하네스 프로토콜 - 결제 가드 및 회로 차단기]
    # 주의: 여기서는 **차감하지 않고 자격만 확인**한다. 차감은 프로젝트 등록과
    # 파일 저장이 모두 성공한 뒤에 수행한다 (아래 deduct 참조).
    # 과거: 자격 확인 즉시 차감 → 이후 단계가 실패해도 크레딧이 소멸되었다.
    if not StripePaymentService.check_user_access_gate(user_id, db, amount=3):
        raise HTTPException(
            status_code=402,
            detail="Payment required. Please purchase a plan or single ticket at /payments/checkout-session to access 3D conversion. (3 credits required)"
        )

    file_extension = os.path.splitext(file.filename)[1]

    import logging
    logger = logging.getLogger(__name__)

    # SP6/P0-1: 과거에는 insert 실패 시 DB에 등록되지 않은 임의 ID로 처리를 강행했다.
    # 그 결과 파일은 저장·처리되지만 사용자가 조회할 수 없는 유령 프로젝트가 되었다.
    try:
        response = db.table("projects").insert({
            "user_id": user_id,
            "original_filename": file.filename,
            "status": "pending"
        }).execute()

        if not response.data:
            raise RuntimeError("Insert returned no rows (possibly blocked by RLS)")
        project_id = response.data[0]["id"]
    except Exception as e:
        logger.error(f"[Convert] Failed to register project for user={user_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="프로젝트를 등록할 수 없습니다. 크레딧은 차감되지 않았습니다. 잠시 후 다시 시도해 주십시오."
        )

    saved_file_name = f"{project_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, saved_file_name)

    # 1. 파일 저장 (실패 시 크레딧 미차감 상태로 종료되므로 손실 없음)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. 모든 준비가 끝난 뒤 크레딧 3건 차감
    StripePaymentService.deduct_credit(user_id, db, amount=3)

    # Update DB status to processing (소유자 기준으로 한정 — C1)
    try:
        db.table("projects").update({"status": "processing"}).eq("id", project_id).eq("user_id", user_id).execute()
    except Exception as e:
        logger.warning(f"[Harness Fallback] Failed to update project status in Supabase: {str(e)}")

    # 3. Celery Task 호출
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

@router.get("/projects")
async def list_projects(auth_data: dict = Depends(get_current_user_and_db)):
    """
    로그인한 사용자의 프로젝트 목록 조회 (SP6/P0-2 신설).

    이 엔드포인트가 없어 프론트엔드(reports/dashboard)가 프로젝트를 열거할 수 없었고,
    그 결과 하드코딩된 가짜 프로젝트 2건을 표시하고 있었다 (C2).

    소유권은 .eq("user_id", ...) 와 RLS 양쪽으로 강제된다.
    """
    db = auth_data["db"]
    user_id = auth_data["user_id"]

    try:
        res = (
            db.table("projects")
            .select("id, original_filename, status, ifc_url, error_message, created_at, updated_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as e:
        logger.error(f"[Projects] Failed to list projects for user={user_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="프로젝트 목록을 불러올 수 없습니다. 잠시 후 다시 시도해 주십시오.",
        )

    return {"projects": res.data or []}

from pipeline.paths import OUTPUT_ROOT
import json

@router.get("/projects/{project_id}/geometry")
async def get_project_geometry(project_id: str, auth_data: dict = Depends(get_current_user_and_db)):
    db = auth_data["db"]
    
    # SP6/P0-1: 소유권 검증 (C1).
    # 과거: 이 블록은 try/except 로 감싸져 있었고, 예외 발생 시
    #       "bypassing check" 로그를 남기며 **인증 검사를 건너뛰고** 진행했다.
    #       즉 Supabase 가 잠시 불안정하면 누구나 타인의 도면을 열람할 수 있었다.
    #       또한 DB에 없어도 로컬 파일만 있으면 통과시켰다 (소유권 미검증).
    # 현재: require_project 는 DB 오류를 503 으로 처리한다 (fail-closed).
    require_project(db, project_id, auth_data["user_id"])

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
    user_id = auth_data["user_id"]
    require_project(db, project_id, user_id)

    geom_path = str(OUTPUT_ROOT / "projects" / project_id / "page0_rooms.json")
    if not os.path.exists(geom_path):
        raise HTTPException(status_code=404, detail="Geometry data not available")

    with open(geom_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    import uuid
    from datetime import datetime, timezone
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

    # 일본 건축 규정 및 공용/전유 누수 책임 판정 연동 (Phase 7)
    from compliance.jp_compliance import JPResponsibilityEngine
    compliance_opinions = []
    
    incident = payload.get("incident", {})
    leak_sources = incident.get("leak_sources", [])
    rooms = payload.get("rooms", [])
    
    for ls in leak_sources:
        rid = ls.get("room_id")
        target_room = next((r for r in rooms if r.get("id") == rid), None)
        room_meta = target_room if target_room else {"id": rid, "kind": "UNKNOWN"}
        
        opinion = JPResponsibilityEngine.evaluate_leak(ls.get("point", {}), room_meta)
        compliance_opinions.append(opinion)
        ls["compliance_opinion"] = opinion
        
    incident["compliance_opinions"] = compliance_opinions
    payload["incident"] = incident
    
    # 정합성을 위해 수정된 geom JSON 파일 저장
    with open(geom_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # DB 상태 업데이트 및 메타데이터 필드 보강 (하네스 방화벽 안전장치)
    ifc_path = payload.get("_rebuilt_ifc", "")
    db_update = {
        "status": "completed",
        "metadata": {
            "compliance_opinions": compliance_opinions,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    }
    if ifc_path:
        db_update["ifc_url"] = ifc_path

    # 소유자 기준으로 한정 (C1) — 타인 프로젝트 갱신 차단
    db.table("projects").update(db_update).eq("id", project_id).eq("user_id", user_id).execute()

    return {
        "status": "success",
        "session_id": session.session_id,
        "patches_applied": session.patch_count,
        "correction_source": session.correction_source,
        "operation_summary": session.operation_summary,
        "compliance_opinions": compliance_opinions,
    }


@router.get("/projects/{project_id}/correction/history")
async def get_correction_history(
    project_id: str,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """프로젝트의 보정 이력 조회"""
    db = auth_data["db"]
    require_project(db, project_id, auth_data["user_id"])

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
    require_project(db, project_id, auth_data["user_id"])

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
    # require_project 는 소유권이 확인된 행을 반환한다 (없으면 404).
    project = require_project(db, project_id, auth_data["user_id"], select="id, ifc_url")
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
    require_project(db, project_id, auth_data["user_id"])

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
    require_project(db, project_id, auth_data["user_id"])

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
    require_project(db, project_id, auth_data["user_id"])

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
    require_project(db, project_id, auth_data["user_id"])

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
    require_project(db, project_id, auth_data["user_id"])

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


@router.get("/projects/{project_id}/pdf-report")
async def get_pdf_report(
    project_id: str,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """
    일본 소기업 대상 'A4 1장 표준 누수 진단 보고서' PDF 생성 및 다운로드 API
    """
    db = auth_data["db"]
    user_id = auth_data["user_id"]
    
    # [하네스 프로토콜 - 결제 가드 및 회로 차단기]
    if not StripePaymentService.check_user_access_gate(user_id, db):
        raise HTTPException(
            status_code=402, 
            detail="Payment required. Please purchase a plan or single ticket at /payments/checkout-session to download PDF reports."
        )

    project = require_project(db, project_id, auth_data["user_id"], select="*")
    metadata = project.get("metadata", {}) or {}
    raw_opinions = metadata.get("compliance_opinions", [])
    
    # [다국어 i18n 통합] 방 명칭 및 의견서 내의 영문 방 명칭을 일본 표준 명칭으로 자동 매핑 보완
    compliance_opinions = []
    for op in raw_opinions:
        room_kind = op.get("room_type_jp", "用途不明")
        translated_room = JPTranslationEngine.translate_room(room_kind)
        
        op_copy = dict(op)
        op_copy["room_type_jp"] = translated_room["name"]
        op_copy["room_abbr_jp"] = translated_room["abbr"]
        compliance_opinions.append(op_copy)

    from pipeline.paths import OUTPUT_ROOT
    from exporter.pdf_generator import JPPDFGenerator

    project_dir = OUTPUT_ROOT / "projects" / project_id
    
    project_name = project.get("original_filename", f"Project_{project_id}")
    address = "東京都千代田区麹町" # 현장 진단 기본 템플릿
    inspector_name = "漏水診断エキスパート"

    # 만약 incident 데이터가 있다면 정보 획득
    incident_path = project_dir / "incident.json"
    if incident_path.exists():
        try:
            with open(incident_path, "r", encoding="utf-8") as f:
                inc_data = json.load(f)
                project_name = inc_data.get("customer_name", project_name)
                address = inc_data.get("address", address)
        except Exception as e:
            # SP4/H-2: 폴백은 유지하되 원인은 소멸시키지 않는다
            logger.warning(f"incident.json unreadable for project {project_id}: {e}")

    # 2D & 3D 이미지 경로 매핑
    image_2d = str(project_dir / "page0_rooms.png")
    if not os.path.exists(image_2d):
        image_2d = "test_original.png" # Fallback static

    image_3d = str(project_dir / "page0_3d.png")
    if not os.path.exists(image_3d):
        image_3d = "test_deskewed.png" # Fallback static

    output_pdf = str(project_dir / "page0_compliance_report.pdf")

    try:
        pdf_path = JPPDFGenerator.generate_report(
            project_id=project_id,
            project_name=project_name,
            address=address,
            inspector_name=inspector_name,
            compliance_opinions=compliance_opinions,
            image_2d_path=image_2d,
            image_3d_path=image_3d,
            output_pdf_path=output_pdf
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="Generated PDF not found on server")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"leak_report_{project_id}.pdf"
    )


# ================================================================
# Stripe Japan 결제 & i18n 통합 라우트 (Phase 9)
# ================================================================

@router.post("/payments/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    auth_data: dict = Depends(get_current_user_and_db)
):
    """
    엔화(JPY) 결제를 위한 Stripe Checkout Session 생성 API
    """
    user_id = auth_data["user_id"]
    db = auth_data["db"]
    
    try:
        session_info = StripePaymentService.create_checkout_session(
            user_id=user_id,
            plan_type=request.plan_type,
            db=db
        )
        return CheckoutSessionResponse(**session_info)
    except CircuitBreakerOpenException as e:
        # SP2 후속 정비: 회로 OPEN 상태에서 무료(0엔) checkout 세션을 발급하는
        # 'circuit_breaker_bypass' 그레이스 발급은 결제 무결성 훼손 우려로 제거한다.
        # 클라이언트는 잠시 후 재시도하도록 안내한다 (fail-closed).
        logger.error(f"Checkout blocked - payment circuit breaker OPEN: {e}")
        raise HTTPException(
            status_code=503,
            detail="Payment gateway temporarily unavailable. Please retry in a minute."
        )
    except Exception as e:
        # 내부 예외 메시지를 클라이언트에 노출하지 않는다 (정보 유출 방지).
        logger.error(f"[Payments] Checkout creation failed for user={user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="決済セッションの作成に失敗しました。しばらくしてから再度お試しください。",
        )


@router.post("/payments/webhook")
async def payment_webhook(
    request: Request,
    db = Depends(get_supabase_client)
):
    """
    Stripe 결제 성공 콜백/웹훅 처리 API.

    SP6/P0-8: 재시도 가능 오류(DB 반영 실패)는 5xx 로 반환해 Stripe 재전달을
    유도하고, 서명 불일치처럼 재시도로 해결되지 않는 오류는 4xx 로 반환한다.
    중복 이벤트는 200 으로 흡수해 Stripe 의 무한 재시도를 막는다.
    """
    raw_body = await request.body()
    sig_header = request.headers.get("stripe-signature")

    result = StripePaymentService.verify_and_apply_webhook(
        raw_body=raw_body,
        sig_header=sig_header,
        db=db
    )

    if result.get("status") == "error":
        # 재시도 가능 여부에 따라 상태 코드를 분리한다.
        status_code = 503 if result.get("retryable") else 400
        raise HTTPException(status_code=status_code, detail=result.get("message"))

    return result


@router.get("/payments/status", response_model=PaymentStatusResponse)
async def get_payment_status(
    auth_data: dict = Depends(get_current_user_and_db)
):
    """
    현재 사용자의 결제 요금제 정보 및 잔여 크레딧 현황을 조회하는 API
    """
    user_id = auth_data["user_id"]
    db = auth_data["db"]
    
    plan_type = "free"
    credits = 0
    
    try:
        res = db.table("profiles").select("plan_type, credits").eq("id", user_id).execute()
        if res.data:
            plan_type = res.data[0].get("plan_type", "free") or "free"
            credits = res.data[0].get("credits", 0) or 0
    except Exception as e:
        # SP6/P0-8: 과거 이 블록은 정의되지 않은 `project_id` 를 참조해
        #   DB 오류 시 NameError 를 유발하고 500 으로 번지던 복사-붙여넣기 결함이었다.
        #   또한 "Fallback" 이라는 주석과 달리 실제 폴백 로직은 존재하지 않았다.
        #   현재: 오류를 기록하고 보수적 기본값(free / 크레딧 0)을 유지한다.
        logger.error(f"[Payments] Failed to read profile for user={user_id}: {e}")

    active = StripePaymentService.check_user_access_gate(user_id, db)
    circuit = StripePaymentService._circuit_state
    
    return PaymentStatusResponse(
        plan_type=plan_type,
        credits=credits,
        active=active,
        circuit_state=circuit
    )


@router.post("/projects/{project_id}/media")
async def upload_project_media(
    project_id: str,
    file: UploadFile = File(...),
    auth_data: dict = Depends(get_current_user_and_db)
):
    """
    현장 조사 사진 업로드 API (Circuit Breaker 및 로컬 폴백 지원)
    """
    db = auth_data["db"]
    
    # SP6/P0-1: 소유권 검증 (C1).
    # 과거: try/except 가 HTTPException(404) 까지 삼켜 "fallback" 로그만 남기고
    #       진행했다. 결과적으로 존재하지 않는/권한 없는 프로젝트에도
    #       사진 업로드가 가능했다. 검증 자체가 무효화되어 있던 상태다.
    require_project(db, project_id, auth_data["user_id"])

    # 파일 확장자 검사
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg"]:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, JPEG images are allowed.")

    # 파일 크기 검사 (Max 10MB)
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds maximum limit of 10MB.")

    # 저장 파일 경로 및 이름 결정
    import uuid
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    media_dir = os.path.join(UPLOAD_DIR, "media", project_id)
    os.makedirs(media_dir, exist_ok=True)
    local_path = os.path.join(media_dir, safe_filename)

    file_bytes = await file.read()
    file.file.seek(0)

    # 1. Supabase Storage 업로드 시도 (Circuit Breaker 탑재)
    supabase_url = None
    try:
        # Supabase Storage에 업로드 시도
        # 버킷명 'projects' 하위 'media/{project_id}/{safe_filename}'
        storage_path = f"media/{project_id}/{safe_filename}"
        db.storage.from_("projects").upload(storage_path, file_bytes, {"content-type": file.content_type})
        
        # CDN Public URL 확보
        supabase_url = db.storage.from_("projects").get_public_url(storage_path)
    except Exception as e:
        # Storage 업로드 실패 시 (인프라 장애, Mock 환경 등) 로컬 폴백 처리
        logger.warning(f"Supabase storage upload failed, local fallback used: {e}")

    # 2. 로컬 스토리지에 무조건 복사하여 서빙 가용성 이중화 확보
    with open(local_path, "wb") as buffer:
        buffer.write(file_bytes)

    # 최종 노출 URL: Supabase CDN 우선 바인딩, 실패 시 로컬 CDN URL로 자동 롤백
    final_url = supabase_url if supabase_url else f"/api/v1/projects/{project_id}/media/{safe_filename}"

    return {
        "media_id": f"att_{uuid.uuid4().hex[:12]}",
        "url": final_url,
        "filename": safe_filename,
        "storage_mode": "supabase_cdn" if supabase_url else "local_fallback"
    }


@router.get("/projects/{project_id}/media/{file_name}")
async def get_project_media(project_id: str, file_name: str):
    """
    로컬 폴백 미디어 직접 서빙 스트리밍 API (i18n / 오프라인 가용성 보완)

    보안 정책 (SP1/S-5): URL 세그먼트를 파일 경로에 그대로 조립하지 않고,
    세그먼트 화이트라이닝 + resolve 기반 컨테인먼트 검증으로 경로 순회를 차단한다.
    """
    # 1. 세그먼트 무결성: '..', '.', 구분자·드라이브 접두어 포함 세그먼트 원천 차단
    if not _is_safe_path_segment(project_id):
        raise HTTPException(status_code=400, detail="Invalid project id")
    if not _is_safe_path_segment(file_name):
        raise HTTPException(status_code=400, detail="Invalid file name")

    # 2. 컨테인먼트 검증: resolve 결과가 media/{project_id} 내부에 머무는지 이중 확인
    media_root = Path(UPLOAD_DIR).resolve() / "media"
    candidate = (media_root / project_id / file_name).resolve()
    if candidate.parent != (media_root / project_id).resolve():
        raise HTTPException(status_code=400, detail="Path traversal detected")

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    return FileResponse(str(candidate))


@router.patch("/projects/{project_id}/incidents/{case_id}/pins")
async def patch_incident_pins(
    project_id: str,
    case_id: str,
    request: IncidentPinUpdateRequest,
    auth_data: dict = Depends(get_current_user_and_db)
):
    """
    3D IFC 객체 핀(LeakSource, DamageZone 등) 좌표 매핑 및 현장 사진/소견 바인딩 API
    """
    db = auth_data["db"]
    
    # 1. 프로젝트 소유권 확인 (C1)
    # 과거: try/except 가 HTTPException(404) 까지 삼켜 검증이 무효화되어 있었다.
    #       타인 프로젝트의 3D 핀 좌표를 수정할 수 있는 상태였다.
    require_project(db, project_id, auth_data["user_id"])

    # 2. incident.json 로드
    path = _incident_json_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Incident data not found. Create incident first.")

    from scene.serializer import load_leak_case, save_leak_case, leak_case_to_dict
    from domain.models import LeakSource, DamageZone, IncidentAnnotation, Point, DamageType, Severity
    from datetime import datetime, timezone

    case = load_leak_case(path)
    if case.case_id != case_id:
        raise HTTPException(status_code=400, detail="Case ID mismatch")

    updated = False

    # 3. 핀 타입 별 정밀 타격 업데이트
    if request.pin_type == "leak_source":
        # 좌표 거리 0.1 이내인 기존 leak_source 검색
        found_ls = None
        for ls in case.leak_sources:
            dist = ((ls.point.x - request.coordinate.x) ** 2 + (ls.point.y - request.coordinate.y) ** 2) ** 0.5
            if dist < 0.1:
                found_ls = ls
                break
        
        if found_ls:
            # 기존 핀 업데이트
            found_ls.description = request.comment
            # Pydantic schema는 photos가 없으므로 Custom meta dictionary나 description 등을 활용하거나 필드 갱신
            found_ls.description += f" [Attached Photos: {', '.join(request.media_urls)}]"
            updated = True
        else:
            # 새로운 LeakSource 추가
            new_ls = LeakSource(
                point=Point(x=request.coordinate.x, y=request.coordinate.y),
                room_id=request.target_room_id,
                confidence=1.0,
                description=f"{request.comment} [Attached Photos: {', '.join(request.media_urls)}]"
            )
            case.leak_sources.append(new_ls)
            updated = True

    elif request.pin_type == "damage_zone":
        # 가장 가까운 damage_zone 검색
        found_dz = None
        for dz in case.damage_zones:
            # 다각형 중심이나 첫 번째 꼭짓점으로 매칭
            if dz.polygon:
                dist = ((dz.polygon[0].x - request.coordinate.x) ** 2 + (dz.polygon[0].y - request.coordinate.y) ** 2) ** 0.5
                if dist < 1.0:
                    found_dz = dz
                    break
        
        if found_dz:
            found_dz.photos = list(set(found_dz.photos + request.media_urls))
            found_dz.description = request.comment
            updated = True
        else:
            # 신규 데미지 존 생성
            new_dz = DamageZone(
                id=len(case.damage_zones) + 1,
                damage_type=DamageType.CEILING, # 기본값
                severity=Severity.MEDIUM,
                polygon=[Point(x=request.coordinate.x, y=request.coordinate.y)],
                room_id=request.target_room_id,
                description=request.comment,
                photos=request.media_urls
            )
            case.damage_zones.append(new_dz)
            updated = True

    elif request.pin_type == "annotation":
        # 좌표 거리 0.1 이내인 어노테이션 검색
        found_ann = None
        for ann in case.annotations:
            dist = ((ann.anchor_point.x - request.coordinate.x) ** 2 + (ann.anchor_point.y - request.coordinate.y) ** 2) ** 0.5
            if dist < 0.1:
                found_ann = ann
                break
        
        if found_ann:
            found_ann.attached_photo = request.media_urls[0] if request.media_urls else None
            found_ann.text = request.comment
            updated = True
        else:
            new_ann = IncidentAnnotation(
                id=len(case.annotations) + 1,
                anchor_point=Point(x=request.coordinate.x, y=request.coordinate.y),
                anchor_room_id=request.target_room_id,
                text=request.comment,
                category="photo",
                attached_photo=request.media_urls[0] if request.media_urls else None
            )
            case.annotations.append(new_ann)
            updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="Failed to map pin coordinates.")

    case.bump_version()
    save_leak_case(case, path)

    # 4. Supabase DB projects 테이블 metadata 동기화
    db_update = {
        "metadata": {
            "compliance_opinions": [ls.get("compliance_opinion", {}) for ls in leak_case_to_dict(case).get("leak_sources", []) if ls.get("compliance_opinion")],
            "media_mapping_updated_at": datetime.now(timezone.utc).isoformat(),
            "incident_version": case.version
        }
    }
    
    try:
        # 소유자 기준으로 한정 (C1) — require_project 로 이미 검증했으나 2중 방어
        db.table("projects").update(db_update).eq("id", project_id).eq("user_id", auth_data["user_id"]).execute()
    except Exception as e:
        logger.warning(f"Pin update DB persist failed for {project_id}/{case_id}: {e}")

    return {
        "status": "success",
        "case_id": case_id,
        "version": case.version,
        "pin_type": request.pin_type,
        "pin_mapped": True
    }


@router.get("/projects/{project_id}/compliance-checksheet")
async def get_compliance_checksheet(
    project_id: str,
    format: str = "pdf",  # "pdf" 또는 "json"
    chief_designer: str = "日本一級建築士",
    license_number: str = "",  # SP1/D-1: 가짜 면허번호 기본값 금지 - 미입력 시 문서에 (未登録) 표기
    digital_seal_path: str = None,
    auth_data: dict = Depends(get_current_user_and_db)
):
    """
    일본 국토교통성(MLIT) 2026 가이드라인 규격 'BIM 준공 설계자 자가 확인 체크시트' 다운로드 및 조회 API (Phase 12)
    """
    user_id = auth_data["user_id"]
    db = auth_data["db"]
    
    # [하네스 프로토콜 - 결제 가드 및 회로 차단기]
    # 단순 JSON 화면 조회 시에는 최소 1크레딧 기본 가드를 태우고,
    # 실제 법적 효력을 가지는 PDF 다운로드 시에는 10 크레딧 차등 가드 및 실질 차감을 집행합니다!
    required_amount = 10 if format == "pdf" else 1
    if not StripePaymentService.check_user_access_gate(user_id, db, amount=required_amount):
        raise HTTPException(
            status_code=402, 
            detail=f"Payment required. Please purchase a plan or single ticket at /payments/checkout-session to download checksheets. ({required_amount} credits required for format={format})"
        )
        
    # 정식 PDF 리포트 발행일 때만 실질적인 10 크레딧 차감 집행!
    if format == "pdf":
        StripePaymentService.deduct_credit(user_id, db, amount=10)

    # 프로젝트 정보 획득
    #
    # SP6/P0-1: 과거 이 호출은 try/except 로 감싸져 있었고, 소유권 검증 실패(404)나
    # DB 장애(503)를 삼킨 뒤 `{"id": project_id, "original_filename": ...}` 를
    # 조립해 계속 진행했다. 즉 **자신이 소유하지 않은 project_id 로도** 로컬 파일을
    # 읽어 체크시트를 발급할 수 있는 IDOR 우회 경로였다.
    # 현재: 실패는 그대로 전파해 404/503 으로 응답한다 (fail-closed).
    project = require_project(db, project_id, auth_data["user_id"], select="*")

    building_name = project.get("original_filename", f"Project_{project_id}")
    if building_name.endswith('.pdf') or building_name.endswith('.PDF'):
        building_name = building_name[:-4]

    from pipeline.paths import OUTPUT_ROOT
    import json
    
    comp_path = OUTPUT_ROOT / "projects" / project_id / "page0_compliance.json"
    
    check_items_list = []
    overall_judgment = "適合"
    compliance_data = None  # SP5: energy 섹션 접근을 위한 초기화

    if comp_path.exists():
        try:
            with open(comp_path, "r", encoding="utf-8") as f:
                compliance_data = json.load(f)
                
            from compliance.evaluator import evaluate_project
            report = evaluate_project(compliance_data)
            
            # evaluate_project의 결과를 활용하여 체크 항목들 빌드
            room_results = report.get("room_results", [])
            
            idx = 1
            for r in room_results:
                room_id = r.get("room_id", "unknown")
                room_kind = r.get("room_kind", "UNKNOWN")
                
                # 번역 및 i18n
                translated_room = JPTranslationEngine.translate_room(room_kind)
                room_name_jp = translated_room["name"]
                
                for eval_item in r.get("evaluations", []):
                    rule_id = eval_item.get("rule_id")
                    rule_name = eval_item.get("rule_name")
                    status = eval_item.get("status")
                    reason = eval_item.get("reason")
                    
                    # 규칙 종류에 따른 국토교통성 조문 표준화 매핑
                    # SP2/L-3: 규칙이 반환한 구조화 수치(facts)를 직접 소비한다.
                    # 사람이 읽는 reason 문자열을 regex로 재파싱하는 결합은 제거되었다.
                    facts = eval_item.get("facts") or {}
                    if rule_id == "RULE-JP-LAW-28":
                        article_no = f"第28条第1項 (居室{idx})"
                        item_name = f"{room_name_jp} の有効採光面積の割合"
                        standard_value = "窓面積 / 居室面積 >= 1/7"

                        win_area = facts.get("window_area_m2")
                        floor_area = facts.get("floor_area_m2")
                        if win_area and floor_area and win_area > 0 and floor_area > 0:
                            ratio_denominator = floor_area / win_area
                            calc_val = (
                                f"窓 {win_area:.2f}m² / 床 {floor_area:.2f}m² "
                                f"(= 1/{ratio_denominator:.1f})"
                            )
                        else:
                            calc_val = "-"

                    elif rule_id == "RULE-JP-ORD-21":
                        article_no = f"令第21条 (居室{idx})"
                        item_name = f"{room_name_jp} の天井高"
                        standard_value = "天井高 >= 2.1m"

                        height_mm = facts.get("height_mm")
                        if height_mm is not None:
                            calc_val = f"{float(height_mm) / 1000.0:.2f}m"
                        else:
                            calc_val = "-"
                    else:
                        article_no = "関係法令"
                        item_name = rule_name
                        standard_value = "-"
                        calc_val = "-"

                    # 소견 문구는 rule_id 기반으로만 선정한다 (reason 부분일치 매칭 금지 - SP2/L-3)
                    if rule_id == "RULE-JP-LAW-28":
                        if status == "PASS":
                            inspector_comment = f"3D BIM幾何演算の結果、当該{room_name_jp}の有効採光面積が法定基準をクリアしており、法第28条に適合することを確認した。"
                        else:
                            inspector_comment = f"3D BIM幾何演算の結果、有効採光面積が法定基準の1/7を下回っており、意図的な開口の拡充、または窓の増設が必要と判断される。"
                    elif rule_id == "RULE-JP-ORD-21":
                        if status == "PASS":
                            inspector_comment = f"居室のスラブ上部から天井面までの平均高さが2.1m以上を確保しており、建築基準法施行令第21条に適合することを確認した。"
                        else:
                            inspector_comment = f"天井高が2.1m未満であり、居室としての天井高さ基準を充足しないため、設計変更またはダクトスペースの調整が必要と判断される。"
                    else:
                        inspector_comment = "設計図書とBIMモデルの幾何情報が完全に一致していることを確認いたしました。"
                        
                    check_items_list.append({
                        "article_no": article_no,
                        "item_name_jp": item_name,
                        "standard_value": standard_value,
                        "calculated_value": calc_val,
                        "status": status,
                        "inspector_comment": inspector_comment
                    })
                idx += 1
                
            if report.get("total_violations", 0) > 0:
                overall_judgment = "不適合"
        except Exception as e:
            # 평가 실패는 조용히 삼키지 않고 기록한다 (SP1/H-2 선제 정비)
            logger.error(f"Compliance evaluation failed for project {project_id}: {e}")

    # --- 建築物省エネ法 BEI 평가 (SP5) ---
    # compliance JSON에 'energy' 섹션이 있으면 채에네기야법 항목을 추가한다.
    # FAIL 시 종합 판정도 不適合으로 강등한다.
    try:
        if compliance_data and isinstance(compliance_data.get("energy"), dict):
            from compliance.rules_energy import evaluate_energy_compliance, RULE_ID_ENERGY
            energy_item = evaluate_energy_compliance(compliance_data["energy"])
            energy_item.pop("facts", None)  # 체크시트 아이템 계약에는 facts 미포함
            check_items_list.append(energy_item)
            if energy_item["status"] == "FAIL":
                overall_judgment = "不適合"
    except Exception as e:
        logger.warning(f"Energy (省エネ法) evaluation skipped for {project_id}: {e}")

    # 최종적으로 평가 데이터가 없는 경우 (보안 정책 SP1/L-2):
    # 가짜「適合」항목을 만들어내는 것은 법적 문서 위조이므로 금지한다.
    # 판정 불가 사실을 명시적으로 반환한다.
    if not check_items_list:
        check_items_list = [
            {
                "article_no": "-",
                "item_name_jp": "判定不能 (評価データ不在)",
                "standard_value": "-",
                "calculated_value": "-",
                "status": "N/A",
                "inspector_comment": "法規判定に必要なBIM幾何データが存在しないため、適合性を自動判定できませんでした。図面変換完了後に再度発行してください。"
            }
        ]
        overall_judgment = "判定不能"

    # format = json 일 때 Pydantic 스키마 응답
    if format == "json":
        from app.schemas.compliance import BIMComplianceChecksheet, BIMComplianceCheckItem
        
        check_items_pydantic = [
            BIMComplianceCheckItem(
                article_no=item["article_no"],
                item_name_jp=item["item_name_jp"],
                standard_value=item["standard_value"],
                calculated_value=item["calculated_value"],
                status=item["status"],
                inspector_comment=item["inspector_comment"]
            )
            for item in check_items_list
        ]
        
        return BIMComplianceChecksheet(
            project_id=project_id,
            building_name=building_name,
            chief_designer=chief_designer,
            license_number=license_number,
            check_items=check_items_pydantic,
            overall_judgment=overall_judgment,
            legal_basis=_legal_basis_note() or None,  # SP2/L-4
            digital_seal_url=digital_seal_path
        )

    # format = pdf 일 때 PDF 파일 스트림 응답
    from exporter.pdf_generator import JPPDFGenerator
    project_dir = OUTPUT_ROOT / "projects" / project_id
    output_pdf = str(project_dir / "page0_compliance_checksheet.pdf")

    try:
        pdf_path = JPPDFGenerator.generate_compliance_checksheet(
            project_id=project_id,
            building_name=building_name,
            chief_designer=chief_designer,
            license_number=license_number,
            check_items=check_items_list,
            overall_judgment=overall_judgment,
            digital_seal_path=digital_seal_path,
            output_pdf_path=output_pdf,
            legal_basis_note=_legal_basis_note() or None  # SP2/L-4
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate compliance checksheet PDF: {str(e)}")

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="Generated checksheet PDF not found on server")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"compliance_checksheet_{project_id}.pdf"
    )


# ================================================================
# BIM 견적서 (見積書) API — SP3/Q-1
# 수량산출(takeoff) + 단가(pricing) → 数量取合書 호환 견적 문서/PDF
# ================================================================

QUOTATION_CREDIT_COST = 2


@router.post("/projects/{project_id}/quotation", response_model=QuotationDocument)
async def create_project_quotation(
    project_id: str,
    auth_data: dict = Depends(get_current_user_and_db)
):
    """
    BIM 지오메트리에서 수량을 산출하고 단가 마스터로 견적 문서(JSON)를 생성한다.

    - 원천: out/projects/{id}/page0_rooms.json (+ page0_compliance.json 개구부)
    - 모든 명산은 source_ref로 IFC 엔티티 역추적 가능
    - fail-closed: 단가 미등장 품목·스케일 부재 등은 조용한 0엔 계상 없이 처리
    """
    user_id = auth_data["user_id"]
    db = auth_data["db"]

    if not StripePaymentService.check_user_access_gate(user_id, db, amount=QUOTATION_CREDIT_COST):
        raise HTTPException(
            status_code=402,
            detail=(f"Payment required. {QUOTATION_CREDIT_COST} credits required to build a quotation. "
                    "Purchase a plan at /payments/checkout-session.")
        )
    StripePaymentService.deduct_credit(user_id, db, amount=QUOTATION_CREDIT_COST)

    from exporter.quotation_json import build_quotation_document, save_quotation, load_quotation

    project_dir = OUTPUT_ROOT / "projects" / project_id
    rooms_path = project_dir / "page0_rooms.json"
    comp_path = project_dir / "page0_compliance.json"

    if not rooms_path.exists():
        raise HTTPException(status_code=404, detail="Geometry data not found. Convert a PDF first.")

    with open(rooms_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    compliance_doc = None
    if comp_path.exists():
        try:
            with open(comp_path, "r", encoding="utf-8") as f:
                compliance_doc = json.load(f)
        except Exception as e:
            logger.warning(f"Compliance doc unreadable for quotation ({project_id}): {e}")

    document = build_quotation_document(project_id, payload, compliance_doc)
    save_quotation(document, str(project_dir))
    return document


@router.get("/projects/{project_id}/quotation.pdf")
async def download_project_quotation_pdf(
    project_id: str,
    auth_data: dict = Depends(get_current_user_and_db)
):
    """
    저장된 견적 문서를 お見積書 PDF로 출력한다. 문서가 없으면 동일 입력으로 재생성한다
    (결정론적 파이프라인이므로 동일 크레딧으로 한 번만 과금된다).
    """
    user_id = auth_data["user_id"]
    db = auth_data["db"]

    if not StripePaymentService.check_user_access_gate(user_id, db, amount=QUOTATION_CREDIT_COST):
        raise HTTPException(
            status_code=402,
            detail=(f"Payment required. {QUOTATION_CREDIT_COST} credits required to download a quotation PDF.")
        )
    StripePaymentService.deduct_credit(user_id, db, amount=QUOTATION_CREDIT_COST)

    from exporter.quotation_json import load_quotation
    from exporter.quotation_pdf import QuotationPDFGenerator

    project_dir = OUTPUT_ROOT / "projects" / project_id
    document = load_quotation(str(project_dir))
    if document is None:
        # 결정론적 산출물이므로 POST 결과가 없으면 즉석 재구성 (무료 재발급 아님 - 위 POST에서 과금됨)
        rooms_path = project_dir / "page0_rooms.json"
        if not rooms_path.exists():
            raise HTTPException(status_code=404, detail="Quotation not found and no geometry data to rebuild from")
        from exporter.quotation_json import build_quotation_document
        with open(rooms_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        document = build_quotation_document(project_id, payload)

    output_pdf = str(project_dir / "quotation.pdf")
    try:
        pdf_path = QuotationPDFGenerator.generate(project_id, document, output_pdf_path=output_pdf)
    except Exception as e:
        logger.error(f"Quotation PDF generation failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate quotation PDF: {str(e)}")

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="Generated quotation PDF not found on server")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"quotation_{project_id}.pdf"
    )


@router.post("/projects/{project_id}/sync", response_model=OfflineSyncResponse)
async def sync_offline_changes(
    project_id: str,
    request: OfflineSyncRequest,
    auth_data: dict = Depends(get_current_user_and_db),
):
    """
    IndexedDB 기반 오프라인 델타 벌크 동기화 및 낙관적 락 충돌 방지 API (Phase 13)
    """
    from datetime import datetime, timezone
    import uuid

    db = auth_data["db"]
    require_project(db, project_id, auth_data["user_id"])

    # 1. incident.json 로드 및 낙관적 락 검증
    incident_path = _incident_json_path(project_id)
    if not os.path.exists(incident_path):
        raise HTTPException(status_code=404, detail="Incident data not found. Create incident first.")

    from scene.serializer import load_leak_case, save_leak_case, leak_case_to_dict
    case = load_leak_case(incident_path)

    # 낙관적 락 충돌 검사
    if request.base_version != case.version:
        raise HTTPException(
            status_code=409,
            detail=f"Conflict detected. Server version: {case.version}, Client base version: {request.base_version}"
        )

    # 2. page0_rooms.json 로드
    geom_path = str(OUTPUT_ROOT / "projects" / project_id / "page0_rooms.json")
    if not os.path.exists(geom_path):
        raise HTTPException(status_code=404, detail="Geometry data not available")

    with open(geom_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # 3. 델타 연산 순차 적용
    from correction.patch import CorrectionSession
    from correction.operations import (
        change_room_type, move_wall, add_wall, delete_wall,
        merge_rooms, split_room, move_opening,
        place_leak_source, paint_damage_zone, delete_room,
    )
    from correction.rebuild import rebuild_after_correction
    from domain.models import RoomKind, Point, LeakSource, DamageZone, IncidentAnnotation, DamageType, Severity

    session = CorrectionSession(
        session_id=str(uuid.uuid4())[:8],
        case_id=case.case_id,
    )

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

    # 각 오프라인 연산 순차 적용
    for op in request.operations:
        handler = op_dispatch.get(op.operation)
        if not handler:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {op.operation}")
        patch = handler(payload, op.params, op.author)
        if patch:
            session.patches.append(patch)

        # incident 관련 도메인 모델 데이터도 동시 싱크처리 (Optimistic lock 병합 처리)
        if op.operation == "place_leak_source":
            pt = Point(x=op.params["point"]["x"], y=op.params["point"]["y"])
            new_ls = LeakSource(
                point=pt,
                room_id=op.params.get("room_id"),
                confidence=1.0,
                description=op.params.get("description", "")
            )
            case.leak_sources.append(new_ls)
        elif op.operation == "paint_damage_zone":
            poly = [Point(x=pt["x"], y=pt["y"]) for pt in op.params["polygon"]]
            new_dz = DamageZone(
                id=len(case.damage_zones) + 1,
                damage_type=DamageType(op.params["damage_type"]),
                severity=Severity(op.params["severity"]),
                polygon=poly,
                room_id=op.params.get("room_id"),
                description=op.params.get("description", "")
            )
            case.damage_zones.append(new_dz)

    # 4. 재빌드 실행
    project_dir = str(OUTPUT_ROOT / "projects" / project_id)
    payload = rebuild_after_correction(payload, session, output_dir=project_dir)

    # 5. 일본 건축 규정 및 공용/전유 누수 책임 판정 연동
    from compliance.jp_compliance import JPResponsibilityEngine
    compliance_opinions = []
    
    incident = payload.get("incident", {})
    leak_sources = incident.get("leak_sources", [])
    rooms = payload.get("rooms", [])
    
    for ls in leak_sources:
        rid = ls.get("room_id")
        target_room = next((r for r in rooms if r.get("id") == rid), None)
        room_meta = target_room if target_room else {"id": rid, "kind": "UNKNOWN"}
        
        opinion = JPResponsibilityEngine.evaluate_leak(ls.get("point", {}), room_meta)
        compliance_opinions.append(opinion)
        ls["compliance_opinion"] = opinion
        
    incident["compliance_opinions"] = compliance_opinions
    payload["incident"] = incident

    # 6. 정합성을 위해 수정된 page0_rooms.json 저장
    with open(geom_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 7. incident.json 버전 증가 및 파일 저장
    case.bump_version()
    # 핀 매핑 결과가 반영되도록 case 갱신 후 저장
    save_leak_case(case, incident_path)

    # 8. DB 상태 업데이트
    ifc_path = payload.get("_rebuilt_ifc", "")
    db_update = {
        "status": "completed",
        "metadata": {
            "compliance_opinions": compliance_opinions,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "incident_version": case.version
        }
    }
    if ifc_path:
        db_update["ifc_url"] = ifc_path
        
    try:
        # 소유자 기준으로 한정 (C1) — require_project 로 이미 검증했으나 2중 방어
        db.table("projects").update(db_update).eq("id", project_id).eq("user_id", auth_data["user_id"]).execute()
    except Exception as e:
        logger.warning(f"Offline-sync DB persist failed for {project_id}: {e}")

    return OfflineSyncResponse(
        status="success",
        session_id=session.session_id,
        current_version=case.version,
        patches_applied=session.patch_count,
        operation_summary=session.operation_summary
    )





