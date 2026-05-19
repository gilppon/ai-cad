# scene/incident_mapper.py — 인시던트 → 기하학 씬 매핑 엔진
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from domain.models import (
    LeakCase, LeakSource, DamageZone, SuspectedPath,
    IncidentAnnotation, Point,
)
from scene.serializer import (
    leak_case_to_dict,
    _leak_source_to_dict,
    _damage_zone_to_dict,
    _suspected_path_to_dict,
    _annotation_to_dict,
)


# ----------------------------------------------------------------
# 공간 유틸리티 (Point-in-Polygon, Ray Casting)
# ----------------------------------------------------------------

def _point_in_polygon(px: float, py: float, polygon: List[Dict[str, Any]]) -> bool:
    """
    Ray-casting 알고리즘으로 점이 다각형 안에 있는지 판별.
    polygon은 [{"x": ..., "y": ...}, ...] 형식.
    """
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    j = n - 1
    for i in range(n):
        xi = float(polygon[i].get("x", 0))
        yi = float(polygon[i].get("y", 0))
        xj = float(polygon[j].get("x", 0))
        yj = float(polygon[j].get("y", 0))

        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i

    return inside


def _find_room_for_point(
    px: float, py: float, rooms: List[Dict[str, Any]]
) -> Optional[int]:
    """점 좌표가 속하는 room_id를 찾아 반환. 못 찾으면 None."""
    for room in rooms:
        polygon = room.get("polygon", [])
        if _point_in_polygon(px, py, polygon):
            return room.get("id")
    return None


def _polygon_overlaps_room(
    damage_polygon: List[Dict[str, Any]], room_polygon: List[Dict[str, Any]]
) -> bool:
    """
    damage zone의 폴리곤이 room 폴리곤과 겹치는지 간이 판별.
    damage zone의 꼭짓점 중 하나라도 room 안에 있으면 True.
    """
    for p in damage_polygon:
        if _point_in_polygon(float(p.get("x", 0)), float(p.get("y", 0)), room_polygon):
            return True
    return False


# ----------------------------------------------------------------
# 핵심: 인시던트 → 씬 매핑
# ----------------------------------------------------------------

def map_incident_to_scene(
    case: LeakCase,
    geometry_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    LeakCase의 인시던트 데이터를 geometry_payload에 직접 매핑하여 합성.

    동작:
    1. leak_sources → rooms 좌표 공간에서 point 매핑, room_id 자동 바인딩
    2. damage_zones → room polygon 교차 검증, room_id 자동 매핑
    3. suspected_paths → 경유 room_ids 자동 계산
    4. annotations → anchor_point 기준 room_id 자동 바인딩

    Returns:
        인시던트가 합성된 geometry_payload (원본 수정하지 않고 복사본 반환)
    """
    import copy
    result = copy.deepcopy(geometry_payload)

    rooms = result.get("rooms", [])

    # 1. Leak Sources — room_id 자동 바인딩
    mapped_sources = []
    for src in case.leak_sources:
        src_dict = _leak_source_to_dict(src)
        if src.room_id is None:
            auto_room = _find_room_for_point(src.point.x, src.point.y, rooms)
            src_dict["room_id"] = auto_room
            src_dict["auto_mapped"] = True
        mapped_sources.append(src_dict)

    # 2. Damage Zones — room_id 자동 매핑 + 영향 받는 방 목록
    mapped_zones = []
    for dz in case.damage_zones:
        dz_dict = _damage_zone_to_dict(dz)
        affected_rooms = []

        dz_poly = dz_dict.get("polygon", [])
        for room in rooms:
            room_poly = room.get("polygon", [])
            if _polygon_overlaps_room(dz_poly, room_poly):
                affected_rooms.append(room.get("id"))

        # room_id가 미지정이면 첫 번째 겹치는 방으로 바인딩
        if dz.room_id is None and affected_rooms:
            dz_dict["room_id"] = affected_rooms[0]
            dz_dict["auto_mapped"] = True

        dz_dict["affected_room_ids"] = affected_rooms
        mapped_zones.append(dz_dict)

    # 3. Suspected Paths — 경유 room_ids 자동 계산
    mapped_paths = []
    for sp in case.suspected_paths:
        sp_dict = _suspected_path_to_dict(sp)
        if not sp.room_ids:
            # 각 waypoint가 어떤 방에 속하는지 계산
            auto_room_ids = []
            for wp in sp.waypoints:
                rid = _find_room_for_point(wp.x, wp.y, rooms)
                if rid is not None and rid not in auto_room_ids:
                    auto_room_ids.append(rid)
            sp_dict["room_ids"] = auto_room_ids
            sp_dict["auto_mapped"] = True
        mapped_paths.append(sp_dict)

    # 4. Annotations — room_id 자동 바인딩
    mapped_annotations = []
    for ann in case.annotations:
        ann_dict = _annotation_to_dict(ann)
        if ann.anchor_room_id is None:
            auto_room = _find_room_for_point(
                ann.anchor_point.x, ann.anchor_point.y, rooms
            )
            ann_dict["anchor_room_id"] = auto_room
            ann_dict["auto_mapped"] = True
        mapped_annotations.append(ann_dict)

    # 5. incident 서브 페이로드 합성
    result["incident"] = {
        "case_id": case.case_id,
        "customer_name": case.customer_name,
        "address": case.address,
        "incident_date": case.incident_date,
        "description": case.description,
        "version": case.version,
        "leak_sources": mapped_sources,
        "damage_zones": mapped_zones,
        "suspected_paths": mapped_paths,
        "annotations": mapped_annotations,
    }

    return result


# ----------------------------------------------------------------
# 매핑 검증
# ----------------------------------------------------------------

def validate_incident_mapping(scene_payload: Dict[str, Any]) -> List[str]:
    """
    인시던트 매핑의 유효성을 검증.
    문제가 있으면 경고 메시지 목록 반환, 문제 없으면 빈 리스트.
    """
    warnings: List[str] = []
    incident = scene_payload.get("incident", {})

    if not incident:
        return warnings  # 인시던트 없으면 검증할 것 없음

    rooms = scene_payload.get("rooms", [])
    room_ids = {r.get("id") for r in rooms}

    # leak_sources 검증
    for i, src in enumerate(incident.get("leak_sources", [])):
        rid = src.get("room_id")
        if rid is not None and rid not in room_ids:
            warnings.append(f"leak_source[{i}]: room_id={rid} does not exist in rooms")
        if rid is None:
            warnings.append(f"leak_source[{i}]: not mapped to any room")

    # damage_zones 검증
    for i, dz in enumerate(incident.get("damage_zones", [])):
        rid = dz.get("room_id")
        if rid is not None and rid not in room_ids:
            warnings.append(f"damage_zone[{i}]: room_id={rid} does not exist in rooms")
        affected = dz.get("affected_room_ids", [])
        if not affected:
            warnings.append(f"damage_zone[{i}]: no affected rooms found")

    # suspected_paths 검증
    for i, sp in enumerate(incident.get("suspected_paths", [])):
        path_rooms = sp.get("room_ids", [])
        if len(path_rooms) < 2:
            warnings.append(f"suspected_path[{i}]: path crosses fewer than 2 rooms")
        for rid in path_rooms:
            if rid not in room_ids:
                warnings.append(f"suspected_path[{i}]: room_id={rid} does not exist")

    return warnings


# ----------------------------------------------------------------
# 다실 확산 분석
# ----------------------------------------------------------------

def compute_damage_spread(
    case: LeakCase,
    geometry_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    누수의 다실/다층 확산 범위를 분석.

    Returns:
        {
            "total_affected_rooms": int,
            "affected_room_ids": [int, ...],
            "affected_floor_levels": [int, ...],
            "spread_summary": str,
            "per_room_damage": {room_id: {"damage_types": [...], "max_severity": str}}
        }
    """
    rooms = geometry_payload.get("rooms", [])

    affected_rooms: Dict[int, Dict[str, Any]] = {}
    affected_floors: set = set()

    for dz in case.damage_zones:
        dz_poly = [{"x": p.x, "y": p.y} for p in dz.polygon]

        for room in rooms:
            room_poly = room.get("polygon", [])
            rid = room.get("id")
            if _polygon_overlaps_room(dz_poly, room_poly):
                if rid not in affected_rooms:
                    affected_rooms[rid] = {"damage_types": [], "max_severity": "low"}

                dtype = dz.damage_type.value
                if dtype not in affected_rooms[rid]["damage_types"]:
                    affected_rooms[rid]["damage_types"].append(dtype)

                # 심각도 비교 (low < medium < high < critical)
                severity_order = ["low", "medium", "high", "critical"]
                current_max = affected_rooms[rid]["max_severity"]
                new_sev = dz.severity.value
                if severity_order.index(new_sev) > severity_order.index(current_max):
                    affected_rooms[rid]["max_severity"] = new_sev

        affected_floors.add(dz.floor_level)

    total = len(affected_rooms)
    spread = "none"
    if total == 1:
        spread = "single_room"
    elif total <= 3:
        spread = "multi_room"
    elif total > 3:
        spread = "extensive"

    if len(affected_floors) > 1:
        spread = f"multi_floor_{spread}"

    return {
        "total_affected_rooms": total,
        "affected_room_ids": sorted(affected_rooms.keys()),
        "affected_floor_levels": sorted(affected_floors),
        "spread_summary": spread,
        "per_room_damage": affected_rooms,
    }
