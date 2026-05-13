from typing import List, Dict, Any, Tuple
import numpy as np

# In a real scenario, we would use a dataclass or import from room_detect
# For decoupling, we'll use a generic approach or assume a certain interface.

def classify_rooms(rooms: List[Any], width: int, height: int) -> None:
    """
    Classify rooms into LDK, ROOM, WET, CORRIDOR, ENTRANCE based on geometry.
    """
    if not rooms:
        return

    total_area = float(width * height)
    img_center = (width / 2.0, height / 2.0)
    img_diag = (width * width + height * height) ** 0.5

    # 1. Sort by area
    rooms_sorted = sorted(rooms, key=lambda r: r.area_px, reverse=True)
    
    # 2. Largest is likely LDK (Living, Dining, Kitchen)
    ldk = rooms_sorted[0]
    ldk.kind = "LDK"

    for r in rooms_sorted[1:]:
        x, y, w, h = r.bbox
        area_ratio = r.area_px / total_area
        aspect_ratio = max(w/h, h/w) if h > 0 and w > 0 else 1.0
        
        # Distance from center (normalized 0.0 to 1.0)
        cx, cy = x + w/2.0, y + h/2.0
        center_dist = ((cx - img_center[0])**2 + (cy - img_center[1])**2)**0.5 / img_diag
        
        # Heuristics for Japanese Floor Plans
        kind = "ROOM"
        
        # Corridor: Very long and narrow
        if aspect_ratio > 4.5 and area_ratio < 0.15:
            kind = "CORRIDOR"
        elif area_ratio < 0.05 and center_dist > 0.2:
            # Wet Area (Bath/Toilet) or Storage
            if area_ratio < 0.015:
                kind = "STORAGE"
            else:
                kind = "WET"
        else:
            # Entrance: Small area touching the outer boundary
            touches_border = (x <= 5 or y <= 5 or (x+w) >= width-5 or (y+h) >= height-5)
            if touches_border and area_ratio < 0.03:
                kind = "ENTRANCE"
        
        r.kind = kind
        print(f"  [Semantics] Room {r.id}: Area={r.area_px:.1f}, AR={aspect_ratio:.2f}, CenterDist={center_dist:.2f} -> {r.kind}")

def get_room_summary(rooms: List[Any]) -> Dict[str, int]:
    summary = {}
    for r in rooms:
        summary[r.kind] = summary.get(r.kind, 0) + 1
    return summary
