import re
from typing import List, Dict, Any, Optional
import fitz

def extract_text_from_page(pdf_page: fitz.Page) -> List[Dict[str, Any]]:
    """
    Extracts text blocks with their positions.
    """
    blocks = pdf_page.get_text("blocks")
    results = []
    for b in blocks:
        # b: (x0, y0, x1, y1, "text", block_no, block_type)
        results.append({
            "bbox": (b[0], b[1], b[2], b[3]),
            "text": b[4].strip(),
            "type": b[6]
        })
    return results

def find_room_height(text_blocks: List[Dict[str, Any]], room_poly: List[Dict[str, float]], scale: float = 1.0) -> Optional[float]:
    """
    Heuristically finds room height (CH) from text blocks inside or near the room.
    'scale' is used to convert text coordinates to match room_poly coordinates.
    """
    # regex for CH=2400, H=2.5m, etc.
    ch_pattern = re.compile(r"(?:CH|H)\s*[=:]\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
    
    # Calculate room bbox for fast filtering
    xs = [p["x"] for p in room_poly]
    ys = [p["y"] for p in room_poly]
    rx0, ry0, rx1, ry1 = min(xs), min(ys), max(xs), max(ys)
    
    for block in text_blocks:
        match = ch_pattern.search(block["text"])
        if match:
            bx0, by0, bx1, by1 = block["bbox"]
            # Scale coordinates
            bx0, by0, bx1, by1 = bx0 * scale, by0 * scale, bx1 * scale, by1 * scale
            
            # Center of text block
            bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
            
            # Check if center is inside room bbox first
            if rx0 <= bcx <= rx1 and ry0 <= bcy <= ry1:
                # Point in polygon check
                if _is_point_in_poly(bcx, bcy, room_poly):
                    val = float(match.group(1))
                    # Handle units (mm vs m)
                    if val < 10: # assume meters
                        return val * 1000.0
                    return val
    return None

def _is_point_in_poly(x: float, y: float, poly: List[Dict[str, float]]) -> bool:
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]["x"], poly[0]["y"]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]["x"], poly[i % n]["y"]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside
