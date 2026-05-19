from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime, timezone

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class RoomKind(Enum):
    LDK = "ldk"
    BEDROOM = "bedroom"
    CORRIDOR = "corridor"
    BATHROOM = "bathroom"
    TOILET = "toilet"
    KITCHEN = "kitchen"
    BALCONY = "balcony"
    SHAFT = "shaft"
    CLOSET = "closet"
    ENTRANCE = "entrance"
    WET = "wet"
    STORAGE = "storage"
    ROOM = "room"
    UNKNOWN = "unknown"

class DamageType(Enum):
    CEILING = "ceiling"
    WALL_SURFACE = "wall_surface"
    FLOOR = "floor"
    PIPE = "pipe"

class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class OpeningKind(Enum):
    DOOR = "door"
    WINDOW = "window"
    OPENING = "opening"

@dataclass
class Point:
    x: float
    y: float

@dataclass
class Opening:
    id: int
    p1: Point
    p2: Point
    kind: OpeningKind = OpeningKind.DOOR
    width_mm: float = 900.0
    connected_rooms: List[int] = field(default_factory=list)

@dataclass
class Room:
    id: int
    polygon: List[Point]
    kind: RoomKind = RoomKind.UNKNOWN
    area_px2: float = 0.0
    area_m2: float = 0.0
    height_mm: float = 2400.0
    connected_rooms: List[int] = field(default_factory=list)
    openings: List[Opening] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Wall:
    id: int
    p1: Point
    p2: Point
    thickness_px: float = 10.0
    kind: str = "STRUCTURAL" # STRUCTURAL, PARTITION, etc.

@dataclass
class Floor:
    level: int  # 0 for GF, 1 for 2F, etc.
    name: str
    rooms: List[Room] = field(default_factory=list)
    walls: List[Wall] = field(default_factory=list)
    elevation_mm: float = 0.0
    height_mm: float = 3000.0
    px_to_m: float = 0.01  # default 100px = 1m

@dataclass
class LeakSource:
    point: Point
    room_id: Optional[int]
    confidence: float = 0.0
    description: str = ""

@dataclass
class DamageZone:
    id: int
    damage_type: DamageType
    severity: Severity
    polygon: List[Point]
    room_id: Optional[int]
    floor_level: int = 0
    surface_area_m2: float = 0.0
    description: str = ""
    photos: List[str] = field(default_factory=list)

@dataclass
class SuspectedPath:
    waypoints: List[Point]
    room_ids: List[int]
    description: str = ""

@dataclass
class IncidentAnnotation:
    id: int
    anchor_point: Point
    anchor_room_id: Optional[int]
    text: str
    category: str = "note"
    attached_photo: Optional[str] = None
    created_at: str = ""

@dataclass
class LeakCase:
    case_id: str
    customer_name: Optional[str] = None
    address: Optional[str] = None
    incident_date: Optional[str] = None
    description: Optional[str] = None
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    floors: List[Floor] = field(default_factory=list)
    leak_sources: List[LeakSource] = field(default_factory=list)
    damage_zones: List[DamageZone] = field(default_factory=list)
    suspected_paths: List[SuspectedPath] = field(default_factory=list)
    annotations: List[IncidentAnnotation] = field(default_factory=list)
    compliance_checks: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = _now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at

    def bump_version(self):
        """버전 증가 및 updated_at 갱신"""
        self.version += 1
        self.updated_at = _now_iso()
