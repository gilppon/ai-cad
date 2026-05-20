# app/schemas/incident.py — Pydantic 스키마 (Incident Semantics API)
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class PointSchema(BaseModel):
    x: float
    y: float


class LeakSourceSchema(BaseModel):
    point: PointSchema
    room_id: Optional[int] = None
    confidence: float = 0.0
    description: str = ""


class DamageZoneSchema(BaseModel):
    id: int
    damage_type: str  # "ceiling", "wall_surface", "floor", "pipe"
    severity: str     # "low", "medium", "high", "critical"
    polygon: List[PointSchema] = []
    room_id: Optional[int] = None
    floor_level: int = 0
    surface_area_m2: float = 0.0
    description: str = ""
    photos: List[str] = []


class SuspectedPathSchema(BaseModel):
    waypoints: List[PointSchema] = []
    room_ids: List[int] = []
    description: str = ""


class AnnotationCreateRequest(BaseModel):
    anchor_point: PointSchema
    anchor_room_id: Optional[int] = None
    text: str = ""
    category: str = "note"
    attached_photo: Optional[str] = None


class IncidentCreateRequest(BaseModel):
    case_id: str
    customer_name: Optional[str] = None
    address: Optional[str] = None
    incident_date: Optional[str] = None
    description: Optional[str] = None
    leak_sources: List[LeakSourceSchema] = []
    damage_zones: List[DamageZoneSchema] = []
    suspected_paths: List[SuspectedPathSchema] = []
    annotations: List[AnnotationCreateRequest] = []


class IncidentResponse(BaseModel):
    case_id: str
    version: int
    created_at: str
    updated_at: str
    customer_name: Optional[str] = None
    leak_sources_count: int = 0
    damage_zones_count: int = 0
    annotations_count: int = 0
    data: Dict[str, Any] = {}


class AnnotationResponse(BaseModel):
    id: int
    anchor_point: PointSchema
    anchor_room_id: Optional[int] = None
    text: str
    category: str
    attached_photo: Optional[str] = None
    created_at: str = ""


class DamageSpreadResponse(BaseModel):
    total_affected_rooms: int
    affected_room_ids: List[int]
    affected_floor_levels: List[int]
    spread_summary: str
    per_room_damage: Dict[str, Any] = {}
    

class IncidentPinUpdateRequest(BaseModel):
    pin_type: str = Field("leak_source", description="leak_source, damage_zone, 또는 annotation")
    target_room_id: Optional[int] = None
    coordinate: PointSchema
    media_urls: List[str] = Field(default_factory=list, description="연결된 실사 이미지 CDN URL 목록")
    comment: str = Field("", description="현장 추가 코멘트 및 상태 소견")

