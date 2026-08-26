import json
import logging
import math
import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# SP4/H-5: 레거시 폴백 스케일의 단일 정의는 core.units로 수렴 (재발 방지)
from core.units import DEFAULT_PX_TO_M


def resolve_px_to_m(rooms_payload: Dict[str, Any]) -> float:
    """
    페이로드에 기록된 파이프라인 스케일을 단일 진실원(SSOT)으로 해석한다. (SP1/L-1)

    우선순위:
      1. payload["scale"]["pixel_to_mm"]  (래스터 경로: save_rooms_json이 기록)
      2. payload["metadata"]["px_to_m"]   (명시적 메타데이터)
      3. DEFAULT_PX_TO_M (스케일 정보 부재 시 레거시 폴백 + 경고)

    법규 판정(채광 1/7 등)은 이 값의 제곱에 비례하므로, 파이프라인과
    컴플라이언스 계층의 스케일 불일치는 판정 오류로 직결된다.
    """
    scale = rooms_payload.get("scale") or {}
    pixel_to_mm = scale.get("pixel_to_mm")
    if pixel_to_mm:
        try:
            return float(pixel_to_mm) / 1000.0
        except (TypeError, ValueError):
            logger.warning(f"[Scale] Invalid scale.pixel_to_mm={pixel_to_mm!r}, falling back.")

    metadata = rooms_payload.get("metadata") or {}
    explicit_px_to_m = metadata.get("px_to_m")
    if explicit_px_to_m:
        try:
            return float(explicit_px_to_m)
        except (TypeError, ValueError):
            logger.warning(f"[Scale] Invalid metadata.px_to_m={explicit_px_to_m!r}, falling back.")

    logger.warning(
        "[Scale] No scale info in payload - using legacy default %.4f m/px. "
        "Legal area verdicts may be inaccurate.", DEFAULT_PX_TO_M
    )
    return DEFAULT_PX_TO_M

def apply_scale_factor(rooms_data: Dict[str, Any], px_to_m: float = DEFAULT_PX_TO_M) -> Dict[str, Any]:
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
    # 1. Apply scale - 파이프라인이 기록한 스케일을 그대로 수용 (SP1/L-1, 하드코딩 금지)
    px_to_m = resolve_px_to_m(rooms_payload)
    scaled_payload = apply_scale_factor(rooms_payload, px_to_m=px_to_m)
    
    # 2. Extract Openings
    openings = extract_openings(rooms_payload, output_dir, page_index)
    scaled_payload["openings"] = openings
    
    # Calculate global metrics
    total_area_m2 = sum(r.get("area_m2", 0.0) for r in scaled_payload.get("rooms", []))
    
    compliance_doc = {
        "page_index": page_index,
        "metrics": {
            "total_area_m2": total_area_m2,
            "px_to_m_scale": px_to_m
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
