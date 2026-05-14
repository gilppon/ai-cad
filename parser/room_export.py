from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from domain.models import Point, Room, RoomKind
from pipeline.contracts import build_geometry_payload, build_processing_metadata
from pipeline.paths import resolve_output_path, resolve_project_path


def run_freecad_step(rooms_json_path: str, out_step_path: str) -> None:
    """
    Runs an external FreeCAD script to convert room geometry to STEP.
    """
    freecadcmd = r"C:\Program Files\FreeCAD 1.0\bin\Freecadcmd.exe"
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "exporter", "freecad_rooms_to_step.py"))
    rooms_json = resolve_project_path(rooms_json_path)
    out_step = resolve_output_path(out_step_path)

    if not os.path.exists(freecadcmd):
        print(f"[Warning] FreeCAD not found at {freecadcmd}. Skipping STEP export.")
        return

    env = os.environ.copy()
    env["ROOMS_JSON"] = str(rooms_json)
    env["OUT_STEP"] = str(out_step)

    try:
        subprocess.run([freecadcmd, script], check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"[Error] FreeCAD export failed: {e}")
        raise


def _poly_area(poly: List[Point]) -> float:
    """
    Shoelace formula for Point list.
    """
    if not poly or len(poly) < 3:
        return 0.0
    s = 0.0
    n = len(poly)
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        s += (p1.x * p2.y - p2.x * p1.y)
    return abs(s) / 2.0


def _bbox_from_poly(poly: List[Point]) -> Dict[str, int]:
    if not poly:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    xs = [p.x for p in poly]
    ys = [p.y for p in poly]
    x0, y0 = min(xs), min(ys)
    x1, y1 = max(xs), max(ys)
    return {"x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)}


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def rooms_to_json_dict(
    room_result: Any,
    *,
    page: int = 0,
    pixel_to_mm: Optional[float] = None,
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Converts detector results into the standardized GeometryPayload.
    """
    w = int(getattr(room_result, "width", 0))
    h = int(getattr(room_result, "height", 0))
    rooms_data = getattr(room_result, "rooms", []) or []
    walls_data = getattr(room_result, "walls", []) or []
    debug = getattr(room_result, "debug", {}) or {}

    out_rooms: List[Dict[str, Any]] = []
    
    for r in rooms_data:
        kind_str = str(getattr(r, "kind", "UNKNOWN")).upper()
        try:
            # Handle potential lowercase or mixed case from detector
            if kind_str not in RoomKind.__members__:
                kind = RoomKind.UNKNOWN
            else:
                kind = RoomKind[kind_str]
        except (KeyError, ValueError):
            kind = RoomKind.UNKNOWN

        rid = int(getattr(r, "id", -1))
        contour = getattr(r, "contour", []) or []
        
        # Convert to domain Points
        poly_points = [Point(x=float(p[0]), y=float(p[1])) for p in contour]
        
        # Room classification fallback
        if kind == RoomKind.UNKNOWN:
            from .room_semantics import classify_room
            # convert poly_points to dict list for classify_room
            poly_dicts = [{"x": p.x, "y": p.y} for p in poly_points]
            kind = classify_room(poly_dicts, pixel_to_mm or 5.0)
        
        area_px = _safe_float(getattr(r, "area_px", _poly_area(poly_points)))
        
        # Create domain Room instance
        room_obj = Room(
            id=rid,
            polygon=poly_points,
            kind=kind,
            area_px2=area_px
        )
        
        if pixel_to_mm is not None and pixel_to_mm > 0:
            area_mm2 = area_px * (pixel_to_mm ** 2)
            room_obj.area_m2 = area_mm2 / 1_000_000.0
            
        # Convert to dict for JSON payload
        room_dict = asdict(room_obj)
        # Ensure kind is string value in dict
        room_dict["kind"] = room_obj.kind.value
        # Add bbox for legacy/UI support if needed
        room_dict["bbox"] = _bbox_from_poly(poly_points)
        
        out_rooms.append(room_dict)

    scale = None
    if pixel_to_mm is not None and pixel_to_mm > 0:
        scale = {"pixel_to_mm": float(pixel_to_mm)}

    processing = build_processing_metadata("room_export")

    out_walls: List[Dict[str, Any]] = []
    for wall_obj in walls_data:
        out_walls.append({
            "id": getattr(wall_obj, "id", 0),
            "p1": {"x": float(wall_obj.p1[0]), "y": float(wall_obj.p1[1])},
            "p2": {"x": float(wall_obj.p2[0]), "y": float(wall_obj.p2[1])},
        })

    return build_geometry_payload(
        page=page,
        canvas={"width": w, "height": h},
        rooms=out_rooms,
        walls=out_walls,
        debug_files=debug,
        scale=scale,
        source=source,
        processing=processing,
    )


def save_rooms_json(
    room_result: Any,
    out_json_path: str,
    *,
    page: int = 0,
    pixel_to_mm: Optional[float] = None,
    source: Optional[Dict[str, Any]] = None,
    refinement_context: Optional[Dict[str, Any]] = None,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> str:
    """
    Saves the room geometry to a JSON file, applying refinement if available.
    """
    payload = rooms_to_json_dict(
        room_result,
        page=page,
        pixel_to_mm=pixel_to_mm,
        source=source,
    )

    # Apply detect_and_refine_rooms if pipeline exists
    try:
        from .rooms_pipeline import detect_and_refine_rooms
        before = len(payload.get("rooms", []))
        payload = detect_and_refine_rooms(payload, refinement_context=refinement_context)
        after = len(payload.get("rooms", []))
        print(f"[Refine] Rooms: {before} -> {after} (refined={payload.get('refined', False)})")
    except ImportError:
        print("[Refine] rooms_pipeline not found, skipping refinement.")
    except Exception as e:
        print(f"[Refine] Error during refinement: {e}")

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=indent, ensure_ascii=ensure_ascii)
    
    return out_json_path
