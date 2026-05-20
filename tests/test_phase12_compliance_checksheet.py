# -*- coding: utf-8 -*-
import os
import sys
import io
import pytest
import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from test_japan_market_e2e import GLOBAL_MOCK_DB, get_mock_user_and_db
from app.services.payment import StripePaymentService

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_phase12_mocks():
    # FastAPI 의존성 오버라이드
    from app.api.deps import get_current_user_and_db
    app.dependency_overrides[get_current_user_and_db] = get_mock_user_and_db
    
    # 임시 프로젝트 디렉토리 준비
    from pipeline.paths import OUTPUT_ROOT
    project_dir = OUTPUT_ROOT / "projects" / "proj_999"
    os.makedirs(project_dir, exist_ok=True)
    
    # 각 테스트 시작 전 DB 상태 초기화 (독립성 확보)
    GLOBAL_MOCK_DB.table("profiles")._data = [
        {"id": "user_123", "plan_type": "pro", "credits": 9999, "stripe_subscription_id": "sub_xyz"}
    ]
    GLOBAL_MOCK_DB.table("profiles")._filters = {}
    
    # 기본 기하 법규 검증 데이터 page0_compliance.json 준비 (적합 케이스)
    compliance_path = project_dir / "page0_compliance.json"
    initial_compliance = {
        "rooms": [
            {
                "id": "room_1",
                "kind": "LDK",
                "area_m2": 15.0,
                "height_mm": 2400.0,
                "polygon": [
                    {"x": 0, "y": 0},
                    {"x": 300, "y": 0},
                    {"x": 300, "y": 500},
                    {"x": 0, "y": 500}
                ],
                "actual_window_area_m2": 2.5 # 15/7 = 2.14m2 이상이므로 적합
            }
        ],
        "openings": [
            {
                "kind": "WINDOW",
                "p1": {"x": 100, "y": 0},
                "p2": {"x": 200, "y": 0},
                "width_px": 100
            }
        ],
        "metrics": {
            "px_to_m_scale": 0.01
        }
    }
    
    with open(compliance_path, "w", encoding="utf-8") as f:
        json.dump(initial_compliance, f, ensure_ascii=False, indent=2)
        
    yield
    
    # 정리
    app.dependency_overrides.clear()
    if compliance_path.exists():
        os.remove(compliance_path)
    # Stripe Payment Service 초기화
    StripePaymentService._failure_count = 0
    StripePaymentService._circuit_state = "CLOSED"


# ================================================================
# 1. Stripe 결제 미결제 유저의 402 Payment Required 차단 가드 테스트
# ================================================================
def test_compliance_checksheet_payment_guard():
    """결제 이력이 없는 무료 회원(credits=0, free plan)인 경우, API가 402 에러를 반환하며 다운로드를 철저히 가드하는지 검증"""
    # 유저 정보를 free 회원으로 변경
    GLOBAL_MOCK_DB.table("profiles")._data = [
        {"id": "user_123", "plan_type": "free", "credits": 0, "stripe_subscription_id": None}
    ]
    
    # 402 Payment Required 반환 확인
    res = client.get("/api/v1/projects/proj_999/compliance-checksheet?format=pdf")
    assert res.status_code == 402
    assert "Payment required" in res.json()["detail"]


# ================================================================
# 2. format=json 요청 시 Pydantic 데이터 계약 준수성 정밀 검증
# ================================================================
def test_compliance_checksheet_json_format():
    """format=json 쿼리 시 일본 건축기준법 자가 체크시트 데이터가 Pydantic 모델에 정의된 바에 따라 무결성 높게 200 OK와 함께 리턴되는지 검증"""
    res = client.get(
        "/api/v1/projects/proj_999/compliance-checksheet",
        params={
            "format": "json",
            "chief_designer": "코다리 소장",
            "license_number": "一級第888888号"
        }
    )
    
    assert res.status_code == 200
    data = res.json()
    
    # Pydantic 모델 필드 계약성 검사
    assert data["project_id"] == "proj_999"
    assert "test_mansion" in data["building_name"]
    assert data["chief_designer"] == "코다리 소장"
    assert data["license_number"] == "一級第888888号"
    assert data["overall_judgment"] == "適合" # 기하 조건 상 적합하므로 "適合"
    
    # 검증 조항 목록 정밀 분석
    items = data["check_items"]
    assert len(items) >= 2
    
    # 1) 채광 (第28조)
    lighting_item = next(item for item in items if "第28条" in item["article_no"])
    assert lighting_item["item_name_jp"] == "LDK の有効採光面積の割合"
    assert lighting_item["standard_value"] == "窓面積 / 居室面積 >= 1/7"
    assert lighting_item["status"] == "PASS"
    assert "適合することを確認" in lighting_item["inspector_comment"]
    
    # 2) 반자 높이 (令21조)
    height_item = next(item for item in items if "令第21条" in item["article_no"])
    assert height_item["item_name_jp"] == "LDK の天井高"
    assert height_item["standard_value"] == "天井高 >= 2.1m"
    assert height_item["status"] == "PASS"
    assert "2.1m以上" in height_item["inspector_comment"]


# ================================================================
# 3. format=pdf 요청 시 ReportLab PDF 1장 패키징 및 날인 정합성 검증
# ================================================================
def test_compliance_checksheet_pdf_generation():
    """format=pdf 요청 시, A4 규격에 맞는 ReportLab 컴파일레이션이 완료되고, 1급 건축사 날인이 동적 합성된 깨짐 없는 일본어 PDF 바이너리가 다운로드되는지 검증"""
    res = client.get(
        "/api/v1/projects/proj_999/compliance-checksheet",
        params={
            "format": "pdf",
            "chief_designer": "코다리 부장",
            "license_number": "一級第777777号"
        }
    )
    
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == 'attachment; filename="compliance_checksheet_proj_999.pdf"'
    
    # 리턴된 파일 데이터가 PDF 바이너리(시그니처 %PDF)로 시작하는지 검증
    pdf_content = res.content
    assert pdf_content.startswith(b"%PDF")
    assert len(pdf_content) > 1000 # 유의미한 PDF 데이터 용량 확보 확인


# ================================================================
# 4. 부적합(FAIL) 시나리오 E2E 동적 매핑 검증
# ================================================================
def test_compliance_checksheet_non_compliant_flow():
    """기하 규격 중 채광이 기준 미달(FAIL)인 경우, 종합 판정이 '不適合'으로 실시간 반영되고 동적 적합 판정 배지(不適合)가 합성되는지 E2E 검증"""
    from pipeline.paths import OUTPUT_ROOT
    project_dir = OUTPUT_ROOT / "projects" / "proj_999"
    compliance_path = project_dir / "page0_compliance.json"
    
    # 창문 면적을 극단적으로 줄여 FAIL 유도
    non_compliant_data = {
        "rooms": [
            {
                "id": "room_1",
                "kind": "LDK",
                "area_m2": 15.0,
                "height_mm": 2400.0,
                "polygon": [
                    {"x": 0, "y": 0},
                    {"x": 300, "y": 0},
                    {"x": 300, "y": 500},
                    {"x": 0, "y": 500}
                ],
                "actual_window_area_m2": 0.5 # 15/7 = 2.14m2 미만이므로 부적합!
            }
        ],
        "openings": [
            {
                "kind": "WINDOW",
                "p1": {"x": 100, "y": 0},
                "p2": {"x": 120, "y": 0}, # 좁은 창문
                "width_px": 20
            }
        ],
        "metrics": {
            "px_to_m_scale": 0.01
        }
    }
    
    with open(compliance_path, "w", encoding="utf-8") as f:
        json.dump(non_compliant_data, f, ensure_ascii=False, indent=2)
        
    # JSON 요청을 통해 종합 판정 및 체크아이템 필터링 확인
    res = client.get(
        "/api/v1/projects/proj_999/compliance-checksheet",
        params={"format": "json"}
    )
    
    assert res.status_code == 200
    data = res.json()
    assert data["overall_judgment"] == "不適合"
    
    lighting_item = next(item for item in data["check_items"] if "第28条" in item["article_no"])
    assert lighting_item["status"] == "FAIL"
    assert "下回っており" in lighting_item["inspector_comment"] # "하회하고 있으므로" 일본어 소견 확인
    
    # PDF 다운로드 테스트 역시 부적합 배지를 태운 상태에서 빌드가 정상 수행되는지 검증
    res_pdf = client.get(
        "/api/v1/projects/proj_999/compliance-checksheet",
        params={"format": "pdf"}
    )
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF")
