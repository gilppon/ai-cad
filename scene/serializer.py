# scene/serializer.py — LeakCase ↔ JSON 완전 왕복 변환 (버전 관리 포함)
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from domain.models import (
    LeakCase, LeakSource, DamageZone, SuspectedPath,
    IncidentAnnotation, Point, DamageType, Severity,
    Floor, Room, Wall, RoomKind, Opening, OpeningKind,
    _now_iso,
)


# ----------------------------------------------------------------
# LeakCase → dict (JSON-serializable)
# ----------------------------------------------------------------

def _point_to_dict(p: Point) -> Dict[str, float]:
    return {"x": p.x, "y": p.y}


def _leak_source_to_dict(src: LeakSource) -> Dict[str, Any]:
    return {
        "point": _point_to_dict(src.point),
        "room_id": src.room_id,
        "confidence": src.confidence,
        "description": src.description,
    }


def _damage_zone_to_dict(dz: DamageZone) -> Dict[str, Any]:
    return {
        "id": dz.id,
        "damage_type": dz.damage_type.value,
        "severity": dz.severity.value,
        "polygon": [_point_to_dict(p) for p in dz.polygon],
        "room_id": dz.room_id,
        "floor_level": dz.floor_level,
        "surface_area_m2": dz.surface_area_m2,
        "description": dz.description,
        "photos": list(dz.photos),
    }


def _suspected_path_to_dict(sp: SuspectedPath) -> Dict[str, Any]:
    return {
        "waypoints": [_point_to_dict(p) for p in sp.waypoints],
        "room_ids": list(sp.room_ids),
        "description": sp.description,
    }


def _annotation_to_dict(ann: IncidentAnnotation) -> Dict[str, Any]:
    return {
        "id": ann.id,
        "anchor_point": _point_to_dict(ann.anchor_point),
        "anchor_room_id": ann.anchor_room_id,
        "text": ann.text,
        "category": ann.category,
        "attached_photo": ann.attached_photo,
        "created_at": ann.created_at,
    }


def _opening_to_dict(op: Opening) -> Dict[str, Any]:
    return {
        "id": op.id,
        "p1": _point_to_dict(op.p1),
        "p2": _point_to_dict(op.p2),
        "kind": op.kind.value,
        "width_mm": op.width_mm,
        "connected_rooms": list(op.connected_rooms),
    }


def _room_to_dict(r: Room) -> Dict[str, Any]:
    return {
        "id": r.id,
        "polygon": [_point_to_dict(p) for p in r.polygon],
        "kind": r.kind.value,
        "area_px2": r.area_px2,
        "area_m2": r.area_m2,
        "height_mm": r.height_mm,
        "connected_rooms": list(r.connected_rooms),
        "openings": [_opening_to_dict(o) for o in r.openings],
        "metadata": dict(r.metadata),
    }


def _wall_to_dict(w: Wall) -> Dict[str, Any]:
    return {
        "id": w.id,
        "p1": _point_to_dict(w.p1),
        "p2": _point_to_dict(w.p2),
        "thickness_px": w.thickness_px,
        "kind": w.kind,
    }


def _floor_to_dict(f: Floor) -> Dict[str, Any]:
    return {
        "level": f.level,
        "name": f.name,
        "rooms": [_room_to_dict(r) for r in f.rooms],
        "walls": [_wall_to_dict(w) for w in f.walls],
        "elevation_mm": f.elevation_mm,
        "height_mm": f.height_mm,
        "px_to_m": f.px_to_m,
    }


def leak_case_to_dict(case: LeakCase) -> Dict[str, Any]:
    """LeakCase → 완전한 JSON-serializable dict 변환"""
    return {
        "case_id": case.case_id,
        "customer_name": case.customer_name,
        "address": case.address,
        "incident_date": case.incident_date,
        "description": case.description,
        "version": case.version,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "floors": [_floor_to_dict(f) for f in case.floors],
        "leak_sources": [_leak_source_to_dict(s) for s in case.leak_sources],
        "damage_zones": [_damage_zone_to_dict(dz) for dz in case.damage_zones],
        "suspected_paths": [_suspected_path_to_dict(sp) for sp in case.suspected_paths],
        "annotations": [_annotation_to_dict(a) for a in case.annotations],
        "compliance_checks": list(case.compliance_checks),
        "metadata": dict(case.metadata),
    }


# ----------------------------------------------------------------
# dict → LeakCase (역직렬화)
# ----------------------------------------------------------------

def _dict_to_point(d: Dict[str, Any]) -> Point:
    return Point(x=float(d["x"]), y=float(d["y"]))


def _dict_to_leak_source(d: Dict[str, Any]) -> LeakSource:
    return LeakSource(
        point=_dict_to_point(d["point"]),
        room_id=d.get("room_id"),
        confidence=float(d.get("confidence", 0.0)),
        description=str(d.get("description", "")),
    )


def _dict_to_damage_zone(d: Dict[str, Any]) -> DamageZone:
    return DamageZone(
        id=int(d["id"]),
        damage_type=DamageType(d["damage_type"]),
        severity=Severity(d["severity"]),
        polygon=[_dict_to_point(p) for p in d.get("polygon", [])],
        room_id=d.get("room_id"),
        floor_level=int(d.get("floor_level", 0)),
        surface_area_m2=float(d.get("surface_area_m2", 0.0)),
        description=str(d.get("description", "")),
        photos=list(d.get("photos", [])),
    )


def _dict_to_suspected_path(d: Dict[str, Any]) -> SuspectedPath:
    return SuspectedPath(
        waypoints=[_dict_to_point(p) for p in d.get("waypoints", [])],
        room_ids=list(d.get("room_ids", [])),
        description=str(d.get("description", "")),
    )


def _dict_to_annotation(d: Dict[str, Any]) -> IncidentAnnotation:
    return IncidentAnnotation(
        id=int(d["id"]),
        anchor_point=_dict_to_point(d["anchor_point"]),
        anchor_room_id=d.get("anchor_room_id"),
        text=str(d.get("text", "")),
        category=str(d.get("category", "note")),
        attached_photo=d.get("attached_photo"),
        created_at=str(d.get("created_at", "")),
    )


def _dict_to_opening(d: Dict[str, Any]) -> Opening:
    return Opening(
        id=int(d["id"]),
        p1=_dict_to_point(d["p1"]),
        p2=_dict_to_point(d["p2"]),
        kind=OpeningKind(d.get("kind", "door")),
        width_mm=float(d.get("width_mm", 900.0)),
        connected_rooms=list(d.get("connected_rooms", [])),
    )


def _dict_to_room(d: Dict[str, Any]) -> Room:
    return Room(
        id=int(d["id"]),
        polygon=[_dict_to_point(p) for p in d.get("polygon", [])],
        kind=RoomKind(d.get("kind", "unknown")),
        area_px2=float(d.get("area_px2", 0.0)),
        area_m2=float(d.get("area_m2", 0.0)),
        height_mm=float(d.get("height_mm", 2400.0)),
        connected_rooms=list(d.get("connected_rooms", [])),
        openings=[_dict_to_opening(o) for o in d.get("openings", [])],
        metadata=dict(d.get("metadata", {})),
    )


def _dict_to_wall(d: Dict[str, Any]) -> Wall:
    return Wall(
        id=int(d["id"]),
        p1=_dict_to_point(d["p1"]),
        p2=_dict_to_point(d["p2"]),
        thickness_px=float(d.get("thickness_px", 10.0)),
        kind=str(d.get("kind", "STRUCTURAL")),
    )


def _dict_to_floor(d: Dict[str, Any]) -> Floor:
    return Floor(
        level=int(d["level"]),
        name=str(d["name"]),
        rooms=[_dict_to_room(r) for r in d.get("rooms", [])],
        walls=[_dict_to_wall(w) for w in d.get("walls", [])],
        elevation_mm=float(d.get("elevation_mm", 0.0)),
        height_mm=float(d.get("height_mm", 3000.0)),
        px_to_m=float(d.get("px_to_m", 0.01)),
    )


def dict_to_leak_case(data: Dict[str, Any]) -> LeakCase:
    """JSON dict → LeakCase 역직렬화"""
    return LeakCase(
        case_id=str(data["case_id"]),
        customer_name=data.get("customer_name"),
        address=data.get("address"),
        incident_date=data.get("incident_date"),
        description=data.get("description"),
        version=int(data.get("version", 1)),
        created_at=str(data.get("created_at", "")),
        updated_at=str(data.get("updated_at", "")),
        floors=[_dict_to_floor(f) for f in data.get("floors", [])],
        leak_sources=[_dict_to_leak_source(s) for s in data.get("leak_sources", [])],
        damage_zones=[_dict_to_damage_zone(dz) for dz in data.get("damage_zones", [])],
        suspected_paths=[_dict_to_suspected_path(sp) for sp in data.get("suspected_paths", [])],
        annotations=[_dict_to_annotation(a) for a in data.get("annotations", [])],
        compliance_checks=list(data.get("compliance_checks", [])),
        metadata=dict(data.get("metadata", {})),
    )


# ----------------------------------------------------------------
# File I/O
# ----------------------------------------------------------------

def save_leak_case(case: LeakCase, path: str) -> None:
    """LeakCase를 JSON 파일로 저장"""
    import os
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(leak_case_to_dict(case), f, indent=2, ensure_ascii=False)


def load_leak_case(path: str) -> LeakCase:
    """JSON 파일에서 LeakCase 로드"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return dict_to_leak_case(data)
