# export_step.py (FreeCAD STEP8 FINAL: rooms + walls + doors from mask OR wall-gaps)
import os
import json
import math
import traceback

from pipeline.contracts import build_export_metadata, build_processing_metadata
from pipeline.paths import resolve_output_path, resolve_project_path


def _load_json(path):
    resolved_path = resolve_project_path(path)
    with open(resolved_path, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------
# Door candidates from WALL GAPS (no mask needed)
# -----------------------------
def _derive_doors_from_wall_gaps(
    walls_px,
    *,
    tol_px=4.0,          # 같은 x/y로 묶는 허용 오차
    min_gap_px=8.0,      # 너무 작은 갭은 무시
    max_gap_px=80.0,     # 너무 큰 갭(창/외부 개구 등)은 무시(필요시 올리기)
):
    """
    walls_px: list of (x1,y1,x2,y2) in px, 거의 axis-aligned라는 전제(이미 axis filter 적용됨)
    Returns: list of door dicts:
      { "cx_px":..., "cy_px":..., "gap_px":..., "angle_deg":..., "axis":"H"|"V" }
    """
    # group horizontals by y, verticals by x
    horizontals = []
    verticals = []

    for (x1, y1, x2, y2) in walls_px:
        dx = x2 - x1
        dy = y2 - y1
        if abs(dy) <= abs(dx):  # horizontal-ish
            y = (y1 + y2) / 2.0
            a = min(x1, x2)
            b = max(x1, x2)
            horizontals.append((y, a, b))
        else:  # vertical-ish
            x = (x1 + x2) / 2.0
            a = min(y1, y2)
            b = max(y1, y2)
            verticals.append((x, a, b))

    def cluster_by_key(items, key_index=0):
        items = sorted(items, key=lambda t: t[key_index])
        clusters = []
        for it in items:
            k = it[key_index]
            if not clusters:
                clusters.append([it])
            else:
                prev_k = clusters[-1][-1][key_index]
                if abs(k - prev_k) <= tol_px:
                    clusters[-1].append(it)
                else:
                    clusters.append([it])
        return clusters

    def intervals_from_cluster(cluster, axis="H"):
        # cluster entries: (y, x1, x2) for H or (x, y1, y2) for V
        # return merged intervals list: (start,end,coord)
        coord = sum(c[0] for c in cluster) / len(cluster)
        segs = [(c[1], c[2]) for c in cluster]
        segs.sort()
        merged = []
        for s, e in segs:
            if not merged:
                merged.append([s, e])
            else:
                if s <= merged[-1][1] + tol_px:
                    merged[-1][1] = max(merged[-1][1], e)
                else:
                    merged.append([s, e])
        return coord, [(m[0], m[1]) for m in merged]

    doors = []

    # Horizontal gaps => vertical door opening (cut angle 0 along x)
    for cl in cluster_by_key(horizontals, 0):
        y, ints = intervals_from_cluster(cl, "H")
        if len(ints) < 2:
            continue
        for (s1, e1), (s2, e2) in zip(ints, ints[1:]):
            gap = s2 - e1
            if gap < min_gap_px or gap > max_gap_px:
                continue
            cx = (e1 + s2) / 2.0
            cy = y
            doors.append({"cx_px": cx, "cy_px": cy, "gap_px": gap, "angle_deg": 0.0, "axis": "H"})

    # Vertical gaps => horizontal door opening (cut angle 90 along y? actually along wall direction => 90 deg)
    for cl in cluster_by_key(verticals, 0):
        x, ints = intervals_from_cluster(cl, "V")
        if len(ints) < 2:
            continue
        for (s1, e1), (s2, e2) in zip(ints, ints[1:]):
            gap = s2 - e1
            if gap < min_gap_px or gap > max_gap_px:
                continue
            cx = x
            cy = (e1 + s2) / 2.0
            doors.append({"cx_px": cx, "cy_px": cy, "gap_px": gap, "angle_deg": 90.0, "axis": "V"})

    return doors


def export_step_final(
    rooms_payload,
    *,
    graph_path,
    walls_path,
    door_mask_png,
    out_step,
    out_meta,
    px_to_mm=5.0,
    wall_height_mm=2400.0,
    wall_thickness_mm=120.0,
    door_clearance_mm=2100.0,
    door_len_margin_mm=140.0,     # 문 폭 여유
    cut_thickness_mul=2.6,        # 벽 관통 보장
):
    import FreeCAD
    import Part

    out_step = str(resolve_output_path(out_step))
    out_meta = str(resolve_output_path(out_meta))
    if graph_path:
        graph_path = str(resolve_project_path(graph_path))
    walls_path = str(resolve_project_path(walls_path))
    if door_mask_png:
        door_mask_png = str(resolve_project_path(door_mask_png))

    doc = FreeCAD.newDocument("Rooms")

    graph = _load_json(graph_path) if (graph_path and os.path.exists(graph_path)) else {}
    rooms_src = rooms_payload.get("rooms", [])
    if not isinstance(rooms_src, list):
        rooms_src = []

    walls_meta = []
    doors_meta = []
    params = {
        "px_to_mm": float(px_to_mm),
        "wall_height_mm": float(wall_height_mm),
        "wall_thickness_mm": float(wall_thickness_mm),
        "door_clearance_mm": float(door_clearance_mm),
        "door_len_margin_mm": float(door_len_margin_mm),
        "cut_thickness_mul": float(cut_thickness_mul),
        "door_mask_png": door_mask_png,
        "walls_path": walls_path,
        "door_source": None,
    }

    created_objects = []
    wall_objects = []

    # -----------------
    # Rooms geometry
    # -----------------
    for r in rooms_src:
        poly = r.get("polygon", [])
        if not isinstance(poly, list) or len(poly) < 3:
            continue
        try:
            pts = [FreeCAD.Vector(float(p["x"]) * px_to_mm, float(p["y"]) * px_to_mm, 0.0) for p in poly]
            pts.append(pts[0])
            wire = Part.makePolygon(pts)
            face = Part.Face(wire)
            solid = face.extrude(FreeCAD.Vector(0, 0, float(wall_height_mm)))
        except Exception:
            continue

        obj = doc.addObject("Part::Feature", "Room_%d" % int(r.get("id", 0)))
        obj.Shape = solid
        created_objects.append(obj)

    # -----------------
    # Walls geometry
    # -----------------
    walls_payload = _load_json(walls_path)
    wall_lines = walls_payload.get("walls", [])

    walls_px = []
    for i, seg in enumerate(wall_lines):
        if not isinstance(seg, (list, tuple)) or len(seg) < 4:
            continue
        x1, y1, x2, y2 = map(float, seg[:4])
        walls_px.append((x1, y1, x2, y2))

        dx = (x2 - x1) * px_to_mm
        dy = (y2 - y1) * px_to_mm
        L = (dx * dx + dy * dy) ** 0.5
        if L < 1e-6:
            continue

        ang = math.degrees(math.atan2(dy, dx))

        shape = Part.makeBox(float(L), float(wall_thickness_mm), float(wall_height_mm))
        shape.translate(FreeCAD.Vector(0, -float(wall_thickness_mm) / 2.0, 0))
        shape.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), float(ang))
        shape.translate(FreeCAD.Vector(float(x1) * px_to_mm, float(y1) * px_to_mm, 0))

        wobj = doc.addObject("Part::Feature", "Wall_%d" % i)
        wobj.Shape = shape
        created_objects.append(wobj)
        wall_objects.append(wobj)

        walls_meta.append({"id": int(i), "x1_px": x1, "y1_px": y1, "x2_px": x2, "y2_px": y2})

    # -----------------
    # Doors: Prefer mask if it exists AND not empty
    # If empty -> derive from wall gaps
    # -----------------
    doors = []
    mask_nonzero = 0

    if door_mask_png and os.path.exists(door_mask_png):
        try:
            from PIL import Image
            import numpy as np
            a = np.array(Image.open(door_mask_png).convert("L"))
            mask_nonzero = int((a > 0).sum())
        except Exception:
            mask_nonzero = 0

    if mask_nonzero > 0:
        # If later you fix mask, you can implement mask-based extraction here.
        # For now, we still fall back to wall-gaps because it's deterministic.
        params["door_source"] = "mask_present_but_wallgap_used"
        doors = _derive_doors_from_wall_gaps(walls_px)
    else:
        params["door_source"] = "wall_gaps"
        doors = _derive_doors_from_wall_gaps(walls_px)

    print("[STEP8] door_source:", params["door_source"], "mask_nonzero=", mask_nonzero)
    print("[STEP8] door candidates from wall gaps:", len(doors))

    cut_thickness = float(wall_thickness_mm) * float(cut_thickness_mul)
    cut_height = float(min(door_clearance_mm, wall_height_mm))

    applied = 0
    for di, d in enumerate(doors):
        cx_px = float(d["cx_px"])
        cy_px = float(d["cy_px"])
        gap_px = float(d["gap_px"])
        ang_deg = float(d["angle_deg"])

        door_len_mm = gap_px * px_to_mm + float(door_len_margin_mm)
        if door_len_mm < 300.0:
            door_len_mm = 300.0

        cutter = Part.makeBox(float(door_len_mm), float(cut_thickness), float(cut_height))
        cutter.translate(FreeCAD.Vector(-float(door_len_mm) / 2.0, -float(cut_thickness) / 2.0, 0.0))
        cutter.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), float(ang_deg))
        cutter.translate(FreeCAD.Vector(cx_px * px_to_mm, cy_px * px_to_mm, 0.0))

        for wobj in wall_objects:
            try:
                wobj.Shape = wobj.Shape.cut(cutter)
            except Exception:
                pass

        doors_meta.append({
            "id": int(di),
            "source": params["door_source"],
            "center_px": {"x": cx_px, "y": cy_px},
            "gap_px": gap_px,
            "angle_deg": ang_deg,
            "door_len_mm": float(door_len_mm),
            "cut_thickness_mm": float(cut_thickness),
            "cut_height_mm": float(cut_height),
            "axis": d.get("axis"),
        })
        applied += 1

    print("[STEP8] door cuts applied:", applied)

    doc.recompute()

    meta = build_export_metadata(
        page_index=int(rooms_payload.get("page_index", rooms_payload.get("page", 0))),
        rooms=rooms_src,
        walls=walls_meta,
        doors=doors_meta,
        edges=graph.get("edges", []) if isinstance(graph, dict) else [],
        params=params,
        source=rooms_payload.get("source") if isinstance(rooms_payload.get("source"), dict) else None,
        incident=rooms_payload.get("incident") if isinstance(rooms_payload.get("incident"), dict) else None,
        processing=build_processing_metadata(
            "export_step",
            extra={
                "graph_path": graph_path,
                "walls_path": walls_path,
                "door_mask_nonzero": mask_nonzero,
                "rooms_count": len(rooms_src),
            },
        ),
        artifacts={"step_path": out_step, "meta_path": out_meta},
    )

    Part.export(created_objects, out_step)
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    try:
        FreeCAD.closeDocument(doc.Name)
    except Exception:
        pass


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, ".."))
    out_dir = os.path.join(root, "out")
    os.makedirs(out_dir, exist_ok=True)

    log_path = os.path.join(out_dir, "step8_debug.txt")

    def log(msg):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")

    try:
        rooms_json = os.path.join(out_dir, "page0_rooms.json")
        graph_json = os.path.join(out_dir, "room_graph_page0.json")
        walls_json = os.path.join(out_dir, "walls_page0.json")
        door_mask = os.path.join(out_dir, "door_mask_page0.png")

        out_step = os.path.join(out_dir, "result.step")
        out_meta = os.path.join(out_dir, "result.meta.json")

        log("=== STEP8 START ===")
        log("rooms_json=" + rooms_json + " exists=" + str(os.path.exists(rooms_json)))
        log("walls_json=" + walls_json + " exists=" + str(os.path.exists(walls_json)))
        log("door_mask=" + door_mask + " exists=" + str(os.path.exists(door_mask)))

        if not os.path.exists(rooms_json):
            raise RuntimeError("missing rooms json: " + rooms_json)
        if not os.path.exists(walls_json):
            raise RuntimeError("missing walls json: " + walls_json)

        rooms_payload = _load_json(rooms_json)
        if not isinstance(rooms_payload, dict):
            raise RuntimeError("invalid rooms payload: " + rooms_json)

        export_step_final(
            rooms_payload,
            graph_path=graph_json,
            walls_path=walls_json,
            door_mask_png=door_mask,
            out_step=out_step,
            out_meta=out_meta,
            px_to_mm=5.0,
            wall_height_mm=2400.0,
            wall_thickness_mm=120.0,
            door_clearance_mm=2100.0,
            door_len_margin_mm=140.0,
            cut_thickness_mul=2.6,
        )

        log("DONE: result.step/result.meta.json written")

    except Exception as e:
        log("!!! EXCEPTION !!!")
        log(str(e))
        log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
