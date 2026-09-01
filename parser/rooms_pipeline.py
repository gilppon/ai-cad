# rooms_pipeline.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import math
from core.units import RASTER_PIXEL_TO_MM
import os
import json
import cv2
import numpy as np

import logging

logger = logging.getLogger(__name__)

def _out_path(fname: str) -> str:
    base = os.path.join(os.getcwd(), "out")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, fname)


def _build_refinement_context(page_index: int, output_dir: Optional[str] = None) -> Dict[str, Any]:
    base_dir = output_dir or os.path.join(os.getcwd(), "out")
    os.makedirs(base_dir, exist_ok=True)

    def p(name: str) -> str:
        return os.path.join(base_dir, f"{name}_page{page_index}.png")

    def j(name: str) -> str:
        return os.path.join(base_dir, f"{name}_page{page_index}.json")

    return {
        "page_index": int(page_index),
        "output_dir": base_dir,
        "inputs": {
            "lines_path": j("snapped"),
            "contours_path": j("contours"),
            "render_path": p("rendered"),
            "walls_path": j("walls"),
        },
        "outputs": {
            "parallel_clusters_mask_path": p("parallel_clusters_mask"),
            "parallel_clusters_overlay_path": p("parallel_clusters_overlay"),
            "parallel_clusters_json_path": j("parallel_clusters"),
            "rooms_mask_clean_path": p("rooms_mask_clean"),
            "rooms_mask_clean_overlay_path": p("rooms_mask_clean_overlay"),
            "door_mask_path": p("door_mask"),
            "rooms_mask_door_path": p("rooms_mask_door"),
            "rooms_mask_door_overlay_path": p("rooms_mask_door_overlay"),
            "room_graph_json_path": j("room_graph"),
            "room_graph_overlay_path": p("room_graph_overlay"),
        },
    }


def _resolve_refinement_context(
    rooms_payload: Dict[str, Any],
    refinement_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if refinement_context:
        page_index = int(refinement_context.get("page_index", rooms_payload.get("page_index", rooms_payload.get("page", 0))))
        output_dir = refinement_context.get("output_dir")
        base_context = _build_refinement_context(page_index=page_index, output_dir=output_dir)

        for key in ("inputs", "outputs"):
            if isinstance(refinement_context.get(key), dict):
                base_context[key].update(refinement_context[key])
        return base_context

    page_index = int(rooms_payload.get("page_index", rooms_payload.get("page", 0)))
    return _build_refinement_context(page_index=page_index)


Point = Dict[str, int]
Room = Dict[str, Any]

def _poly_area(poly: List[Point]) -> float:
    # shoelace
    if len(poly) < 3:
        return 0.0
    s = 0
    for i in range(len(poly)):
        x1, y1 = poly[i]["x"], poly[i]["y"]
        x2, y2 = poly[(i + 1) % len(poly)]["x"], poly[(i + 1) % len(poly)]["y"]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5

def _bbox(poly: List[Point]) -> Dict[str, int]:
    xs = [p["x"] for p in poly]
    ys = [p["y"] for p in poly]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return {"x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)}

def _touches_border(poly: List[Point], W: int, H: int, margin: int = 3) -> bool:
    # 폴리곤 점이 캔버스 테두리 근처에 있으면 True
    for p in poly:
        if p["x"] <= margin or p["x"] >= W - margin or p["y"] <= margin or p["y"] >= H - margin:
            return True
    return False

def _border_contact_ratio(poly: List[Point], W: int, H: int, margin: int = 3) -> float:
    # 테두리 근처 점의 비율 (외곽 접촉이 과한 공간 제거용)
    if not poly:
        return 0.0
    hit = 0
    for p in poly:
        if p["x"] <= margin or p["x"] >= W - margin or p["y"] <= margin or p["y"] >= H - margin:
            hit += 1
    return hit / len(poly)

def _simplify_rdp(poly: List[Point], eps: float) -> List[Point]:
    # Ramer–Douglas–Peucker 단순화 (외부 라이브러리 없이)
    # eps는 픽셀 단위(크면 더 단순)
    if len(poly) < 3:
        return poly

    def dist_point_to_segment(px, py, ax, ay, bx, by) -> float:
        # segment AB to point P distance
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        c1 = vx * wx + vy * wy
        if c1 <= 0:
            return math.hypot(px - ax, py - ay)
        c2 = vx * vx + vy * vy
        if c2 <= c1:
            return math.hypot(px - bx, py - by)
        t = c1 / c2
        projx, projy = ax + t * vx, ay + t * vy
        return math.hypot(px - projx, py - projy)

    def rdp(points: List[Point]) -> List[Point]:
        if len(points) < 3:
            return points
        ax, ay = points[0]["x"], points[0]["y"]
        bx, by = points[-1]["x"], points[-1]["y"]
        max_d = -1.0
        idx = -1
        for i in range(1, len(points) - 1):
            px, py = points[i]["x"], points[i]["y"]
            d = dist_point_to_segment(px, py, ax, ay, bx, by)
            if d > max_d:
                max_d = d
                idx = i
        if max_d > eps:
            left = rdp(points[: idx + 1])
            right = rdp(points[idx:])
            return left[:-1] + right
        else:
            return [points[0], points[-1]]

    # 닫힌 폴리곤이므로, 시작점을 고정하고 한 번 단순화 후, 다시 닫힘 보장
    simplified = rdp(poly)
    # 너무 줄어들면 원본 유지
    if len(simplified) < 4:
        return poly
    return simplified

def _classify_corridor(bbox: Dict[str, int], aspect_th: float = 3.0) -> bool:
    w, h = max(1, bbox["w"]), max(1, bbox["h"])
    aspect = max(w / h, h / w)
    return aspect >= aspect_th
    


def detect_and_refine_rooms(
    rooms_payload: Dict[str, Any],
    *,
    refinement_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    입력: room_detect.py가 만든 page0_rooms.json 같은 payload 전체(dict)
    출력: refine된 payload(dict)
    """
    if rooms_payload is None:
        raise ValueError("detect_and_refine_rooms(): rooms_payload is None")

    W = int(rooms_payload["canvas"]["width"])
    H = int(rooms_payload["canvas"]["height"])
    rooms: List[Room] = list(rooms_payload.get("rooms", []))
    context = _resolve_refinement_context(rooms_payload, refinement_context)
    page_index = int(context["page_index"])
    lines_path = context["inputs"]["lines_path"]
    contours_path = context["inputs"]["contours_path"]
    render_path = context["inputs"]["render_path"]
    walls_path = context["inputs"]["walls_path"]
    parallel_clusters_mask_path = context["outputs"]["parallel_clusters_mask_path"]
    parallel_clusters_overlay_path = context["outputs"]["parallel_clusters_overlay_path"]
    parallel_clusters_json_path = context["outputs"]["parallel_clusters_json_path"]
    rooms_mask_clean_path = context["outputs"]["rooms_mask_clean_path"]
    rooms_mask_clean_overlay_path = context["outputs"]["rooms_mask_clean_overlay_path"]
    door_mask_path = context["outputs"]["door_mask_path"]
    rooms_mask_door_path = context["outputs"]["rooms_mask_door_path"]
    rooms_mask_door_overlay_path = context["outputs"]["rooms_mask_door_overlay_path"]
    room_graph_json_path = context["outputs"]["room_graph_json_path"]
    room_graph_overlay_path = context["outputs"]["room_graph_overlay_path"]

    # ----------------------------
    # STEP3-4: parallel clusters detect (우드데크/난간)
    # ----------------------------
    cluster_mask = np.zeros((H, W), dtype=np.uint8)
    shell_bmask = np.zeros((H, W), dtype=np.uint8)
    clusters_meta: List[dict] = []

    logger.info("[STEP3-4] out dir =", context["output_dir"])
    logger.info("[STEP3-4] lines_path =", lines_path, "exists=", os.path.exists(lines_path))
    logger.info("[STEP3-4] contours_path =", contours_path, "exists=", os.path.exists(contours_path))
    logger.info("[STEP3-4] render_path =", render_path, "exists=", os.path.exists(render_path))

    if os.path.exists(lines_path) and os.path.exists(contours_path):
        lines_step2 = load_snapped_lines(lines_path)
        outer_poly = _load_outer_shell_from_contours(contours_path)

        cluster_mask, clusters_meta, shell_bmask = detect_parallel_clusters_mask(
            lines=lines_step2,
            image_shape_hw=(H, W),
            outer_shell_polygon=outer_poly,
        )

        cv2.imwrite(parallel_clusters_mask_path, cluster_mask)

        base = cv2.imread(render_path)
        if base is None:
            base = np.zeros((H, W, 3), dtype=np.uint8)

        overlay = base.copy()
        overlay[:, :, 1] = np.maximum(overlay[:, :, 1], shell_bmask)
        overlay[:, :, 2] = np.maximum(overlay[:, :, 2], cluster_mask)
        cv2.imwrite(parallel_clusters_overlay_path, overlay)

        with open(parallel_clusters_json_path, "w", encoding="utf-8") as f:
            json.dump(clusters_meta, f, indent=2)

        logger.info("[STEP3-4] lines loaded =", len(lines_step2), "clusters =", len(clusters_meta))
    else:
        logger.info("[STEP3-4] skipped: walls_page0.json or contours_page0.json missing")

    # ----------------------------
    # STEP3-5-0: cluster mask ensure (파일에서 로드 fallback)
    # ----------------------------
    if (not np.any(cluster_mask)) and os.path.exists(parallel_clusters_mask_path):
        cm = cv2.imread(parallel_clusters_mask_path, cv2.IMREAD_GRAYSCALE)
        if cm is not None:
            cluster_mask = cm

    if cluster_mask.shape[:2] != (H, W):
        cluster_mask = cv2.resize(cluster_mask, (W, H), interpolation=cv2.INTER_NEAREST)

    logger.info("[STEP3-5] cluster_mask any =", bool(np.any(cluster_mask)))

    # --- 튜닝 파라미터 ---
    MIN_AREA_PX2 = 12000
    BORDER_RATIO_MAX = 0.35
    SIMPLIFY_EPS = 3.5
    ASPECT_CORRIDOR = 3.0

    refined: List[Room] = []
    # ============================
    # STEP3-5-α: expand cluster mask to area (우드데크 영역화)
    # ============================
    if np.any(cluster_mask):
        # 우드데크 선 간격을 메우기 위한 확장
        # 커널 크기는 도면 스케일에 따라 7~15 사이가 적당
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        cluster_mask_area = cv2.dilate(cluster_mask, k, iterations=2)
    else:
        cluster_mask_area = cluster_mask

    # ----------------------------
    # STEP3-5-1: subtract cluster area from each room polygon
    # ----------------------------
    for r in rooms:
        poly = r.get("polygon", [])
        if len(poly) < 4:
            continue

        area = float(r.get("area_px2") or _poly_area(poly))
        if area < MIN_AREA_PX2:
            continue

        border_ratio = _border_contact_ratio(poly, W, H, margin=20)
        if border_ratio > BORDER_RATIO_MAX:
            continue

        # subtract
        if np.any(cluster_mask):
            rm = _poly_points_to_mask(poly, (H, W))
            rm2 = cv2.bitwise_and(rm, cv2.bitwise_not(cluster_mask_area))
            rm2 = cv2.morphologyEx(rm2, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

            new_poly = _mask_to_largest_polygon(rm2, simplify_eps=2.0)
            if len(new_poly) >= 4:
                poly = new_poly
                area = float(_poly_area(poly))
            else:
                continue

        # simplify + bbox
        poly2 = _simplify_rdp(poly, eps=SIMPLIFY_EPS)
        bbox2 = _bbox(poly2)

        kind = r.get("kind", "ROOM")
        if kind == "ROOM" and _classify_corridor(bbox2, ASPECT_CORRIDOR):
            kind = "CORRIDOR"

        nr = dict(r)
        nr["polygon"] = poly2
        nr["bbox"] = bbox2
        nr["area_px2"] = float(_poly_area(poly2))
        nr["kind"] = kind
        nr["refine"] = {
            "border_ratio": border_ratio,
            "simplified": len(poly2) < len(poly),
            "n_pts_before": len(poly),
            "n_pts_after": len(poly2),
        }
        refined.append(nr)

    # id 재정렬
    for i, rr in enumerate(refined):
        rr["id"] = i

    # ----------------------------
    # STEP3-5-2: save cleaned rooms mask (검증용)
    # ----------------------------
    rooms_mask_clean = np.zeros((H, W), dtype=np.uint8)
    for rr in refined:
        p = rr.get("polygon", [])
        if len(p) >= 3:
            pts = np.array([[pt["x"], pt["y"]] for pt in p], dtype=np.int32).reshape(-1, 1, 2)
            cv2.fillPoly(rooms_mask_clean, [pts], 255)

    cv2.imwrite(rooms_mask_clean_path, rooms_mask_clean)

    base = cv2.imread(render_path)
    if base is None:
        base = np.zeros((H, W, 3), dtype=np.uint8)

    overlay_clean = base.copy()
    overlay_clean[:, :, 2] = np.maximum(overlay_clean[:, :, 2], rooms_mask_clean)  # red: indoor
    overlay_clean[:, :, 1] = np.maximum(overlay_clean[:, :, 1], cluster_mask_area)# green: removed
    cv2.imwrite(rooms_mask_clean_overlay_path, overlay_clean)

    logger.info("[STEP3-5] saved: rooms_mask_clean_page0.png / rooms_mask_clean_overlay_page0.png")
   
    # ---- STEP4 anchor guard ----
    assert "rooms_mask_clean" in locals(), "STEP4 must run after STEP3-5 rooms_mask_clean is created"

    
     # ============================
    # STEP4: door/opening detection by WALL-GAP (stable)
    # input: rooms_mask_clean (from STEP3-5), walls_page0.json
    # output: door_mask_page0.png, rooms_mask_door_page0.png, overlay
    # ============================
    assert "rooms_mask_clean" in locals(), "STEP4 must run after STEP3-5"
    # --- load wall_lines inside STEP4 (no external dependency) ---
    with open(walls_path, "r", encoding="utf-8") as f:
        walls_data = json.load(f)

    wall_lines: List[LineSeg] = []
    for x1, y1, x2, y2 in walls_data.get("walls", []):
        wall_lines.append(LineSeg(int(x1), int(y1), int(x2), int(y2)))

    # 기본값(항상 정의해서 크래시 방지)
    door_mask = np.zeros((H, W), dtype=np.uint8)
    door_mask_area = np.zeros((H, W), dtype=np.uint8)
    rooms_mask_door = rooms_mask_clean.copy()

    # 1) walls -> wall_mask (굵게 그려서 '벽 띠'를 만든다)
    wall_mask = np.zeros((H, W), dtype=np.uint8)
    for ln in wall_lines:  # walls_page0.json 로드해서 만든 LineSeg 리스트
        cv2.line(wall_mask, (ln.x1, ln.y1), (ln.x2, ln.y2), 255, 7, cv2.LINE_AA)

    # 벽 띠 확장(도면마다 조금 다르지만 7~11 사이가 안전)
    wall_mask = cv2.dilate(wall_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)), iterations=1)

    # 2) room boundary 추출
    room_er = cv2.erode(rooms_mask_clean, np.ones((3, 3), np.uint8), iterations=1)
    room_boundary = cv2.subtract(rooms_mask_clean, room_er)  # 1px~ 얇은 경계

    # 3) "벽 근처" 영역 만들기
    wall_near = cv2.dilate(wall_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21)), iterations=1)

    # 4) 핵심: 방 경계 중에서 (벽 근처이면서) (벽 픽셀이 없는) 지점 = '개구부 후보'
    #    즉, wall_near ∩ room_boundary ∩ (~wall_mask)
    gap = cv2.bitwise_and(room_boundary, wall_near)
    gap = cv2.bitwise_and(gap, cv2.bitwise_not(wall_mask))

    # 5) gap을 문 영역으로 키우기 (벽 두께 + 여유)
    gap = cv2.dilate(gap, cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11)), iterations=2)

    # 6) 연결성분 필터: 너무 작은 잡음 제거 + 너무 큰 구멍(외곽) 제거
    num, lab, stats, _ = cv2.connectedComponentsWithStats(gap, connectivity=8)
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < 120:       # 너무 작은 잡음 제거
            continue
        if area > 9000:      # 너무 큰 건 외곽/큰 공백일 가능성
            continue
    # 가로/세로 비율이 너무 극단이면(치수선 등) 제거
        ar = max(w / max(1, h), h / max(1, w))
        if ar > 12.0:
            continue
        door_mask[lab == i] = 255

    # 문 마스크를 실제 “뚫릴 영역”으로 확장
    door_mask_area = cv2.dilate(door_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (13, 13)), iterations=1)

    # 7) subtract
    rooms_mask_door = cv2.bitwise_and(rooms_mask_clean, cv2.bitwise_not(door_mask_area))

    # 8) 저장
    cv2.imwrite(door_mask_path, door_mask_area)
    cv2.imwrite(rooms_mask_door_path, rooms_mask_door)

    base = cv2.imread(render_path)
    if base is None:
        base = np.zeros((H, W, 3), dtype=np.uint8)

    overlay = base.copy()
    overlay[:, :, 2] = np.maximum(overlay[:, :, 2], rooms_mask_door)   # red: room after openings
    overlay[:, :, 1] = np.maximum(overlay[:, :, 1], door_mask_area)    # green: openings
    cv2.imwrite(rooms_mask_door_overlay_path, overlay)

    logger.info("[STEP4] openings components =", int(np.max(lab)), "saved door overlay")

    # 기존 subtract 로직 유지
    
    # ============================
    # STEP5: build room connectivity graph (stable)
    # ============================

    def _poly_to_mask_xy(poly_pts: List[Dict[str, int]], shape_hw: Tuple[int, int]) -> np.ndarray:
        h, w = shape_hw
        m = np.zeros((h, w), dtype=np.uint8)
        pts = np.array([[p["x"], p["y"]] for p in poly_pts], dtype=np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(m, [pts], 255)
        return m

    def _centroid_from_mask(m: np.ndarray) -> Tuple[float, float]:
        ys, xs = np.where(m > 0)
        if len(xs) == 0:
            return (0.0, 0.0)
        return (float(xs.mean()), float(ys.mean()))

    # 0) 준비: wall_mask 만들기 (벽 선분 기반)
    with open(walls_path, "r", encoding="utf-8") as f:
        walls_data = json.load(f)

    wall_lines_local: List[LineSeg] = []
    for x1, y1, x2, y2 in walls_data.get("walls", []):
        wall_lines_local.append(LineSeg(int(x1), int(y1), int(x2), int(y2)))

    wall_mask = np.zeros((H, W), dtype=np.uint8)
    for ln in wall_lines_local:
        cv2.line(wall_mask, (ln.x1, ln.y1), (ln.x2, ln.y2), 255, 7, cv2.LINE_AA)
    wall_mask = cv2.dilate(wall_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)), iterations=1)

    # 1) door_mask 로드(있으면 사용, 없으면 0)
    door_mask_area = np.zeros((H, W), dtype=np.uint8)
    if os.path.exists(door_mask_path):
        dm = cv2.imread(door_mask_path, cv2.IMREAD_GRAYSCALE)
        if dm is not None:
            door_mask_area = dm
    if door_mask_area.shape[:2] != (H, W):
        door_mask_area = cv2.resize(door_mask_area, (W, H), interpolation=cv2.INTER_NEAREST)

    # 2) room masks/centroids 준비 (refined 기준)
    room_masks: List[np.ndarray] = []
    room_centroids: List[Tuple[float, float]] = []
    room_meta = []

    for rr in refined:
        poly = rr.get("polygon", [])
        if len(poly) < 3:
            room_masks.append(np.zeros((H, W), dtype=np.uint8))
            room_centroids.append((0.0, 0.0))
            room_meta.append({"id": rr.get("id"), "kind": rr.get("kind", "ROOM")})
            continue

        m = _poly_to_mask_xy(poly, (H, W))
        room_masks.append(m)
        room_centroids.append(_centroid_from_mask(m))
        room_meta.append({
            "id": int(rr.get("id", 0)),
            "kind": rr.get("kind", "ROOM"),
            "area_px2": float(rr.get("area_px2", 0.0)),
        })

    # 3) pairwise adjacency 판정
    # 핵심: 두 방이 '서로 접촉(경계 근접)'하면서,
    #       그 접촉 밴드에서 wall_mask가 너무 크지 않거나(오픈 공간),
    #       door_mask가 감지되면(문 힌트) 연결로 본다.
    MIN_CONTACT_PX = 120       # 접촉 픽셀 최소치
    WALL_BLOCK_RATIO = 0.55    # 접촉 밴드 중 벽 비율이 이 이상이면 "막힘"
    DOOR_HIT_PX = 25           # door_mask가 접촉 밴드에서 이 이상이면 "문 있음"
    BARRIER_MAX = 0.18  # 벽 통과 허용 비율 (0.12~0.22 안정)

    edges = []
    n = len(room_masks)

    dilate_k = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    for i in range(n):
        mi = room_masks[i]
        if not np.any(mi):
            continue
        mi_d = cv2.dilate(mi, dilate_k, iterations=1)

        for j in range(i + 1, n):
            mj = room_masks[j]
            if not np.any(mj):
                continue
            mj_d = cv2.dilate(mj, dilate_k, iterations=1)

            # contact band
            contact = cv2.bitwise_and(mi_d, mj_d)
            c_area = int(cv2.countNonZero(contact))
            if c_area < MIN_CONTACT_PX:
                continue

            wall_cover = cv2.bitwise_and(contact, wall_mask)
            w_area = int(cv2.countNonZero(wall_cover))
            wall_ratio = w_area / max(1, c_area)

            door_cover = cv2.bitwise_and(contact, door_mask_area)
            d_area = int(cv2.countNonZero(door_cover))

            # 결정 규칙
            # 1) door 힌트가 있으면 연결
            # 2) door 힌트 없더라도 벽 비율이 충분히 낮으면(큰 개구부/오픈 공간) 연결
            # 거리 기반 보완: 중심점이 충분히 가까우면 연결
            dx = room_centroids[i][0] - room_centroids[j][0]
            dy = room_centroids[i][1] - room_centroids[j][1]
            centroid_dist = (dx*dx + dy*dy) ** 0.5
            # ---- barrier crossing score: line between centroids crosses walls 얼마나?
            ax, ay = room_centroids[i]
            bx, by = room_centroids[j]

            # 선 샘플링 (50~80점이면 충분)
            S = 70
            xs = np.linspace(ax, bx, S).astype(np.int32)
            ys = np.linspace(ay, by, S).astype(np.int32)
            xs = np.clip(xs, 0, W-1)
            ys = np.clip(ys, 0, H-1)

            # 벽 통과 비율(0~1)
            wall_hits = wall_mask[ys, xs] > 0
            wall_hit_ratio = float(np.mean(wall_hits))

            is_connected = (
                (d_area >= DOOR_HIT_PX)
                or (wall_ratio <= (1.0 - WALL_BLOCK_RATIO))
                or (c_area >= 450)   # ★ 강한 접촉은 연결로 인정 (문 미탐 보완)
                or (wall_hit_ratio <= BARRIER_MAX)   # ★ 확실한 근거
            )


            if is_connected:
                edges.append({
                    "a": int(room_meta[i]["id"]),
                    "b": int(room_meta[j]["id"]),
                    "contact_px": c_area,
                    "wall_ratio": float(wall_ratio),
                    "door_hit_px": d_area,
                    "reason": "door" if d_area >= DOOR_HIT_PX else "open_or_gap",
                    "wall_hit_ratio": wall_hit_ratio,
                })

    logger.info("[STEP5] edges =", len(edges))

    graph = {
        "page_index": page_index,
        "rooms": room_meta,
        "edges": edges,
        "params": {
            "MIN_CONTACT_PX": MIN_CONTACT_PX,
            "WALL_BLOCK_RATIO": WALL_BLOCK_RATIO,
            "DOOR_HIT_PX": DOOR_HIT_PX,
        }
    }

    with open(room_graph_json_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    # 4) overlay 시각화 (centroid 연결선)
    base = cv2.imread(render_path)
    if base is None:
        base = np.zeros((H, W, 3), dtype=np.uint8)

    ov = base.copy()

    # 방 중심점 표시(파랑)
    for (cx, cy) in room_centroids:
        if cx > 0 and cy > 0:
            cv2.circle(ov, (int(cx), int(cy)), 6, (255, 0, 0), -1, cv2.LINE_AA)

    # 연결선 표시(초록)
    for e in edges:
        a = e["a"]; b = e["b"]
        ia = next((k for k, rm in enumerate(room_meta) if rm["id"] == a), None)
        ib = next((k for k, rm in enumerate(room_meta) if rm["id"] == b), None)
        if ia is None or ib is None:
            continue
        ax, ay = room_centroids[ia]
        bx, by = room_centroids[ib]
        cv2.line(ov, (int(ax), int(ay)), (int(bx), int(by)), (0, 255, 0), 3, cv2.LINE_AA)

    cv2.imwrite(room_graph_overlay_path, ov)
    logger.info("[STEP5] saved: room_graph_page0.json / room_graph_overlay_page0.png")
    out = dict(rooms_payload)
    out["rooms"] = refined
    out["rooms_count"] = len(refined)
    out["refined"] = True
    out["page_index"] = page_index
    return out


import math
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

@dataclass
class LineSeg:
    x1: int; y1: int; x2: int; y2: int
    def mid(self):
        return np.array([(self.x1 + self.x2) * 0.5, (self.y1 + self.y2) * 0.5], dtype=np.float32)
    def length(self):
        return float(math.hypot(self.x2 - self.x1, self.y2 - self.y1))
    def angle_rad_0_pi(self):
        a = math.atan2(self.y2 - self.y1, self.x2 - self.x1)
        if a < 0: a += math.pi
        if a >= math.pi: a -= math.pi
        return a

def _polygon_to_boundary_mask(shape_hw: Tuple[int,int], outer_poly: np.ndarray, thickness: int = 2) -> np.ndarray:
    h, w = shape_hw
    m = np.zeros((h, w), dtype=np.uint8)
    poly = np.asarray(outer_poly, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(m, [poly], True, 255, thickness, cv2.LINE_AA)
    return m

def _dist_to_shell(mids_xy: np.ndarray, shell_boundary_mask: np.ndarray) -> np.ndarray:
    inv = (shell_boundary_mask == 0).astype(np.uint8) * 255
    dist = cv2.distanceTransform(inv, cv2.DIST_L2, 3)
    mids = np.round(mids_xy).astype(np.int32)
    mids[:, 0] = np.clip(mids[:, 0], 0, dist.shape[1] - 1)
    mids[:, 1] = np.clip(mids[:, 1], 0, dist.shape[0] - 1)
    return dist[mids[:, 1], mids[:, 0]]

def _robust_spacing_ok(d_sorted: np.ndarray, max_cv: float = 0.35) -> bool:
    if len(d_sorted) < 3: return False
    gaps = np.diff(d_sorted)
    gaps = gaps[gaps > 1e-6]
    if len(gaps) < 2: return False
    med = float(np.median(gaps))
    if med <= 1e-6: return False
    mad = float(np.median(np.abs(gaps - med))) + 1e-6
    robust_std = 1.4826 * mad
    cv = robust_std / med
    return cv <= max_cv

def detect_parallel_clusters_mask(
    lines: List[LineSeg],
    image_shape_hw: Tuple[int, int],
    outer_shell_polygon: np.ndarray,
    *,
    min_len: int = 25,
    angle_bin_deg: float = 5.0,
    min_cluster_size: int = 3,
    dist_group_tol_px: float = 8.0,
    shell_dist_thresh_px: float = 28.0,
    max_spacing_cv: float = 0.35,
) -> Tuple[np.ndarray, List[dict], np.ndarray]:
    """
    returns: (cluster_mask, clusters_meta, shell_boundary_mask)
    """
    h, w = image_shape_hw
    lines_f = [ln for ln in lines if ln.length() >= min_len]
    if len(lines_f) < min_cluster_size:
        return np.zeros((h, w), np.uint8), [], np.zeros((h, w), np.uint8)

    shell_bmask = _polygon_to_boundary_mask((h, w), outer_shell_polygon, thickness=2)
    mids = np.stack([ln.mid() for ln in lines_f], axis=0).astype(np.float32)
    shell_dist = _dist_to_shell(mids, shell_bmask)

    bin_rad = math.radians(angle_bin_deg)
    angles = np.array([ln.angle_rad_0_pi() for ln in lines_f], dtype=np.float32)
    bins: Dict[int, List[int]] = {}
    for i, a in enumerate(angles):
        b = int(round(a / bin_rad))
        bins.setdefault(b, []).append(i)

    cluster_mask = np.zeros((h, w), dtype=np.uint8)
    clusters = []

    for b, idxs in bins.items():
        if len(idxs) < min_cluster_size:
            continue

        a_mean = float(np.mean(angles[idxs]))
        n = np.array([-math.sin(a_mean), math.cos(a_mean)], dtype=np.float32)

        d = (mids[idxs] @ n)
        order = np.argsort(d)
        d_sorted = d[order]
        idxs_sorted = [idxs[int(k)] for k in order]

        start = 0
        while start < len(d_sorted):
            end = start + 1
            while end < len(d_sorted) and (d_sorted[end] - d_sorted[end - 1]) <= dist_group_tol_px:
                end += 1

            if (end - start) >= min_cluster_size:
                group = idxs_sorted[start:end]
                group_d = d_sorted[start:end]

                if _robust_spacing_ok(group_d, max_cv=max_spacing_cv):
                    mean_shell = float(np.mean(shell_dist[group]))
                    if mean_shell <= shell_dist_thresh_px:
                        clusters.append({
                            "count": int(end - start),
                            "angle_deg": float(a_mean * 180.0 / math.pi),
                            "mean_shell_dist": mean_shell,
                            "indices": group,
                        })
                        for gi in group:
                            ln = lines_f[gi]
                            cv2.line(cluster_mask, (ln.x1, ln.y1), (ln.x2, ln.y2), 255, 3, cv2.LINE_AA)

            start = end

    clusters.sort(key=lambda c: (c["mean_shell_dist"], -c["count"]))
    return cluster_mask, clusters, shell_bmask

def _load_lines_page0_json(path: str) -> List[LineSeg]:
    logger.info("[STEP3-4] loader: walls_page0.json")
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    raw = d.get("walls", [])
    lines = []
    for it in raw:
        if isinstance(it, (list, tuple)) and len(it) >= 4:
            x1, y1, x2, y2 = it[0], it[1], it[2], it[3]
            lines.append(LineSeg(int(x1), int(y1), int(x2), int(y2)))

    logger.info("[STEP3-4] lines loaded =", len(lines))
    return lines

def load_snapped_lines(path: str) -> List[LineSeg]:
    logger.info("[STEP3-4] loader: snapped_page0.json")
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    raw = d.get("snapped", [])
    lines: List[LineSeg] = []
    for it in raw:
        if isinstance(it, (list, tuple)) and len(it) >= 4:
            x1, y1, x2, y2 = it[0], it[1], it[2], it[3]
            lines.append(LineSeg(int(x1), int(y1), int(x2), int(y2)))

    logger.info("[STEP3-4] lines loaded =", len(lines))
    return lines



def _load_outer_shell_from_contours(path: str) -> np.ndarray:
    logger.info("[STEP3-4] loader: contours_page0.json")
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    contours = d["contours"]  # [{area, points}, ...]
    outer = max(contours, key=lambda c: float(c.get("area", 0.0)))
    pts = outer["points"]     # [[x,y], ...]
    poly = np.array([[int(x), int(y)] for x, y in pts], dtype=np.int32)

    logger.info("[STEP3-4] outer pts =", len(poly), "area =", outer.get("area"))
    return poly


def _poly_points_to_mask(poly: List[Point], shape_hw: Tuple[int, int]) -> np.ndarray:
    h, w = shape_hw
    m = np.zeros((h, w), dtype=np.uint8)
    pts = np.array([[p["x"], p["y"]] for p in poly], dtype=np.int32).reshape(-1, 1, 2)
    cv2.fillPoly(m, [pts], 255)
    return m


def _mask_to_largest_polygon(mask: np.ndarray, simplify_eps: float = 0.0) -> List[Point]:
    """
    mask에서 가장 큰 연결 성분의 외곽 contour를 polygon(Point dict)으로 반환
    """
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return []

    cnt = max(cnts, key=cv2.contourArea)
    if simplify_eps > 0:
        cnt = cv2.approxPolyDP(cnt, simplify_eps, True)

    pts = cnt.reshape(-1, 2)
    return [{"x": int(x), "y": int(y)} for x, y in pts]
import glob

def dbg_list_out_json():
    out_dir = os.path.join(os.getcwd(), "out")
    logger.info("[DBG] out_dir =", out_dir)
    paths = sorted(glob.glob(os.path.join(out_dir, "*.json")))
    logger.info("[DBG] json files:", len(paths))
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            n = len(data) if isinstance(data, list) else (len(data.keys()) if isinstance(data, dict) else -1)
            head = None
            if isinstance(data, list) and len(data) > 0:
                head = data[0]
            logger.info(" -", os.path.basename(p), "type=", type(data).__name__, "len=", n, "head=", str(head)[:120])
        except Exception as e:
            logger.info(" -", os.path.basename(p), "read fail:", e)

# 실행 시 1번만 호출

import json, os

def dbg_peek_json(fname: str):
    path = os.path.join(os.getcwd(), "out", fname)
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    logger.info("\n[PEEK]", fname)
    logger.info("type:", type(d).__name__)
    if isinstance(d, dict):
        logger.info("keys:", list(d.keys()))
        for k in d.keys():
            v = d[k]
            if isinstance(v, list):
                head = v[0] if len(v) else None
                logger.info(f" - {k}: list len={len(v)} head={str(head)[:120]}")
            elif isinstance(v, dict):
                logger.info(f" - {k}: dict keys={list(v.keys())[:10]}")
            else:
                logger.info(f" - {k}: {type(v).__name__} {str(v)[:80]}")
    else:
        logger.info("len:", len(d))
def export_step_from_rooms(
    rooms_payload: Dict[str, Any],
    graph_path: str,
    *,
    out_step: str = "out/result.step",
    out_meta: str = "out/result.meta.json",
    px_to_mm: float = RASTER_PIXEL_TO_MM,  # ★ 픽셀 → mm 스케일 (SSOT)
    wall_height_mm: float = 2400.0,
):
    """
    STEP6: Export rooms as closed solids + connectivity as metadata
    """
    try:
        import FreeCAD
        import Part
    except Exception as e:
        raise RuntimeError("FreeCAD Python not available") from e

    # 1) FreeCAD doc
    doc = FreeCAD.newDocument("Rooms")

    # 2) Load graph
    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    meta = {
        "page_index": rooms_payload.get("page_index", 0),
        "rooms": [],
        "edges": graph.get("edges", []),
        "params": graph.get("params", {}),
    }

    # 3) Create room solids
    for r in rooms_payload.get("rooms", []):
        poly = r.get("polygon", [])
        if len(poly) < 3:
            continue

        # px → mm
        pts = [
            FreeCAD.Vector(p["x"] * px_to_mm, p["y"] * px_to_mm, 0)
            for p in poly
        ]
        pts.append(pts[0])  # close

        wire = Part.makePolygon(pts)
        face = Part.Face(wire)
        solid = face.extrude(FreeCAD.Vector(0, 0, wall_height_mm))

        obj = doc.addObject("Part::Feature", f"Room_{r['id']}")
        obj.Shape = solid

        meta["rooms"].append({
            "id": int(r["id"]),
            "kind": r.get("kind", "ROOM"),
            "area_px2": float(r.get("area_px2", 0.0)),
            "area_m2": float(r.get("area_px2", 0.0)) * (px_to_mm ** 2) / 1e6,
            "height_mm": wall_height_mm,
        })

    # 4) Export STEP
    Part.export(doc.Objects, out_step)
    logger.info("[STEP6] saved:", out_step)

    # 5) Save metadata
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    logger.info("[STEP6] saved:", out_meta)

    doc.close()
    return
if __name__ == "__main__":
    dbg_list_out_json()
    # ---- STEP6 실행 (payload를 JSON에서 재로딩: 가장 안전) ----
    rooms_json_path = _out_path("rooms_page0.json")
    graph_json_path = _out_path("room_graph_page0.json")

    with open(rooms_json_path, "r", encoding="utf-8") as f:
        rooms_payload_step6 = json.load(f)

    if rooms_payload_step6 is None or not isinstance(rooms_payload_step6, dict):
        raise RuntimeError(f"STEP6: invalid rooms payload in {rooms_json_path}")

    export_step_from_rooms(
        rooms_payload=rooms_payload_step6,
        graph_path=graph_json_path,
        out_step=_out_path("result.step"),
        out_meta=_out_path("result.meta.json"),
    )
    


#dbg_peek_json("lines_page0.json")
#dbg_peek_json("contours_page0.json")
