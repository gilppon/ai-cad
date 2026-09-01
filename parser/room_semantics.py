# room_semantics.py
import math
from core.units import RASTER_PIXEL_TO_MM
from typing import List, Dict, Any
from domain.models import RoomKind

def classify_room(poly: List[Dict[str, float]], pixel_to_mm: float) -> RoomKind:
    """
    Classifies a room based on its geometric properties.
    """
    if not poly:
        return RoomKind.UNKNOWN

    # Calculate area using shoelace formula
    area_px2 = 0.0
    for i in range(len(poly)):
        p1 = poly[i]
        p2 = poly[(i + 1) % len(poly)]
        area_px2 += (p1["x"] * p2["y"] - p2["x"] * p1["y"])
    area_px2 = abs(area_px2) / 2.0
    
    area_mm2 = area_px2 * (pixel_to_mm ** 2)
    area_m2 = area_mm2 / 1_000_000.0

    # Calculate Bounding Box
    xs = [p["x"] for p in poly]
    ys = [p["y"] for p in poly]
    w_px = max(xs) - min(xs)
    h_px = max(ys) - min(ys)
    aspect_ratio = max(w_px, h_px) / min(w_px, h_px) if min(w_px, h_px) > 0 else 1.0

    # Heuristics (Very basic for MVP)
    if area_m2 < 2.5:
        # Small rooms: Toilet, Closet, or Entrance
        return RoomKind.TOILET
    elif area_m2 < 6.0:
        if aspect_ratio > 3.0:
            return RoomKind.CLOSET # Likely a corridor or narrow storage
        return RoomKind.BATHROOM
    elif area_m2 < 15.0:
        return RoomKind.BEDROOM
    elif area_m2 >= 15.0:
        return RoomKind.LDK # Living, Dining, Kitchen
    
    return RoomKind.LIVING

def classify_rooms(rooms: List[Any], width: int, height: int, pixel_to_mm: float = RASTER_PIXEL_TO_MM) -> None:
    """
    Batch classification of rooms. Updates the 'kind' attribute of each room object.
    """
    for r in rooms:
        # contour is List[Tuple[int, int]]
        contour = getattr(r, "contour", [])
        poly_dicts = [{"x": float(p[0]), "y": float(p[1])} for p in contour]
        kind = classify_room(poly_dicts, pixel_to_mm)
        r.kind = kind.value
