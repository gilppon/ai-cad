from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

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
    UNKNOWN = "unknown"

@dataclass
class Point:
    x: float
    y: float

@dataclass
class Room:
    id: int
    polygon: List[Point]
    kind: RoomKind = RoomKind.UNKNOWN
    area_px2: float = 0.0
    area_m2: float = 0.0
    height_mm: float = 2400.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Wall:
    id: int
    p1: Point
    p2: Point
    thickness_px: float = 10.0
    kind: str = "STRUCTURAL" # STRUCTURAL, PARTITION, etc.

@dataclass
class LeakCase:
    case_id: str
    customer_name: Optional[str] = None
    address: Optional[str] = None
    incident_date: Optional[str] = None
    description: Optional[str] = None
    rooms: List[Room] = field(default_factory=list)
    walls: List[Wall] = field(default_factory=list)
    damage_zones: List[Dict[str, Any]] = field(default_factory=list)
