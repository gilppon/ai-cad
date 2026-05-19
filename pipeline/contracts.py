from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = "0.1.0"


class ContractValidationError(ValueError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_processing_metadata(
    stage: str,
    *,
    warnings: Optional[Iterable[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "stage": str(stage),
        "generated_at": utc_now_iso(),
        "warnings": list(warnings or []),
    }
    if extra:
        metadata["extra"] = dict(extra)
    return metadata


def build_geometry_payload(
    *,
    page: int,
    canvas: Dict[str, int],
    rooms: List[Dict[str, Any]],
    walls: Optional[List[Dict[str, Any]]] = None,
    debug_files: Optional[Dict[str, Any]] = None,
    scale: Optional[Dict[str, Any]] = None,
    source: Optional[Dict[str, Any]] = None,
    incident: Optional[Dict[str, Any]] = None,
    processing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "geometry_payload",
        "page": int(page),
        "page_index": int(page),
        "canvas": {
            "width": int(canvas.get("width", 0)),
            "height": int(canvas.get("height", 0)),
        },
        "rooms": list(rooms),
        "rooms_count": len(rooms),
        "walls": list(walls or []),
        "walls_count": len(walls or []),
        "debug_files": dict(debug_files or {}),
        "processing": dict(processing or build_processing_metadata("room_export")),
        "incident": dict(incident or {}),
    }
    if scale:
        payload["scale"] = dict(scale)
    if source:
        payload["source"] = dict(source)
    return payload


def build_export_metadata(
    *,
    page_index: int,
    rooms: List[Dict[str, Any]],
    walls: List[Dict[str, Any]],
    doors: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    params: Dict[str, Any],
    source: Optional[Dict[str, Any]] = None,
    incident: Optional[Dict[str, Any]] = None,
    processing: Optional[Dict[str, Any]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "scene_export_metadata",
        "page_index": int(page_index),
        "rooms": list(rooms),
        "walls": list(walls),
        "doors": list(doors),
        "edges": list(edges),
        "params": dict(params),
        "processing": dict(processing or build_processing_metadata("export_step")),
        "incident": dict(incident or {}),
        "artifacts": dict(artifacts or {}),
    }
    if source:
        metadata["source"] = dict(source)
    return metadata


def validate_geometry_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("Geometry payload must be a dictionary.")
    if payload.get("kind") != "geometry_payload":
        raise ContractValidationError("Geometry payload kind must be 'geometry_payload'.")
    canvas = payload.get("canvas")
    if not isinstance(canvas, dict):
        raise ContractValidationError("Geometry payload canvas must be a dictionary.")
    if "width" not in canvas or "height" not in canvas:
        raise ContractValidationError("Geometry payload canvas must contain width and height.")
    rooms = payload.get("rooms")
    if not isinstance(rooms, list):
        raise ContractValidationError("Geometry payload rooms must be a list.")


def validate_export_metadata(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("Export metadata must be a dictionary.")
    if payload.get("kind") != "scene_export_metadata":
        raise ContractValidationError("Export metadata kind must be 'scene_export_metadata'.")
    for field_name in ("rooms", "walls", "doors", "edges"):
        if not isinstance(payload.get(field_name), list):
            raise ContractValidationError(f"Export metadata field '{field_name}' must be a list.")
    params = payload.get("params")
    if not isinstance(params, dict):
        raise ContractValidationError("Export metadata params must be a dictionary.")


def validate_incident_payload(incident: Dict[str, Any]) -> None:
    """
    incident 서브 페이로드의 구조 유효성 검증.
    빈 dict는 허용 (인시던트 미첨부 상태).
    """
    if not isinstance(incident, dict):
        raise ContractValidationError("Incident payload must be a dictionary.")

    if not incident:
        return  # 빈 인시던트는 합법

    # case_id 필수
    if "case_id" not in incident:
        raise ContractValidationError("Incident payload must contain 'case_id'.")

    # leak_sources 구조 검증
    sources = incident.get("leak_sources", [])
    if not isinstance(sources, list):
        raise ContractValidationError("Incident leak_sources must be a list.")
    for i, src in enumerate(sources):
        if not isinstance(src, dict):
            raise ContractValidationError(f"leak_sources[{i}] must be a dict.")
        if "point" not in src:
            raise ContractValidationError(f"leak_sources[{i}] must have 'point'.")

    # damage_zones 구조 검증
    zones = incident.get("damage_zones", [])
    if not isinstance(zones, list):
        raise ContractValidationError("Incident damage_zones must be a list.")
    for i, dz in enumerate(zones):
        if not isinstance(dz, dict):
            raise ContractValidationError(f"damage_zones[{i}] must be a dict.")
        for req_field in ("id", "damage_type", "severity"):
            if req_field not in dz:
                raise ContractValidationError(f"damage_zones[{i}] missing '{req_field}'.")

    # suspected_paths 구조 검증
    paths = incident.get("suspected_paths", [])
    if not isinstance(paths, list):
        raise ContractValidationError("Incident suspected_paths must be a list.")

    # annotations 구조 검증
    annotations = incident.get("annotations", [])
    if not isinstance(annotations, list):
        raise ContractValidationError("Incident annotations must be a list.")

