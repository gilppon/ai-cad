"""
Single Source of Truth (SSOT) Domain Models.
Built strictly on Pydantic v2 with @field_validator and @model_validator for zero-overhead validation.
"""
from typing import List, Tuple, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

class CADPrimitive3D(BaseModel):
    """3D Primitive Mesh for WebGL rendering (React Three Fiber)."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    type: Literal["box", "cylinder", "sphere"]
    position: Tuple[float, float, float]
    size: Tuple[float, float, float]
    color: str = Field(default="#4f46e5", pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$")
    name: str = Field(min_length=1, max_length=100)

    @field_validator("size")
    @classmethod
    def validate_positive_dimensions(cls, v: Tuple[float, float, float]) -> Tuple[float, float, float]:
        for dim in v:
            if dim <= 0:
                raise ValueError(f"All 3D dimension sizes must be strictly positive (> 0), got: {v}")
        return v


class RoomGeometry(BaseModel):
    """Planar 2D Room Polygon extracted from PSLG topology."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    room_id: str = Field(pattern=r"^ROOM_\d{2,}$")
    room_type: Literal["living_room", "bedroom", "kitchen", "corridor", "balcony", "toilet"] = "living_room"
    vertices: List[Tuple[float, float]] = Field(min_length=3)
    area_m2: float = Field(gt=0.0)
    perimeter_m: float = Field(gt=0.0)
    window_effective_area_m2: float = Field(default=0.0, ge=0.0)
    vent_opening_area_m2: float = Field(default=0.0, ge=0.0)
    stair_width_cm: Optional[float] = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_polygon_closure(self) -> 'RoomGeometry':
        # Ensure vertices form a valid polygonal face
        if len(self.vertices) < 3:
            raise ValueError(f"A closed room polygon requires at least 3 vertices, got: {len(self.vertices)}")
        return self


class ComplianceCitation(BaseModel):
    """1:1 Citation Binding for Building Code Verification."""
    model_config = ConfigDict(frozen=True)

    rule_id: str
    law_article_id: str
    law_name: str
    hierarchical_path: str
    law_snippet: str
    category: str
    status: Literal["PASS", "FAIL", "WARNING"]
    actual_value: float
    threshold_value: float
    unit: str
    description: str
    exemption_applicable: bool
    remedy_suggestion: Optional[str] = None


class FloorplanDocument(BaseModel):
    """Root Floorplan Payload Model combining Geometry, 3D Primitives, and Compliance."""
    model_config = ConfigDict(extra='forbid')

    doc_id: str
    building_name: str = Field(default="Standard Architectural Project")
    rooms: List[RoomGeometry] = Field(default_factory=list)
    primitives: List[CADPrimitive3D] = Field(default_factory=list)
    compliance_report: Optional[List[ComplianceCitation]] = None

    @model_validator(mode="after")
    def compute_totals(self) -> 'FloorplanDocument':
        # Cross-validation: total floor area integrity check
        total_area = sum(r.area_m2 for r in self.rooms)
        if self.rooms and total_area <= 0:
            raise ValueError("Total floor area of non-empty rooms must be greater than 0")
        return self
