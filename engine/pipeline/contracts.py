"""
Pipeline Contracts & API Payload Schemas.
Fully synchronized with domain/models.py (Pydantic v2 SSOT).
Guarantees zero serialization mismatches across the pipeline.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from engine.domain.models import CADPrimitive3D, RoomGeometry, ComplianceCitation, FloorplanDocument

class Generate3DRequestContract(BaseModel):
    """API Request Payload for 2D-to-3D Geometry & Compliance Pipeline."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    image_base64: str = Field(pattern=r"^data:image\/(png|jpeg|webp);base64,", description="Base64 Data URI")
    project_name: Optional[str] = Field(default="AI-CAD Project", max_length=100)
    scale_hint: Optional[str] = Field(default="1:100", pattern=r"^1:\d+$")
    check_compliance: bool = Field(default=True, description="Enable Japan Building Code validation")

class Generate3DResponseContract(BaseModel):
    """API Response Payload containing 3D Primitives, Extracted Rooms, and Compliance Results."""
    model_config = ConfigDict(extra='forbid')

    status: str = Field(default="SUCCESS")
    floorplan: FloorplanDocument
    processing_time_ms: float = Field(ge=0.0)
    compliance_summary: Dict[str, Any] = Field(default_factory=dict)
