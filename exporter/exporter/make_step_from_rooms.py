# exporter/freecad_rooms_to_step.py
import json
import os

import FreeCAD as App
import Part

WALL_HEIGHT_MM = 2400.0
WALL_THICK_MM = 120.0
FLOOR_THICK_MM = 150.0
def edge_key(a: App.Vector, b: App.Vector, tol_mm: float = 1.0) -> tuple:
    # 좌표를 tol 단위로 라운딩해서 키 안정화 (미세 오차/단순화 영향 흡수)
    def q(v: App.Vector):
        return (round(v.x / tol_mm) * tol_mm, round(v.y / tol_mm) * tol_mm)
    A = q(a)
    B = q(b)
    return (A, B) if A <= B else (B, A)

def vlen(a: App.Vector, b: App.Vector) -> float:
    dx = b.x - a.x
    dy = b.y - a.y
    return (dx*dx + dy*dy) ** 0.5

def unit2(a: App.Vector, b: App.Vector):
    dx = b.x - a.x
    dy = b.y - a.y
    L = (dx*dx + dy*dy) ** 0.5
    if L < 1e-9:
        return (0.0, 0.0, 0.0)
    return (dx / L, dy / L, L)

def dot2(u, v) -> float:
    return u[0]*v[0] + u[1]*v[1]

def is_perp(u, v, th=0.25) -> bool:
    # |dot| < th 이면 거의 직교
    return abs(dot2(u, v)) < th

def is_collinear(u, v, th=0.92) -> bool:
    # dot > th 이면 거의 같은 방향(또는 -th면 반대방향)
    return abs(dot2(u, v)) > th

def bbox_xy(shape):
    bb = shape.BoundBox
    return (bb.XMin, bb.YMin, bb.XMax, bb.YMax)

def bbox_overlap_xy(a, b) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)

def detect_door_openings_from_notches(pts, wall_thick_mm: float):
    """
    pts: [Vector(x,y,0), ...] (room polygon)
    return: [(a,b), ...]  a,b는 opening 중심선(벽 방향) 세그먼트
    노치 패턴: (벽방향) -> (안쪽) -> (문폭) -> (바깥) -> (벽방향 계속)
    """
    openings = []
    n = len(pts)
    if n < 6:
        return openings

    # 튜닝(일본 주거 도면 기준)
    DOOR_W_MIN = 600.0
    DOOR_W_MAX = 1000.0
    # 노치 깊이(벽 두께 수준)
    DEPTH_MIN = max(60.0, wall_thick_mm * 0.35)
    DEPTH_MAX = max(220.0, wall_thick_mm * 2.5)

    for i in range(n):
        p0 = pts[i]
        p1 = pts[(i+1) % n]
        p2 = pts[(i+2) % n]
        p3 = pts[(i+3) % n]
        p4 = pts[(i+4) % n]

        u01 = unit2(p0, p1)
        u12 = unit2(p1, p2)
        u23 = unit2(p2, p3)
        u34 = unit2(p3, p4)

        if u01[2] < 1e-6 or u12[2] < 1e-6 or u23[2] < 1e-6 or u34[2] < 1e-6:
            continue

        # 조건: 벽 방향(u01)과 안쪽(u12)은 직교
        if not is_perp(u01, u12): 
            continue
        # 문폭(u23)은 벽방향과 거의 평행
        if not is_collinear(u01, u23):
            continue
        # 바깥(u34)은 안쪽(u12)과 반대방향(대략) + 직교
        if not is_perp(u23, u34):
            continue

        depth = u12[2]
        door_w = u23[2]

        if not (DEPTH_MIN <= depth <= DEPTH_MAX):
            continue
        if not (DOOR_W_MIN <= door_w <= DOOR_W_MAX):
            continue

        # opening은 벽선 상에서 p1->p4가 문 구간의 “벽 방향”
        # (p1은 노치 시작점, p4는 노치 끝나서 벽선 복귀점)
        # 이 세그먼트 길이가 문폭과 비슷해야 함
        seg_w = vlen(p1, p4)
        if seg_w < DOOR_W_MIN or seg_w > DOOR_W_MAX * 1.2:
            continue

        openings.append((p1, p4))

    return openings

def load_payload(path: str):
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    scale = payload.get("scale", {})
    pixel_to_mm = float(scale.get("pixel_to_mm", 1.0))  # 없으면 임시 1.0
    return payload, pixel_to_mm

def poly_to_pts(poly, px_to_mm: float):
    return [App.Vector(p["x"] * px_to_mm, p["y"] * px_to_mm, 0.0) for p in poly]

def make_solid_from_poly(pts, height_mm: float):
    wire = Part.makePolygon(pts + [pts[0]])
    face = Part.Face(wire)
    return face.extrude(App.Vector(0, 0, height_mm))

def make_wall_from_edge(a, b, thick_mm: float, height_mm: float):
    vx = b.x - a.x
    vy = b.y - a.y
    L = (vx*vx + vy*vy) ** 0.5
    if L < 1e-6:
        return None

    nx = -vy / L
    ny =  vx / L

    p1 = App.Vector(a.x + nx*(thick_mm/2), a.y + ny*(thick_mm/2), 0)
    p2 = App.Vector(b.x + nx*(thick_mm/2), b.y + ny*(thick_mm/2), 0)
    p3 = App.Vector(b.x - nx*(thick_mm/2), b.y - ny*(thick_mm/2), 0)
    p4 = App.Vector(a.x - nx*(thick_mm/2), a.y - ny*(thick_mm/2), 0)

    wire = Part.makePolygon([p1, p2, p3, p4, p1])
    face = Part.Face(wire)
    return face.extrude(App.Vector(0, 0, height_mm))

def export_step_from_rooms(rooms_json: str, out_step: str):
    payload, px_to_mm = load_payload(rooms_json)
    rooms = payload.get("rooms", [])

    doc = App.newDocument("RoomsModel")
    objs = []

    for r in rooms:
        poly = r.get("polygon", [])
        if len(poly) < 3:
            continue

        pts = poly_to_pts(poly, px_to_mm)

        floor = make_solid_from_poly(pts, FLOOR_THICK_MM)
        o_floor = doc.addObject("Part::Feature", f"floor_{r.get('id',0)}")
        o_floor.Shape = floor
        objs.append(o_floor)

            # ---- 1) 모든 방의 edge 수집 + 중복 카운트 ----
    tol_mm = 2.0  # ✅ 중복 판정 허용오차 (1~3mm 추천)
    edge_map = {}  # key -> {"a":Vec,"b":Vec,"count":int}
    for r in rooms:
        poly = r.get("polygon", [])
        if len(poly) < 3:
            continue
        pts = poly_to_pts(poly, px_to_mm)
        n = len(pts)
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            k = edge_key(a, b, tol_mm=tol_mm)
            if k not in edge_map:
                edge_map[k] = {"a": a, "b": b, "count": 1}
            else:
                edge_map[k]["count"] += 1

    # 옵션: 외벽만 만들고 싶으면 True (MVP에서는 False 추천)
    OUTER_WALLS_ONLY = False

    # ---- 2) 바닥은 기존처럼 방마다 생성 ----
    for r in rooms:
        poly = r.get("polygon", [])
        if len(poly) < 3:
            continue
        pts = poly_to_pts(poly, px_to_mm)

        floor = make_solid_from_poly(pts, FLOOR_THICK_MM)
        o_floor = doc.addObject("Part::Feature", f"floor_{r.get('id',0)}")
        o_floor.Shape = floor
        objs.append(o_floor)

    # ---- 3) 벽은 dedupe된 edge 기준으로 한 번만 생성 ----
        # ---- (추가) 오프닝 컷 솔리드 미리 만들기 ----
    # 두께는 벽보다 조금 크게 해서 확실히 관통시키기
    OPEN_CUT_THICK = WALL_THICK_MM * 1.6
    cut_solids = []
    for (a, b) in opening_segs:
        cut = make_wall_from_edge(a, b, OPEN_CUT_THICK, WALL_HEIGHT_MM)
        if cut:
            cut_solids.append(cut)

    # 옵션: 외벽만 만들기
    OUTER_WALLS_ONLY = False

    # ---- 3) 벽 생성 + 문 오프닝 컷 적용 ----
    for k, info in edge_map.items():
        if OUTER_WALLS_ONLY and info["count"] >= 2:
            continue

        a = info["a"]
        b = info["b"]
        wall = make_wall_from_edge(a, b, WALL_THICK_MM, WALL_HEIGHT_MM)
        if wall is None:
            continue

        # (추가) 컷 후보와 XY bbox가 겹치면 cut 적용
        wall_bb = bbox_xy(wall)
        for cut in cut_solids:
            if bbox_overlap_xy(wall_bb, bbox_xy(cut)):
                try:
                    wall = wall.cut(cut)
                except Exception:
                    pass

        tag = "outer" if info["count"] == 1 else "shared"
        o_wall = doc.addObject("Part::Feature", f"wall_{tag}")
        o_wall.Shape = wall
        objs.append(o_wall)

    # ---- (추가) 문 오프닝 후보 수집 ----
    opening_segs = []  # [(a,b), ...] in mm
    for r in rooms:
        poly = r.get("polygon", [])
        if len(poly) < 3:
            continue
        pts = poly_to_pts(poly, px_to_mm)
        opening_segs.extend(detect_door_openings_from_notches(pts, WALL_THICK_MM))


    doc.recompute()

    shape = None
    for o in objs:
        shape = o.Shape if shape is None else shape.fuse(o.Shape)

    model = doc.addObject("Part::Feature", "ModelFused")
    model.Shape = shape
    doc.recompute()

    Part.export([model], out_step)
    print("saved:", out_step)

if __name__ == "__main__":
    rooms_json = os.environ.get("ROOMS_JSON", r"out\page0_rooms.json")
    out_step = os.environ.get("OUT_STEP", r"out\result.step")
    export_step_from_rooms(rooms_json, out_step)
