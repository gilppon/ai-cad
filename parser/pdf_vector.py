# -*- coding: utf-8 -*-
"""
pdf_vector.py - Vector PDF Geometry Extractor
Extracts drawing commands (lines, rects) from PDF using PyMuPDF (fitz)
and converts them into domain Wall models.
"""
import fitz
from typing import List, Dict, Any
from domain.models import Point, Wall
from pipeline.contracts import validate_geometry_payload

def extract_vector_geometry(pdf_path: str, page_index: int = 0) -> Dict[str, Any]:
    """
    Extracts vector-based wall geometry from a PDF page.
    
    Returns:
        A dict matching the GeometryPayload contract.
    """
    doc = fitz.open(pdf_path)
    if page_index >= len(doc):
        raise ValueError(f"Page index {page_index} out of range")
        
    page = doc[page_index]
    width, height = page.rect.width, page.rect.height
    
    # get_drawings returns a list of paths
    paths = page.get_drawings()
    
    walls: List[Wall] = []
    wall_id_counter = 0
    
    for path in paths:
        # Each path can have multiple items (lines, rects, etc.)
        items = path.get("items", [])
        stroke_width = path.get("width", 1.0)
        
        # Simple filtering: skip very thick lines (might be fills or headers)
        # and skip very thin lines (might be grid or hatches)
        if stroke_width > 5.0 or stroke_width < 0.1:
            continue
            
        for item in items:
            type = item[0]
            if type == "l":  # Line
                p1_raw, p2_raw = item[1], item[2]
                wall = Wall(
                    id=wall_id_counter,
                    p1=Point(x=float(p1_raw.x), y=float(p1_raw.y)),
                    p2=Point(x=float(p2_raw.x), y=float(p2_raw.y)),
                    thickness_px=stroke_width,
                    kind="VECTOR_LINE"
                )
                walls.append(wall)
                wall_id_counter += 1
            elif type == "re":  # Rectangle
                # Rect is (x0, y0, x1, y1)
                rect = item[1]
                # We could treat small rects as columns, or convert to lines.
                # For now, let's skip or take the longest edges if it's wall-like.
                pass

    # Build the payload
    payload = {
        "kind": "geometry_payload",
        "canvas": {"width": width, "height": height},
        "rooms": [],  # Vector extraction usually doesn't give rooms directly without further logic
        "walls": [
            {
                "id": w.id,
                "p1": {"x": w.p1.x, "y": w.p1.y},
                "p2": {"x": w.p2.x, "y": w.p2.y},
                "thickness_px": w.thickness_px,
                "kind": w.kind
            } for w in walls
        ],
        "rooms_count": 0,
        "walls_count": len(walls),
        "metadata": {
            "source": "vector_extractor",
            "page_index": page_index,
            "paths_processed": len(paths)
        }
    }
    
    # Validate against contract
    validate_geometry_payload(payload)
    
    return payload

if __name__ == "__main__":
    # Test stub
    import sys
    if len(sys.argv) > 1:
        res = extract_vector_geometry(sys.argv[1])
        print(f"Extracted {res['walls_count']} walls from vector PDF.")
