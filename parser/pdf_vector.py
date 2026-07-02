# -*- coding: utf-8 -*-
"""
pdf_vector.py - Vector PDF Geometry Extractor
Extracts drawing commands (lines, rects) from PDF using PyMuPDF (fitz)
and converts them into domain Wall models.
"""
import fitz
from typing import List, Dict, Any
from domain.models import Point, Wall
from pipeline.contracts import validate_geometry_payload, build_geometry_payload, build_processing_metadata
from parser.line_refine import Line, refine_lines, merge_collinear_segments, snap_endpoints, merge_parallel_pairs, filter_structural_walls
from parser.room_detect import detect_rooms_from_walls
from parser.room_export import rooms_to_json_dict

def extract_vector_geometry(pdf_path: str, page_index: int = 0) -> Dict[str, Any]:
    """
    Extracts vector-based wall geometry from a PDF page and refines it.
    
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
    
    raw_segments: List[tuple] = []
    
    for path in paths:
        items = path.get("items", [])
        stroke_width = path.get("width", 1.0)
        
        # Filtering: skip very thick lines or very thin lines (hatches/grid)
        if stroke_width > 10.0 or stroke_width < 0.05:
            continue
            
        for item in items:
            itype = item[0]
            if itype == "l":  # Line
                p1, p2 = item[1], item[2]
                raw_segments.append((p1.x, p1.y, p2.x, p2.y))
            elif itype == "re":  # Rectangle
                rect = item[1]
                # Convert rect to 4 lines
                x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
                # Only add if it's not a tiny point-like rect
                if abs(x1 - x0) > 0.1 or abs(y1 - y0) > 0.1:
                    raw_segments.append((x0, y0, x1, y0)) # Top
                    raw_segments.append((x1, y0, x1, y1)) # Right
                    raw_segments.append((x1, y1, x0, y1)) # Bottom
                    raw_segments.append((x0, y1, x0, y0)) # Left

    # --- Refinement Pipeline ---
    # 1. Basic refinement (snap to axis, structural min_len filter)
    # Increased to 25.0 to filter out tiny details (text, dimensions, symbols, grid, hatches)
    refined = refine_lines(raw_segments, min_len=25.0)
    
    # 2. Merge collinear (combine broken segments)
    refined = merge_collinear_segments(refined, dist_tol=2.0, gap_tol=10.0)
    
    # 3. Snap endpoints (ensure connectivity)
    refined = snap_endpoints(refined, snap_dist=8.0)
    
    # 4. Merge parallel pairs (cleanup overlaps)
    refined = merge_parallel_pairs(refined, dist_tol=4.0)

    # 5. Filter structural walls (eliminate isolated decorative lines/grid segments)
    refined = filter_structural_walls(refined, min_len_ratio=0.01, min_degree=1, join_tol=15)


    walls: List[Wall] = []
    for i, l in enumerate(refined):
        walls.append(Wall(
            id=i,
            p1=Point(x=float(l.x1), y=float(l.y1)),
            p2=Point(x=float(l.x2), y=float(l.y2)),
            thickness_px=1.0, # Default for vector if not tracked per segment
            kind="VECTOR_WALL"
        ))
    
    wall_dicts = [
        {
            "id": w.id,
            "p1": {"x": w.p1.x, "y": w.p1.y},
            "p2": {"x": w.p2.x, "y": w.p2.y},
            "thickness_px": w.thickness_px,
            "kind": w.kind
        } for w in walls
    ]
    
    # --- Room Detection (Added in Reinforcement Phase) ---
    # Convert refined lines to the format expected by detector
    walls_lines = [
        {"x1": int(l.x1), "y1": int(l.y1), "x2": int(l.x2), "y2": int(l.y2)}
        for l in refined
    ]
    
    room_result = detect_rooms_from_walls(int(width), int(height), walls_lines)
    
    source_info = {
        "source": "vector_extractor_v2_refined",
        "page_index": page_index,
        "raw_paths": len(paths),
        "raw_segments": len(raw_segments),
        "refined_walls": len(walls)
    }

    # Convert rooms to payload using standard exporter
    # Note: rooms_to_json_dict returns a full GeometryPayload
    payload = rooms_to_json_dict(
        room_result,
        page=page_index,
        source=source_info
    )
    
    # Add back the refined wall dictionaries to the payload
    payload["walls"] = wall_dicts
    payload["walls_count"] = len(wall_dicts)
    payload["processing"] = build_processing_metadata("vector_extraction_with_rooms")
    
    validate_geometry_payload(payload)
    return payload

if __name__ == "__main__":
    # Test stub
    import sys
    if len(sys.argv) > 1:
        res = extract_vector_geometry(sys.argv[1])
        print(f"Extracted {res['walls_count']} walls from vector PDF.")
