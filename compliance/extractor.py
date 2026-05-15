import json
import math
import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List

def apply_scale_factor(rooms_data: Dict[str, Any], px_to_m: float = 0.01) -> Dict[str, Any]:
    """
    Applies the scale factor to geometric properties.
    px_to_m = 0.01 means 100 pixels = 1 meter.
    """
    scaled_data = dict(rooms_data)
    scaled_data["px_to_m"] = px_to_m
    
    rooms = scaled_data.get("rooms", [])
    for r in rooms:
        # area_px2 to area_m2
        area_px2 = r.get("area_px2", 0.0)
        r["area_m2"] = area_px2 * (px_to_m ** 2)
        
        # default height if not present
        if "height_mm" not in r:
            r["height_mm"] = 2400.0
            
    return scaled_data

def extract_openings(rooms_data: Dict[str, Any], output_dir: str, page_index: int = 0) -> List[Dict[str, Any]]:
    """
    Extracts explicit Opening (Door/Window) objects from the CV pipeline artifacts.
    """
    door_mask_path = os.path.join(output_dir, f"door_mask_page{page_index}.png")
    contours_path = os.path.join(output_dir, f"contours_page{page_index}.json")
    
    openings = []
    
    if not os.path.exists(door_mask_path) or not os.path.exists(contours_path):
        return openings
        
    door_mask = cv2.imread(door_mask_path, cv2.IMREAD_GRAYSCALE)
    if door_mask is None:
        return openings
        
    H, W = door_mask.shape
        
    with open(contours_path, "r", encoding="utf-8") as f:
        contours_data = json.load(f)
        
    outer = max(contours_data["contours"], key=lambda c: float(c.get("area", 0.0)))
    pts = outer["points"]
    poly = np.array([[int(x), int(y)] for x, y in pts], dtype=np.int32).reshape(-1, 1, 2)
    
    shell_bmask = np.zeros((H, W), dtype=np.uint8)
    cv2.polylines(shell_bmask, [poly], True, 255, 15, cv2.LINE_AA) # Thick boundary for intersection
    
    num, lab, stats, centroids = cv2.connectedComponentsWithStats(door_mask, connectivity=8)
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        cx, cy = centroids[i]
        
        # Create a mask for this single component
        comp_mask = np.zeros((H, W), dtype=np.uint8)
        comp_mask[lab == i] = 255
        
        # Dilate slightly to ensure it touches the shell if it's near
        comp_mask_dilated = cv2.dilate(comp_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11)), iterations=1)
        
        intersection = cv2.bitwise_and(comp_mask_dilated, shell_bmask)
        kind = "WINDOW" if cv2.countNonZero(intersection) > 0 else "DOOR"
        
        # Simplified Line mapping: just use the bounding box center/width
        openings.append({
            "id": i,
            "kind": kind,
            "width_px": max(w, h),
            "p1": {"x": int(cx - w/2), "y": int(cy - h/2)},
            "p2": {"x": int(cx + w/2), "y": int(cy + h/2)},
            "connected_rooms": [] # To be resolved later if needed
        })
        
    return openings

def extract_compliance_data(rooms_payload: Dict[str, Any], output_dir: str, page_index: int = 0) -> Dict[str, Any]:
    """
    Main entry point for Stage 2 data extraction.
    Takes the pure geometry payload and produces a structured compliance JSON.
    """
    # 1. Apply scale
    # Currently default to 100px = 1m (0.01)
    scaled_payload = apply_scale_factor(rooms_payload, px_to_m=0.01)
    
    # 2. Extract Openings
    openings = extract_openings(rooms_payload, output_dir, page_index)
    scaled_payload["openings"] = openings
    
    # Calculate global metrics
    total_area_m2 = sum(r.get("area_m2", 0.0) for r in scaled_payload.get("rooms", []))
    
    compliance_doc = {
        "page_index": page_index,
        "metrics": {
            "total_area_m2": total_area_m2,
            "px_to_m_scale": 0.01
        },
        "rooms": scaled_payload.get("rooms", []),
        "openings": openings,
        "walls": scaled_payload.get("walls", [])
    }
    
    # Save compliance JSON
    comp_path = os.path.join(output_dir, f"page{page_index}_compliance.json")
    with open(comp_path, "w", encoding="utf-8") as f:
        json.dump(compliance_doc, f, indent=2, ensure_ascii=False)
        
    return compliance_doc

if __name__ == "__main__":
    # Test script usage
    pass
