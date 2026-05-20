# app/schemas/correction.py — 보정 워크플로우 Pydantic 스키마
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class PointSchema(BaseModel):
    x: float
    y: float


class CorrectionOperation(BaseModel):
    """단일 보정 연산"""
    operation: str  # "change_room_type", "move_wall", "add_wall", "delete_wall",
                    # "merge_rooms", "split_room", "move_opening",
                    # "place_leak_source", "paint_damage_zone", "delete_room"
    params: Dict[str, Any] = {}
    author: str = "operator"


class CorrectionBatchRequest(BaseModel):
    """배치 보정 요청 (여러 연산을 한 세션으로)"""
    case_id: str = "default"
    operations: List[CorrectionOperation]


class CorrectionPatchResponse(BaseModel):
    id: str
    operation: str
    target_id: Any
    timestamp: str
    author: str


class CorrectionSessionResponse(BaseModel):
    session_id: str
    case_id: str
    status: str
    patch_count: int
    correction_source: str
    operation_summary: Dict[str, int] = {}
    patches: List[CorrectionPatchResponse] = []


class CorrectionHistoryResponse(BaseModel):
    sessions: List[Dict[str, Any]]
    stats: Dict[str, Any]


class OfflineSyncRequest(BaseModel):
    """오프라인 델타 벌크 동기화 요청"""
    base_version: int = Field(..., description="The version of the project when the offline actions started")
    operations: List[CorrectionOperation] = Field(..., description="The sequence of offline operations to apply")


class OfflineSyncResponse(BaseModel):
    """오프라인 델타 벌크 동기화 응답"""
    status: str
    session_id: str
    current_version: int
    patches_applied: int
    operation_summary: Dict[str, int] = {}

