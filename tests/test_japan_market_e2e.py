# -*- coding: utf-8 -*-
import os
import pytest
import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.payment import StripePaymentService
from app.services.i18n import JPTranslationEngine

client = TestClient(app)

# Mock Supabase Database Client
class MockTable:
    def __init__(self, data=None):
        self._data = data or []
        self._filters = {}
        
    def select(self, *args):
        return self
        
    def insert(self, record):
        self._data.append(record)
        return self
        
    def update(self, record):
        for item in self._data:
            if all(item.get(k) == v for k, v in self._filters.items()):
                item.update(record)
        return self
        
    def eq(self, column, value):
        self._filters[column] = value
        return self
        
    def execute(self):
        class Response:
            def __init__(self, data):
                self.data = data
        
        # 필터링 적용
        filtered_data = []
        for item in self._data:
            match = True
            for k, v in self._filters.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                filtered_data.append(item)
                
        return Response(filtered_data if filtered_data else self._data)

class MockSupabaseClient:
    def __init__(self):
        self._tables = {
            "profiles": MockTable([
                {"id": "user_123", "plan_type": "free", "credits": 0, "stripe_subscription_id": None}
            ]),
            "projects": MockTable([
                {
                    "id": "proj_999", 
                    "user_id": "user_123", 
                    "original_filename": "test_mansion.pdf", 
                    "status": "completed",
                    "metadata": {
                        "compliance_opinions": [
                            {
                                "room_type_jp": "toilet",
                                "decision_label": "専有部分",
                                "ownership_decision": "PROPRIETARY",
                                "legal_basis": "区分所有法第1条",
                                "japanese_opinion": "専有部分の給水管継手からの漏水と判定されます。"
                            },
                            {
                                "room_type_jp": "pipe_space",
                                "decision_label": "共用部分",
                                "ownership_decision": "COMMON",
                                "legal_basis": "区分所有法第4条",
                                "japanese_opinion": "PS内部の共用縦管からの漏水と判定されます。"
                            }
                        ]
                    }
                }
            ])
        }
        
    def table(self, name):
        return self._tables.get(name, MockTable())

# [하네스 프로토콜] 싱글톤 DB Mock 인스턴스
GLOBAL_MOCK_DB = MockSupabaseClient()

# JWT 토큰 검증 의존성을 Mocking하기 위한 오버라이드
def get_mock_user_and_db():
    return {
        "user_id": "user_123",
        "db": GLOBAL_MOCK_DB
    }

@pytest.fixture(autouse=True)
def setup_mocks(monkeypatch):
    # API Router 의존성 주입 오버라이드
    from app.api.deps import get_current_user_and_db, get_supabase_client
    app.dependency_overrides[get_current_user_and_db] = get_mock_user_and_db
    app.dependency_overrides[get_supabase_client] = lambda: GLOBAL_MOCK_DB

    # SP1/S-4 + SP6/P0-8: 서명 없는 웹훅과 mock 결제는 기본 거부된다.
    # 본 E2E 테스트에서만 두 개의 열쇠를 모두 명시적으로 활성화한다.
    #   1) PAYMENT_ALLOW_MOCK_WEBHOOK=1
    #   2) ENV 가 개발 환경 화이트리스트에 포함 (ENV 미설정은 화이트리스트에 없다)
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")
    monkeypatch.setenv("ENV", "development")

    # 웹훅·원장 처리는 service_role 클라이언트를 서비스 내부에서 직접 얻는다.
    # FastAPI 의존성 오버라이드는 DI 경로에만 적용되므로 내부 접근자도 함께 교체한다.
    monkeypatch.setattr(
        StripePaymentService, "_service_db", classmethod(lambda cls: GLOBAL_MOCK_DB)
    )

    # 각 테스트 시작 전 DB 상태 초기화 (독립성 확보)
    GLOBAL_MOCK_DB.table("profiles")._data = [
        {"id": "user_123", "plan_type": "free", "credits": 0, "stripe_subscription_id": None}
    ]
    GLOBAL_MOCK_DB.table("profiles")._filters = {}
    
    yield
    app.dependency_overrides.clear()
    # Stripe Payment Service 초기화
    StripePaymentService._failure_count = 0
    StripePaymentService._circuit_state = "CLOSED"

# ================================================================
# 1. 다국어(i18n) 번역 맵 정밀 검증
# ================================================================
def test_i18n_room_translation():
    """영문 방 타입을 일본 주택 표준 명칭과 약어로 정확하게 매핑하는지 검증"""
    res_toilet = JPTranslationEngine.translate_room("toilet")
    assert res_toilet["name"] == "トイレ (WC)"
    assert res_toilet["abbr"] == "WC"

    res_ps = JPTranslationEngine.translate_room("pipe_space")
    assert res_ps["name"] == "パイプスペース (PS)"
    assert res_ps["abbr"] == "PS"

    res_bedroom = JPTranslationEngine.translate_room("bedroom")
    assert res_bedroom["name"] == "洋室"
    assert res_bedroom["abbr"] == "洋室"

    res_unknown = JPTranslationEngine.translate_room("random_zone")
    assert "random_zone" in res_unknown["abbr"]

# ================================================================
# 2. 결제 게이트웨이 및 크레딧 라이선스 흐름 검증
# ================================================================
def test_payment_gateway_and_licensing():
    """결제 구매부터 웹훅 적용, 크레딧 갱신, 유료 다운로드까지의 E2E 결제 생태계 검증"""
    db_mock = MockSupabaseClient()
    
    # 1. 초기 무료 회원 상태 조회
    status_response = client.get("/api/v1/payments/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["plan_type"] == "free"
    assert status_data["credits"] == 0
    assert status_data["active"] == False

    # 2. 무료 회원 상태에서 PDF 레포트 요청 시 결제 필요(402) 응답 검증
    pdf_response = client.get("/api/v1/projects/proj_999/pdf-report")
    assert pdf_response.status_code == 402
    assert "Payment required" in pdf_response.json()["detail"]

    # 3. Stripe JPY 결제 Checkout 생성 (Basic Plan 구매)
    checkout_res = client.post("/api/v1/payments/checkout-session", json={"plan_type": "basic"})
    assert checkout_res.status_code == 200
    checkout_data = checkout_res.json()
    assert checkout_data["plan"] == "basic"
    assert checkout_data["amount"] == 4900
    assert "session_id" in checkout_data

    # 4. 결제 완료 웹훅 모사 발송
    webhook_payload = {
        "user_id": "user_123",
        "plan_type": "basic",
        "session_id": checkout_data["session_id"]
    }
    webhook_res = client.post("/api/v1/payments/webhook", json=webhook_payload)
    assert webhook_res.status_code == 200

    # 5. 구매 후 회원 상태 및 크레딧 확인
    status_response = client.get("/api/v1/payments/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["plan_type"] == "basic"
    assert status_data["credits"] == 10
    assert status_data["active"] == True

# ================================================================
# 3. Circuit Breaker (장애 시 fail-closed 보호) 검증
# ================================================================
def test_payment_circuit_breaker_flow():
    """Stripe API 3회 실패 시 회로를 차단(OPEN)하고, SP1/S-3 fail-closed 정책에 따라
    유료 접근 게이트는 무료 통과(Grace Period)가 아닌 '거부'되는지 검증한다.
    (과금 정합성이 가용성보다 우선 - 회로 OPEN 상태에서의 무료 접근은 매출 누수)"""
    db_mock = MockSupabaseClient()
    
    # 1. 3회 연속 실패 강제 트리거
    for _ in range(3):
        StripePaymentService._handle_failure()
        
    assert StripePaymentService._circuit_state == "OPEN"

    # 2. 가드 게이트웨이는 회로 OPEN 상태에서 접근을 거부해야 한다 (fail-closed)
    access_allowed = StripePaymentService.check_user_access_gate("user_123", db_mock)
    assert access_allowed == False

    # 3. 크레딧 차감 역시 실행되지 않는다
    deducted = StripePaymentService.deduct_credit("user_123", db_mock)
    assert deducted == False

# ================================================================
# 4. A4 1장 일본어 PDF 누수 진단 보고서 실시간 생성 및 다국어 매핑 검증
# ================================================================
def test_pdf_report_generation_endpoint():
    """실시간 프로젝트 메타 로드 -> i18n 공간 세맨틱 변환 -> 1장 최적화 일본어 PDF 생성 200 OK 검증"""
    # 1. 유효 라이선스(PRO) 임시 부여
    GLOBAL_MOCK_DB.table("profiles").update({"plan_type": "pro", "credits": 9999}).eq("id", "user_123").execute()
    
    # 2. PDF 다운로드 API 호출
    pdf_res = client.get("/api/v1/projects/proj_999/pdf-report")
    
    # ReportLab PDF 생성 및 FileResponse 200 검증
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 1000 # 1KB 이상의 PDF 데이터가 들어있는지 확인
