# correction/history.py — 보정 이력 저장/로드/조회
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from correction.patch import CorrectionSession


def _history_dir(project_dir: str) -> str:
    """프로젝트별 보정 이력 디렉토리"""
    d = os.path.join(project_dir, "correction_history")
    os.makedirs(d, exist_ok=True)
    return d


def save_session(session: CorrectionSession, project_dir: str) -> str:
    """
    보정 세션을 JSON 파일로 저장.

    Returns:
        저장된 파일 경로
    """
    hist_dir = _history_dir(project_dir)
    filename = f"session_{session.session_id}.json"
    path = os.path.join(hist_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

    return path


def load_session(session_id: str, project_dir: str) -> Optional[CorrectionSession]:
    """세션 ID로 보정 세션 로드"""
    hist_dir = _history_dir(project_dir)
    path = os.path.join(hist_dir, f"session_{session_id}.json")

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return CorrectionSession.from_dict(data)


def list_sessions(project_dir: str) -> List[Dict[str, Any]]:
    """
    프로젝트의 모든 보정 세션 요약 목록 반환.

    Returns:
        [{"session_id": ..., "created_at": ..., "status": ..., "patch_count": ..., "correction_source": ...}, ...]
    """
    hist_dir = _history_dir(project_dir)

    if not os.path.exists(hist_dir):
        return []

    sessions = []
    for fname in sorted(os.listdir(hist_dir)):
        if not fname.startswith("session_") or not fname.endswith(".json"):
            continue

        path = os.path.join(hist_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions.append({
                "session_id": data.get("session_id", ""),
                "case_id": data.get("case_id", ""),
                "created_at": data.get("created_at", ""),
                "status": data.get("status", ""),
                "patch_count": data.get("patch_count", 0),
                "correction_source": data.get("correction_source", "none"),
                "operation_summary": data.get("operation_summary", {}),
            })
        except Exception:
            continue

    return sessions


def get_correction_stats(project_dir: str) -> Dict[str, Any]:
    """
    프로젝트의 보정 통계 요약.

    Returns:
        {
            "total_sessions": int,
            "total_patches": int,
            "human_sessions": int,
            "auto_sessions": int,
            "operations_breakdown": {op_name: count, ...}
        }
    """
    all_sessions = list_sessions(project_dir)

    total_patches = sum(s.get("patch_count", 0) for s in all_sessions)
    human_count = sum(1 for s in all_sessions if s.get("correction_source") in ("human", "mixed"))
    auto_count = sum(1 for s in all_sessions if s.get("correction_source") == "auto")

    ops_breakdown: Dict[str, int] = {}
    for s in all_sessions:
        for op, count in s.get("operation_summary", {}).items():
            ops_breakdown[op] = ops_breakdown.get(op, 0) + count

    return {
        "total_sessions": len(all_sessions),
        "total_patches": total_patches,
        "human_sessions": human_count,
        "auto_sessions": auto_count,
        "operations_breakdown": ops_breakdown,
    }
