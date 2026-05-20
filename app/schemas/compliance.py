# app/schemas/compliance.py — Pydantic 스키마 (BIM Compliance Checksheet API)
from pydantic import BaseModel, Field
from typing import List, Optional


class BIMComplianceCheckItem(BaseModel):
    article_no: str = Field(..., description="일본 건축기준법 조항 번호 (예: 第28条)")
    item_name_jp: str = Field(..., description="검증 항목명 (예: 居室の採光及び換気)")
    standard_value: str = Field(..., description="법령상 기준치 (예: 窓面積 / 居室面積 >= 1/7)")
    calculated_value: str = Field(..., description="3D IFC 파싱 및 기하 연산 값 (예: 1/5.8)")
    status: str = Field(..., description="적합성 판정 결과: PASS(O), FAIL(X)")
    inspector_comment: str = Field(..., description="설계자 종합 소견")


class BIMComplianceChecksheet(BaseModel):
    project_id: str
    building_name: str
    chief_designer: str
    license_number: str  # 1급 건축사 면허번호 (一級建築士 登録番号)
    check_items: List[BIMComplianceCheckItem]
    overall_judgment: str  # "適合" 또는 "不適合"
    digital_seal_url: Optional[str] = None  # 설계자 인장 이미지 URL (또는 로컬 업로드 인장 경로)
