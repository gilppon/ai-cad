# app/schemas/quotation.py — Pydantic 스키마 (BIM 견적서 API, SP3/Q-1)
from pydantic import BaseModel, Field
from typing import Any, Dict, List


class QuantityLineModel(BaseModel):
    """물리 수량 라인 - 원천 엔티티 역추적 가능 (数量取合書 정신)."""
    basis: str = Field(..., description="물리량 기준 코드 (FLOOR-AREA, WALL-LENGTH 등)")
    unit: str = Field(..., description="m² / m / 式")
    quantity: float = Field(..., ge=0)
    source_kind: str = Field(..., description="room | wall | opening | floor")
    source_ref: Any = Field(..., description="원천 엔티티 ID (room_id / wall_id)")
    part: str = Field("", description="부위 (RoomKind 값)")
    meta: Dict[str, Any] = Field(default_factory=dict)


class QuotationTotals(BaseModel):
    direct_cost: int = Field(..., description="直接工事費 (JPY)")
    construction_cost: int = Field(..., description="工事原価 (JPY)")
    taxable_base: int = Field(..., description="課税対象額 (JPY)")
    consumption_tax: int = Field(..., description="消費税 (JPY)")
    total_including_tax: int = Field(..., description="総工事費 税込 (JPY)")


class QuotationDocument(BaseModel):
    schema_version: str
    document_kind: str = "quotation"
    project_id: str
    issued_at: str
    currency: str = "JPY"
    price_book: Dict[str, Any]
    quantities: List[QuantityLineModel]
    breakdown: Dict[str, Any]
    totals: QuotationTotals
