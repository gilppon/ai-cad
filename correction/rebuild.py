# correction/rebuild.py — 보정 후 다운스트림 재빌드
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from correction.patch import CorrectionSession


def rebuild_after_correction(
    payload: Dict[str, Any],
    session: CorrectionSession,
    output_dir: Optional[str] = None,
    rebuild_ifc: bool = True,
) -> Dict[str, Any]:
    """
    보정 세션 적용 후 다운스트림 데이터를 재빌드.

    처리 내용:
    1. payload에 보정 메타데이터 기록
    2. rooms_count / walls_count 재계산
    3. 인시던트 재매핑 (있는 경우)
    4. IFC 재생성 (output_dir 지정 시)
    5. 보정 세션 저장

    Args:
        payload: geometry payload (이미 operations로 변이된 상태)
        session: 적용된 CorrectionSession
        output_dir: 출력 디렉토리 (None이면 IFC 재생성 건너뜀)
        rebuild_ifc: IFC 재생성 여부

    Returns:
        재빌드된 payload
    """
    # 1. 보정 메타데이터 기록
    payload["refined"] = True
    payload["correction_applied"] = True
    payload["last_correction_session"] = session.session_id
    payload["correction_source"] = session.correction_source

    # processing 메타데이터 업데이트
    processing = payload.get("processing", {})
    processing["stage"] = "post_correction"
    corrections_meta = processing.get("corrections", [])
    corrections_meta.append({
        "session_id": session.session_id,
        "patch_count": session.patch_count,
        "correction_source": session.correction_source,
        "operation_summary": session.operation_summary,
    })
    processing["corrections"] = corrections_meta
    payload["processing"] = processing

    # 2. counts 재계산
    payload["rooms_count"] = len(payload.get("rooms", []))
    payload["walls_count"] = len(payload.get("walls", []))

    # 3. 인시던트 재매핑 (Phase 5 연동)
    incident = payload.get("incident", {})
    if incident and incident.get("leak_sources"):
        try:
            from scene.incident_mapper import _find_room_for_point
            rooms = payload.get("rooms", [])

            for src in incident.get("leak_sources", []):
                pt = src.get("point", {})
                if pt:
                    auto_room = _find_room_for_point(
                        float(pt.get("x", 0)), float(pt.get("y", 0)), rooms
                    )
                    src["room_id"] = auto_room
                    src["auto_mapped"] = True
        except ImportError:
            pass  # scene 모듈이 없으면 건너뜀

    # 4. 세션 상태 갱신
    session.apply()

    # 5. IFC 재생성 + 파일 저장 (output_dir 지정 시)
    if output_dir and rebuild_ifc:
        os.makedirs(output_dir, exist_ok=True)

        # geometry payload 저장
        rooms_json_path = os.path.join(output_dir, "page0_rooms.json")
        with open(rooms_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # IFC 재생성
        try:
            from parser.export_ifc import build_ifc_from_meta
            ifc_path = os.path.join(output_dir, "page0_result.ifc")
            build_ifc_from_meta(
                payload, out_ifc=ifc_path, out_meta=ifc_path + ".meta.json"
            )
            payload["_rebuilt_ifc"] = ifc_path
        except Exception as e:
            payload["_rebuild_error"] = str(e)

        # 보정 세션 저장
        from correction.history import save_session
        save_session(session, output_dir)

    return payload
