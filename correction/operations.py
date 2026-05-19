import uuid
from typing import Dict, Any, List, Optional, Tuple
from domain.models import RoomKind, DamageType, Severity
from correction.patch import CorrectionPatch


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _find_room(payload: Dict[str, Any], room_id: int) -> Optional[Dict[str, Any]]:
    for r in payload.get("rooms", []):
        if r.get("id") == room_id:
            return r
    return None


def _find_wall(payload: Dict[str, Any], wall_id: int) -> Optional[Dict[str, Any]]:
    walls = payload.get("walls", [])
    for w in walls:
        if isinstance(w, dict) and w.get("id") == wall_id:
            return w
    # fallback: index-based (레거시)
    if 0 <= wall_id < len(walls):
        return walls[wall_id]
    return None


def _next_id(items: List[Dict[str, Any]], key: str = "id") -> int:
    if not items:
        return 0
    return max(item.get(key, 0) for item in items) + 1


def _make_patch(operation: str, target_id, before: dict, after: dict, author: str = "operator") -> CorrectionPatch:
    return CorrectionPatch(
        id=str(uuid.uuid4()),
        operation=operation,
        target_id=target_id,
        before=before,
        after=after,
        author=author,
    )


# ================================================================
# 1. change_room_type — 방 종류 변경 (기존)
# ================================================================

def change_room_type(
    payload: Dict[str, Any],
    room_id: int,
    new_kind: RoomKind,
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """방의 종류(kind)를 변경"""
    room = _find_room(payload, room_id)
    if not room:
        return None

    before_kind = room.get("kind", "UNKNOWN")
    new_kind_str = new_kind.value if hasattr(new_kind, "value") else str(new_kind)

    if before_kind == new_kind_str:
        return None

    patch = _make_patch("change_room_type", room_id, {"kind": before_kind}, {"kind": new_kind_str}, author)
    room["kind"] = new_kind_str
    return patch


# ================================================================
# 2. move_wall — 벽 위치 이동 (기존, 정비)
# ================================================================

def move_wall(
    payload: Dict[str, Any],
    wall_id: int,
    new_p1: Dict[str, float],
    new_p2: Dict[str, float],
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """벽의 양 끝점 위치를 이동"""
    walls = payload.get("walls", [])
    if wall_id < 0 or wall_id >= len(walls):
        return None

    wall = walls[wall_id]

    if isinstance(wall, dict):
        before = {"p1": wall.get("p1", {}), "p2": wall.get("p2", {})}
        after = {"p1": new_p1, "p2": new_p2}
        wall["p1"] = new_p1
        wall["p2"] = new_p2
    elif isinstance(wall, (list, tuple)) and len(wall) >= 4:
        before = {"x1": wall[0], "y1": wall[1], "x2": wall[2], "y2": wall[3]}
        after = {"x1": new_p1["x"], "y1": new_p1["y"], "x2": new_p2["x"], "y2": new_p2["y"]}
        wall[0], wall[1] = new_p1["x"], new_p1["y"]
        wall[2], wall[3] = new_p2["x"], new_p2["y"]
    else:
        return None

    return _make_patch("move_wall", wall_id, before, after, author)


# ================================================================
# 3. add_wall — 벽 추가
# ================================================================

def add_wall(
    payload: Dict[str, Any],
    p1: Dict[str, float],
    p2: Dict[str, float],
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """새 벽 세그먼트 추가"""
    walls = payload.get("walls", [])
    new_id = _next_id(walls)

    new_wall = {
        "id": new_id,
        "p1": p1,
        "p2": p2,
        "kind": "STRUCTURAL",
        "source": "manual",
    }
    walls.append(new_wall)
    payload["walls"] = walls
    payload["walls_count"] = len(walls)

    return _make_patch("add_wall", new_id, {}, new_wall, author)


# ================================================================
# 4. delete_wall — 벽 삭제
# ================================================================

def delete_wall(
    payload: Dict[str, Any],
    wall_id: int,
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """벽 세그먼트 삭제"""
    walls = payload.get("walls", [])
    target = None
    target_idx = None

    for i, w in enumerate(walls):
        wid = w.get("id", i) if isinstance(w, dict) else i
        if wid == wall_id:
            target = w
            target_idx = i
            break

    if target is None:
        return None

    before = dict(target) if isinstance(target, dict) else {"data": target}
    walls.pop(target_idx)
    payload["walls"] = walls
    payload["walls_count"] = len(walls)

    return _make_patch("delete_wall", wall_id, before, {}, author)


# ================================================================
# 5. merge_rooms — 두 방을 하나로 합병
# ================================================================

def merge_rooms(
    payload: Dict[str, Any],
    room_id_a: int,
    room_id_b: int,
    merged_kind: Optional[str] = None,
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """
    두 방을 합병. room_b를 삭제하고 room_a의 영역을 확장.
    합병된 방의 polygon은 두 방의 bbox를 감싸는 사각형으로 단순화.
    """
    room_a = _find_room(payload, room_id_a)
    room_b = _find_room(payload, room_id_b)
    if not room_a or not room_b:
        return None
    if room_id_a == room_id_b:
        return None

    before = {
        "room_a": {"id": room_id_a, "kind": room_a.get("kind"), "polygon": room_a.get("polygon", [])},
        "room_b": {"id": room_id_b, "kind": room_b.get("kind"), "polygon": room_b.get("polygon", [])},
    }

    # 합병: 두 polygon의 bounding box로 단순 합성
    all_points = room_a.get("polygon", []) + room_b.get("polygon", [])
    if all_points:
        xs = [p.get("x", p.get("X", 0)) for p in all_points]
        ys = [p.get("y", p.get("Y", 0)) for p in all_points]
        merged_polygon = [
            {"x": min(xs), "y": min(ys)},
            {"x": max(xs), "y": min(ys)},
            {"x": max(xs), "y": max(ys)},
            {"x": min(xs), "y": max(ys)},
        ]
    else:
        merged_polygon = []

    area_a = float(room_a.get("area_m2", 0))
    area_b = float(room_b.get("area_m2", 0))

    room_a["polygon"] = merged_polygon
    room_a["area_m2"] = area_a + area_b
    if merged_kind:
        room_a["kind"] = merged_kind
    room_a["metadata"] = room_a.get("metadata", {})
    room_a["metadata"]["merged_from"] = [room_id_a, room_id_b]
    room_a["metadata"]["source"] = "manual_merge"

    # room_b 삭제
    rooms = payload.get("rooms", [])
    payload["rooms"] = [r for r in rooms if r.get("id") != room_id_b]
    payload["rooms_count"] = len(payload["rooms"])

    after = {
        "merged_room": {"id": room_id_a, "kind": room_a.get("kind"), "polygon": merged_polygon},
        "deleted_room_id": room_id_b,
    }

    return _make_patch("merge_rooms", f"{room_id_a}+{room_id_b}", before, after, author)


# ================================================================
# 6. split_room — 방을 둘로 분할
# ================================================================

def split_room(
    payload: Dict[str, Any],
    room_id: int,
    split_axis: str = "vertical",
    split_ratio: float = 0.5,
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """
    방을 수직(vertical) 또는 수평(horizontal)으로 분할.
    split_ratio: 0.0~1.0, 분할 위치 비율.
    """
    room = _find_room(payload, room_id)
    if not room:
        return None

    polygon = room.get("polygon", [])
    if len(polygon) < 3:
        return None

    # bbox 기반 분할
    xs = [float(p.get("x", 0)) for p in polygon]
    ys = [float(p.get("y", 0)) for p in polygon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    before = {"id": room_id, "polygon": polygon, "kind": room.get("kind")}

    rooms = payload.get("rooms", [])
    new_id = _next_id(rooms)

    if split_axis == "vertical":
        split_x = min_x + (max_x - min_x) * split_ratio
        poly_a = [{"x": min_x, "y": min_y}, {"x": split_x, "y": min_y},
                   {"x": split_x, "y": max_y}, {"x": min_x, "y": max_y}]
        poly_b = [{"x": split_x, "y": min_y}, {"x": max_x, "y": min_y},
                   {"x": max_x, "y": max_y}, {"x": split_x, "y": max_y}]
    else:
        split_y = min_y + (max_y - min_y) * split_ratio
        poly_a = [{"x": min_x, "y": min_y}, {"x": max_x, "y": min_y},
                   {"x": max_x, "y": split_y}, {"x": min_x, "y": split_y}]
        poly_b = [{"x": min_x, "y": split_y}, {"x": max_x, "y": split_y},
                   {"x": max_x, "y": max_y}, {"x": min_x, "y": max_y}]

    # 기존 방을 poly_a로 축소
    original_area = float(room.get("area_m2", 0))
    room["polygon"] = poly_a
    room["area_m2"] = original_area * split_ratio
    room["metadata"] = room.get("metadata", {})
    room["metadata"]["source"] = "manual_split"

    # 새 방 생성
    new_room = {
        "id": new_id,
        "kind": room.get("kind", "unknown"),
        "polygon": poly_b,
        "area_m2": original_area * (1 - split_ratio),
        "metadata": {"source": "manual_split", "split_from": room_id},
    }
    rooms.append(new_room)
    payload["rooms_count"] = len(rooms)

    after = {
        "room_a": {"id": room_id, "polygon": poly_a},
        "room_b": {"id": new_id, "polygon": poly_b},
    }

    return _make_patch("split_room", room_id, before, after, author)


# ================================================================
# 7. move_opening — 개구부(문/창) 위치 이동
# ================================================================

def move_opening(
    payload: Dict[str, Any],
    room_id: int,
    opening_idx: int,
    new_p1: Dict[str, float],
    new_p2: Dict[str, float],
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """방에 속한 개구부의 위치를 이동"""
    room = _find_room(payload, room_id)
    if not room:
        return None

    openings = room.get("openings", [])
    if opening_idx < 0 or opening_idx >= len(openings):
        return None

    opening = openings[opening_idx]
    before = {"p1": opening.get("p1", {}), "p2": opening.get("p2", {})}
    opening["p1"] = new_p1
    opening["p2"] = new_p2

    after = {"p1": new_p1, "p2": new_p2}
    return _make_patch("move_opening", f"room{room_id}_opening{opening_idx}", before, after, author)


# ================================================================
# 8. place_leak_source — 누수 소스 배치 (Phase 5 연동)
# ================================================================

def place_leak_source(
    payload: Dict[str, Any],
    point: Dict[str, float],
    room_id: Optional[int] = None,
    description: str = "",
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """인시던트 페이로드에 누수 소스 추가"""
    incident = payload.get("incident", {})
    sources = incident.get("leak_sources", [])

    new_source = {
        "point": point,
        "room_id": room_id,
        "confidence": 1.0,  # 수동 배치는 confidence 100%
        "description": description,
        "source": "manual",
    }
    sources.append(new_source)
    incident["leak_sources"] = sources
    payload["incident"] = incident

    return _make_patch("place_leak_source", len(sources) - 1, {}, new_source, author)


# ================================================================
# 9. paint_damage_zone — 데미지 영역 추가 (Phase 5 연동)
# ================================================================

def paint_damage_zone(
    payload: Dict[str, Any],
    damage_type: str,
    severity: str,
    polygon: List[Dict[str, float]],
    room_id: Optional[int] = None,
    description: str = "",
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """인시던트 페이로드에 데미지 영역 추가"""
    incident = payload.get("incident", {})
    zones = incident.get("damage_zones", [])

    new_id = max((z.get("id", 0) for z in zones), default=0) + 1

    new_zone = {
        "id": new_id,
        "damage_type": damage_type,
        "severity": severity,
        "polygon": polygon,
        "room_id": room_id,
        "floor_level": 0,
        "surface_area_m2": 0.0,
        "description": description,
        "source": "manual",
    }
    zones.append(new_zone)
    incident["damage_zones"] = zones
    payload["incident"] = incident

    return _make_patch("paint_damage_zone", new_id, {}, new_zone, author)


# ================================================================
# 10. delete_room — 방 삭제
# ================================================================

def delete_room(
    payload: Dict[str, Any],
    room_id: int,
    author: str = "operator",
) -> Optional[CorrectionPatch]:
    """방 삭제"""
    room = _find_room(payload, room_id)
    if not room:
        return None

    before = dict(room)
    rooms = payload.get("rooms", [])
    payload["rooms"] = [r for r in rooms if r.get("id") != room_id]
    payload["rooms_count"] = len(payload["rooms"])

    return _make_patch("delete_room", room_id, before, {}, author)
