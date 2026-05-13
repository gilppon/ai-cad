from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


# -----------------------------
# Data structures
# -----------------------------
@dataclass
class Room:
    id: int
    contour: List[Tuple[int, int]]  # polygon points
    area_px: float
    bbox: Tuple[int, int, int, int]  # x,y,w,h
    kind: str = "ROOM"  # "LDK" | "ROOM" | "WET" | "OTHER"


@dataclass
class RoomResult:
    width: int
    height: int
    rooms: List[Room]
    debug: Dict[str, str]


# -----------------------------
# Drawing / helpers
# -----------------------------
def _draw_thick_lines(mask: np.ndarray, walls_lines: List[Dict[str, int]], thickness: int) -> None:
    for l in walls_lines:
        x1, y1, x2, y2 = int(l["x1"]), int(l["y1"]), int(l["x2"]), int(l["y2"])
        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness, lineType=cv2.LINE_8)


def _simplify_contour(cnt: np.ndarray, mode: str, epsilon_ratio: float) -> np.ndarray:
    mode = (mode or "none").lower()
    if mode == "hull":
        return cv2.convexHull(cnt)
    if mode == "approx":
        peri = cv2.arcLength(cnt, True)
        eps = max(1.0, peri * float(epsilon_ratio))
        return cv2.approxPolyDP(cnt, eps, True)
    return cnt


def simplify_without_long_edges(
    cnt: np.ndarray,
    bbox: Tuple[int, int, int, int],
    eps_ratio: float = 0.006,
    max_edge_ratio: float = 0.35,
) -> np.ndarray:
    """
    approxPolyDP 후, 너무 긴 대각선 edge(쇼트컷)가 생기면 원본 contour로 fallback.
    """
    peri = cv2.arcLength(cnt, True)
    eps = max(1.0, peri * eps_ratio)
    approx = cv2.approxPolyDP(cnt, eps, True)

    x, y, w, h = bbox
    max_edge_len = ((w * w + h * h) ** 0.5) * float(max_edge_ratio)

    n = len(approx)
    if n < 3:
        return cnt

    for i in range(n):
        p1 = approx[i][0]
        p2 = approx[(i + 1) % n][0]
        edge_len = ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5
        if edge_len > max_edge_len:
            return cnt  # 대각선 쇼트컷 방지

    return approx


def _bbox_center(b: Tuple[int, int, int, int]) -> Tuple[float, float]:
    x, y, w, h = b
    return (x + w / 2.0, y + h / 2.0)


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _room_type_classify(
    rooms: List[Room],
    width: int,
    height: int,
    cfg: Dict[str, Any],
) -> None:
    """
    JP 최소 룰 기반 분류 (텍스트/OCR 없이 geometry로만):
      - 가장 큰 room 1개 => LDK
      - 작고(면적), 중앙에서 멀고(외곽), 종횡비가 크지 않은 것들 중 일부 => WET 후보
      - 나머지 => ROOM
    """
    if not rooms:
        return

    # cfg thresholds
    wet_area_ratio_max = float(cfg.get("jp_wet_area_ratio_max", 0.08))   # 전체의 8% 이하면 WET 후보
    wet_center_dist_ratio_min = float(cfg.get("jp_wet_center_dist_ratio_min", 0.22))  # 화면 중심에서 멀면 WET 가산점
    wet_aspect_ratio_max = float(cfg.get("jp_wet_aspect_ratio_max", 3.5))  # 너무 길쭉하면 복도일 가능성

    total = float(width * height)
    img_center = (width / 2.0, height / 2.0)
    img_diag = (width * width + height * height) ** 0.5

    # 1) 가장 큰 room을 LDK로
    rooms_sorted = sorted(rooms, key=lambda r: r.area_px, reverse=True)
    ldk = rooms_sorted[0]
    ldk.kind = "LDK"

    # 2) 나머지 분류
    for r in rooms_sorted[1:]:
        x, y, w, h = r.bbox
        area_ratio = float(r.area_px) / total

        # bbox 기반 feature
        ar = max(w / max(1, h), h / max(1, w))
        c = _bbox_center(r.bbox)
        center_dist = _dist(c, img_center) / max(1.0, img_diag)

        # WET scoring (아주 단순)
        wet_score = 0.0
        if area_ratio <= wet_area_ratio_max:
            wet_score += 1.0
        if center_dist >= wet_center_dist_ratio_min:
            wet_score += 0.7
        if ar <= wet_aspect_ratio_max:
            wet_score += 0.3

        # 결과
        if wet_score >= 1.4:
            r.kind = "WET"
        else:
            r.kind = "ROOM"


# -----------------------------
# Main
# -----------------------------
def detect_rooms_from_walls(
    width: int,
    height: int,
    walls_lines: List[Dict[str, int]],
    cfg: Optional[Dict[str, Any]] = None,
) -> RoomResult:
    cfg = cfg or {}

    # ---- Defaults / knobs ----
    wall_thickness = int(cfg.get("wall_thickness", 8))
    close_kernel = int(cfg.get("close_kernel", 5))
    close_iter = int(cfg.get("close_iter", 1))
    open_kernel = int(cfg.get("open_kernel", 5))

    min_room_area_px = int(cfg.get("min_room_area_px", int(width * height * 0.0015)))
    max_room_area_ratio = float(cfg.get("max_room_area_ratio", 0.40))

    debug_out_dir = cfg.get("debug_out_dir", None)
    prefix = str(cfg.get("prefix", "page0"))

    # JP rules (LDK keep)
    jp_keep_largest_inside = bool(cfg.get("jp_keep_largest_inside", True))
    jp_border_touch_min_area_ratio = float(cfg.get("jp_border_touch_min_area_ratio", 0.05))
    jp_corridor_aspect_ratio_max = cfg.get("jp_corridor_aspect_ratio_max", 6.0)

    # Simplification
    # 권장: "safe_approx" (대각선 쇼트컷 방지)
    simplify_mode = str(cfg.get("simplify_mode", "safe_approx"))  # "none" | "approx" | "hull" | "safe_approx"
    simplify_epsilon_ratio = float(cfg.get("simplify_epsilon_ratio", 0.006))
    simplify_max_edge_ratio = float(cfg.get("simplify_max_edge_ratio", 0.35))

    # 1) wall mask
    wall = np.zeros((height, width), dtype=np.uint8)
    _draw_thick_lines(wall, walls_lines, thickness=wall_thickness)

    # 2) close to seal gaps
    if close_kernel > 1:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (close_kernel, close_kernel))
        wall = cv2.morphologyEx(wall, cv2.MORPH_CLOSE, k, iterations=max(1, close_iter))

    # 3) free space
    free = cv2.bitwise_not(wall)

    # 4) outside by flood fill from border
    outside = np.zeros((height, width), dtype=np.uint8)
    seeds = [
        (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1),
        (width // 2, 0), (width // 2, height - 1),
        (0, height // 2), (width - 1, height // 2),
    ]

    for sx, sy in seeds:
        if sx < 0 or sy < 0 or sx >= width or sy >= height:
            continue
        if free[sy, sx] == 0:
            continue

        ff = free.copy()
        m = np.zeros((height + 2, width + 2), dtype=np.uint8)
        cv2.floodFill(ff, m, seedPoint=(sx, sy), newVal=0)
        filled = (ff == 0) & (free == 255)
        outside[filled] = 255
        free[filled] = 0

    # 5) inside candidate
    inside = (free == 255).astype(np.uint8) * 255

    if open_kernel > 1:
        ok = cv2.getStructuringElement(cv2.MORPH_RECT, (open_kernel, open_kernel))
        inside = cv2.morphologyEx(inside, cv2.MORPH_OPEN, ok)

    # smoothing
    sk = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    inside = cv2.morphologyEx(inside, cv2.MORPH_CLOSE, sk)

    # 6) components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inside, connectivity=8)

    rooms: List[Room] = []
    max_room_area_px = int(width * height * max_room_area_ratio)

    def _make_poly(cnt: np.ndarray, bbox: Tuple[int, int, int, int]) -> List[Tuple[int, int]]:
        if simplify_mode == "safe_approx":
            cnt2 = simplify_without_long_edges(
                cnt,
                bbox,
                eps_ratio=simplify_epsilon_ratio,
                max_edge_ratio=simplify_max_edge_ratio,
            )
        else:
            cnt2 = _simplify_contour(cnt, simplify_mode, simplify_epsilon_ratio)
        return [(int(p[0][0]), int(p[0][1])) for p in cnt2]

    rid = 0
    for lab in range(1, num_labels):
        x, y, w, h, area = stats[lab]
        x, y, w, h = int(x), int(y), int(w), int(h)
        area = int(area)

        if area < min_room_area_px:
            continue
        if area > max_room_area_px:
            continue

        comp = (labels == lab).astype(np.uint8) * 255
        contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        cnt = max(contours, key=cv2.contourArea)
        poly = _make_poly(cnt, (x, y, w, h))

        rooms.append(Room(id=rid, contour=poly, area_px=float(area), bbox=(x, y, w, h)))
        rid += 1

    # 6.5) JP keep largest inside (ignore max_room_area_ratio)
    if jp_keep_largest_inside:
        candidates: List[Tuple[int, int, int, int, int, int]] = []

        for lab in range(1, num_labels):
            x, y, w, h, area = stats[lab]
            x, y, w, h = int(x), int(y), int(w), int(h)
            area = int(area)

            if area < min_room_area_px:
                continue

            if jp_corridor_aspect_ratio_max is not None and w > 0 and h > 0:
                ar = max(w / h, h / w)
                if ar >= float(jp_corridor_aspect_ratio_max):
                    continue

            touches_border = (
                x <= 0 or y <= 0 or (x + w) >= width - 1 or (y + h) >= height - 1
            )
            if touches_border and area < int(width * height * jp_border_touch_min_area_ratio):
                continue

            candidates.append((area, lab, x, y, w, h))

        if candidates:
            candidates.sort(key=lambda t: t[0], reverse=True)
            area, lab, x, y, w, h = candidates[0]

            already = any(r.bbox == (x, y, w, h) for r in rooms)
            if not already:
                comp = (labels == lab).astype(np.uint8) * 255
                contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    cnt = max(contours, key=cv2.contourArea)
                    poly = _make_poly(cnt, (x, y, w, h))

                    rooms.append(Room(id=rid, contour=poly, area_px=float(area), bbox=(x, y, w, h)))
                    rid += 1

    # 7) JP room type classification (LDK / WET / ROOM)
    _room_type_classify(rooms, width, height, cfg)

    # 8) debug outputs
    debug: Dict[str, str] = {}
    if debug_out_dir:
        import os

        os.makedirs(debug_out_dir, exist_ok=True)
        wall_path = f"{debug_out_dir}/{prefix}_wallmask.png"
        out_path = f"{debug_out_dir}/{prefix}_outside.png"
        in_path = f"{debug_out_dir}/{prefix}_inside.png"
        rooms_path = f"{debug_out_dir}/{prefix}_rooms.png"

        cv2.imwrite(wall_path, wall)
        cv2.imwrite(out_path, outside)
        cv2.imwrite(in_path, inside)

        # overlay (inside as base)
        vis = np.dstack([inside, inside, inside])
        for r in rooms:
            pts = np.array(r.contour, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(vis, [pts], isClosed=True, color=(0, 0, 255), thickness=2)

            # kind 라벨 표시 (원하면)
            cx, cy = _bbox_center(r.bbox)
            cv2.putText(
                vis,
                r.kind,
                (int(cx), int(cy)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        cv2.imwrite(rooms_path, vis)

        debug.update({"wallmask": wall_path, "outside": out_path, "inside": in_path, "rooms": rooms_path})

    return RoomResult(width=width, height=height, rooms=rooms, debug=debug)


# ================================================================
# detect_rooms - engine.py 에서 호출하는 고수준 API
# ================================================================
def detect_rooms(
    pdf_path: str,
    page: int = 0,
    out_dir: str = "out",
) -> RoomResult:
    """
    PDF 파일에서 방(Room)을 탐지하여 RoomResult를 반환.
    core/engine.py 에서 직접 호출하는 진입점.

    Args:
        pdf_path: PDF 파일 경로
        page: 처리할 페이지 번호 (0-indexed)
        out_dir: 디버그/결과 파일 출력 디렉토리

    Returns:
        RoomResult: 탐지된 방 목록 포함
    """
    from pathlib import Path

    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ImportError("PyMuPDF(fitz) is required for detect_rooms") from e

    from parser.image_outline import extract_room_result_from_page

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    if page >= len(doc):
        raise ValueError(f"Page {page} out of range (PDF has {len(doc)} pages)")

    pdf_page = doc[page]
    room_result = extract_room_result_from_page(pdf_page, page, out_path, pdf_path=pdf_path)

    print(f"[detect_rooms] PDF={Path(pdf_path).name} page={page} rooms={len(room_result.rooms)}")
    return room_result
