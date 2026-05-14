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
