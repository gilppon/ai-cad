import logging
import os
import shutil
from pathlib import Path
from app.worker.celery_app import celery_app
from core.engine import PipelineEngine
from app.api.deps import get_supabase_client

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="process_pdf_task")
def process_pdf_task(self, file_path: str, project_id: str, user_id: str | None = None):
    """
    PDF 파일을 분석하여 IFC로 변환하는 백그라운드 작업.

    STATE Phase 0.4: 워커는 service_role 경계이므로 user_id를 함께 받아
    소유권을 재확인한다. user_id 없이 호출되면 소유권 검증이 불가하므로
    에러로 기록하고 중단한다 (fail-closed, 조용한 처리 금지).
    """
    self.update_state(state="PROGRESS", meta={"progress": 10})
    db = get_supabase_client()
    if not user_id:
        logger.error(f"[Task {project_id}] missing user_id — refuse to process without ownership proof")
        try:
            db.table("projects").update({
                "status": "error",
                "error_message": "ownership proof missing (user_id required)"
            }).eq("id", project_id).execute()
        except Exception as db_err:
            logger.error(f"[Task {project_id}] Failed to persist error state to DB: {db_err}")
        return {"status": "failed", "message": "ownership proof missing (user_id required)"}
    
    try:
        # 1. 엔진 초기화
        engine = PipelineEngine(project_id=project_id)
        
        # 2. 분석 실행
        self.update_state(state="PROGRESS", meta={"progress": 30})
        result = engine.process_document(file_path)
        
        if result["status"] == "success":
            self.update_state(state="PROGRESS", meta={"progress": 100})
            ifc_path = result["artifacts"]["ifc"]
            # ToDo: Upload IFC to RLS or S3 and get public URL
            # For now, store the local path or relative URL
            # STATE: 소유권 스코프 유지 (id + user_id)
            db.table("projects").update({
                "status": "completed",
                "ifc_url": ifc_path
            }).eq("id", project_id).eq("user_id", user_id).execute()
            
            return {
                "status": "success",
                "project_id": project_id,
                "artifacts": result["artifacts"]
            }
        else:
            error_msg = result.get("message", "Unknown engine error")
            db.table("projects").update({
                "status": "error",
                "error_message": error_msg
            }).eq("id", project_id).eq("user_id", user_id).execute()
            
            return {
                "status": "failed",
                "message": result.get("message", "Unknown engine error")
            }
            
    except Exception as e:
        error_msg = str(e)
        try:
            db.table("projects").update({
                "status": "error",
                "error_message": error_msg
            }).eq("id", project_id).eq("user_id", user_id).execute() if user_id else None
        except Exception as db_err:
            # SP4/H-2: 실패 원인을 소멸시키지 않고 반드시 기록한다
            logger.error(f"[Task {project_id}] Failed to persist error state to DB: {db_err}")
            
        return {
            "status": "failed",
            "message": str(e)
        }
    finally:
        # 처리 완료 후 원본 PDF 삭제 (선택 사항)
        # if os.path.exists(file_path):
        #     os.remove(file_path)
        pass
