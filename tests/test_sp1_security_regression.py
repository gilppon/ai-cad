# -*- coding: utf-8 -*-
"""
SP1 코드보수 회귀 테스트 (code_remediation_plan_v1.0_20260826.md §4 P0 항목 검증)

S-1 인증 우회 제거 / S-3 결제 fail-closed / S-4 웹훅 서명 필수 /
S-5 미디어 경로 순회 차단 / D-1 가짜 등록번호 금지 / L-1 스케일 SSOT / L-2 판정위조 폴백 금지
"""
import asyncio
import json
import os
import shutil
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.main import app
from app.api import deps
from app.services.payment import StripePaymentService

client = TestClient(app)


# ----------------------------------------------------------------
# 공용 Fake DB (체이닝 가능한 최소 Supabase 모사)
# ----------------------------------------------------------------
class FakeTable:
    def __init__(self, rows=None):
        self._rows = rows if rows is not None else []

    def select(self, *a):
        return self

    def insert(self, row):
        self._rows.append(row)
        return self

    def update(self, record):
        for r in self._rows:
            r.update(record)
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def execute(self):
        out = MagicMock()
        out.data = list(self._rows)
        return out


class ExplodingTable(FakeTable):
    def select(self, *a):
        raise RuntimeError("db connection lost")


# ================================================================
# S-1: 무효/만료 JWT는 ENV와 무관하게 401 거부
# ================================================================
def _call_auth(token: str) -> str:
    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return asyncio.run(deps.get_current_user(cred))


def test_s1_invalid_token_rejected_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    with pytest.raises(HTTPException) as ei:
        _call_auth("totally.invalid.token")
    assert ei.value.status_code == 401


def test_s1_mock_key_rejected_by_default(monkeypatch):
    """구버전에서 통과하던 mock-key 토큰 화이트리스트가 완전히 제거되었는지 검증"""
    monkeypatch.delenv("ALLOW_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    with pytest.raises(HTTPException) as ei:
        _call_auth("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock-key")
    assert ei.value.status_code == 401


def test_s1_expired_token_rejected_even_in_local_dev(monkeypatch):
    expired_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImV4cCI6MTAwMH0.bad"
    monkeypatch.setenv("ENV", "local")
    monkeypatch.delenv("ALLOW_AUTH_BYPASS", raising=False)
    with pytest.raises(HTTPException) as ei:
        _call_auth(expired_jwt)
    assert ei.value.status_code == 401


def test_s1_explicit_bypass_flag_allows_local_only(monkeypatch):
    monkeypatch.setenv("ALLOW_AUTH_BYPASS", "1")
    monkeypatch.setenv("ENV", "development")
    user_id = _call_auth("anything.invalid")
    assert user_id == "user_123"


def test_s1_bypass_flag_ignored_in_production(monkeypatch):
    monkeypatch.setenv("ALLOW_AUTH_BYPASS", "1")
    monkeypatch.setenv("ENV", "production")
    # 기본 시크릿 가드(RuntimeError)와 분리하기 위해 실제 시크릿이 설정된 상태를 가정
    monkeypatch.setattr(deps, "JWT_SECRET", "real-production-secret")
    with pytest.raises(HTTPException) as ei:
        _call_auth("totally.invalid.token")
    assert ei.value.status_code == 401


def test_s1_default_secret_in_production_raises(monkeypatch):
    monkeypatch.setattr(deps, "JWT_SECRET", "your-jwt-secret")
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError):
        _call_auth("whatever.token.here")


# ================================================================
# S-3: 결제 게이트·차감 fail-closed
# ================================================================
@pytest.fixture(autouse=True)
def reset_payment_circuit():
    StripePaymentService._failure_count = 0
    StripePaymentService._circuit_state = "CLOSED"
    yield
    StripePaymentService._failure_count = 0
    StripePaymentService._circuit_state = "CLOSED"


def test_s3_gate_denies_on_db_failure():
    db = MagicMock()
    db.table.return_value = ExplodingTable()
    assert StripePaymentService.check_user_access_gate("u1", db, amount=1) is False


def test_s3_deduct_never_pretends_success_on_db_failure():
    db = MagicMock()
    db.table.return_value = ExplodingTable()
    assert StripePaymentService.deduct_credit("u1", db, amount=1) is False


def test_s3_gate_denies_when_circuit_open():
    StripePaymentService._circuit_state = "OPEN"
    db = MagicMock()
    db.table.return_value = FakeTable([{"plan_type": "pro", "credits": 99999}])
    # pro 플랜이라도 회로 OPEN 시에는 접근 거부 (fail-closed)
    assert StripePaymentService.check_user_access_gate("u1", db, amount=1) is False


def test_s3_gate_still_allows_normal_paid_user():
    db = MagicMock()
    db.table.return_value = FakeTable([{"id": "u1", "plan_type": "free", "credits": 5}])
    assert StripePaymentService.check_user_access_gate("u1", db, amount=3) is True


# ================================================================
# S-4: 웹훅 서명 필수화
# ================================================================
WEBHOOK_BODY = json.dumps({"user_id": "user_123", "plan_type": "basic"}).encode("utf-8")


def test_s4_unsigned_webhook_rejected_without_flag(monkeypatch):
    monkeypatch.delenv("PAYMENT_ALLOW_MOCK_WEBHOOK", raising=False)
    res = StripePaymentService.verify_and_apply_webhook(WEBHOOK_BODY, None, MagicMock())
    assert res["status"] == "error"
    assert "stripe-signature" in res["message"]


def test_s4_unsigned_webhook_rejected_even_with_flag_in_production(monkeypatch):
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")
    monkeypatch.setenv("ENV", "production")
    res = StripePaymentService.verify_and_apply_webhook(WEBHOOK_BODY, None, MagicMock())
    assert res["status"] == "error"


def test_s4_unsigned_webhook_denied_when_env_unset(monkeypatch):
    """
    ENV 미설정은 개발 환경 화이트리스트에 없으므로 서명 없는 웹훅을 거부한다.

    과거 계약(`ENV != "production"`)은 ENV 미설정 시 항상 허용으로 평가되어,
    운영 배포에서 ENV 를 빼먹기만 해도 무서명 웹훅으로 크레딧을 충전할 수 있었다.
    """
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")
    res = StripePaymentService.verify_and_apply_webhook(WEBHOOK_BODY, None, MagicMock())
    assert res["status"] == "error"


def test_s4_unsigned_webhook_allowed_with_explicit_flag(monkeypatch):
    """
    비운영 ENV + 명시적 플래그 두 조건이 모두 충족될 때만 서명 없는 웹훅을 허용한다.

    SP6/P0-8: mock 허용 판정은 호출 시점에 평가된다 (과거: 모듈 임포트 시점 스냅샷으로
    인해 프로세스 기동 후 환경 변경이 반영되지 않았다).
    """
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")

    fake_db = MagicMock()
    fake_db.table.return_value = FakeTable([])
    # 웹훅은 service_role 클라이언트로 멱등 선점 테이블에 기록한다
    monkeypatch.setattr(
        StripePaymentService, "_service_db", classmethod(lambda cls: fake_db)
    )

    res = StripePaymentService.verify_and_apply_webhook(WEBHOOK_BODY, None, fake_db)
    # "fallback_success" 는 폐지되었다: DB 반영 실패를 성공으로 위장하지 않는다 (C6)
    assert res["status"] == "success"


# ================================================================
# S-5: 미디어 경로 순회 차단
# (httpx 클라이언트가 ../ 세그먼트를 URL 정규화로 제거하므로 핸들러 직접 호출로 검증)
# ================================================================
def test_s5_media_traversal_via_dotdot_project_blocked():
    from app.api.v1.endpoints import get_project_media
    with pytest.raises(HTTPException) as ei:
        asyncio.run(get_project_media("..", "x.png"))
    assert ei.value.status_code == 400


def test_s5_media_traversal_via_dotdot_filename_blocked():
    # starlette가 %2F를 디코딩한 후 핸들러에 도달하는 형태로 검증
    from app.api.v1.endpoints import get_project_media
    with pytest.raises(HTTPException) as ei:
        asyncio.run(get_project_media("proj_ok", "../../secret.png"))
    assert ei.value.status_code == 400


def test_s5_media_traversal_via_backslash_blocked():
    from app.api.v1.endpoints import get_project_media
    with pytest.raises(HTTPException) as ei:
        asyncio.run(get_project_media("proj_ok", "..\\..\\secret.png"))
    assert ei.value.status_code == 400


def test_s5_media_traversal_dot_project_cannot_escape_containment():
    """
    '.', '..' 프로젝트 ID가 media 루트 밖 파일을 서빙하지 못하도록
    세그먼트 가드가 400으로 차단하는지 정밀 검증.
    """
    from app.api.v1.endpoints import get_project_media
    for bad_pid in ("..", ".", "a/../b"):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(get_project_media(bad_pid, "x.png"))
        assert ei.value.status_code == 400, f"project_id={bad_pid!r}"


def test_s5_media_normal_serving_roundtrip(tmp_path):
    media_dir = os.path.join("uploads", "media", "proj_sp1_media_t")
    os.makedirs(media_dir, exist_ok=True)
    target = os.path.join(media_dir, "ok.txt")
    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write("media-ok")
        res = client.get("/api/v1/projects/proj_sp1_media_t/media/ok.txt")
        assert res.status_code == 200
        assert res.text == "media-ok"
    finally:
        shutil.rmtree(os.path.join("uploads", "media", "proj_sp1_media_t"), ignore_errors=True)


# ================================================================
# L-1: 스케일 SSOT - 파이프라인 스케일 수용 확인
# ================================================================
def test_l1_extractor_honors_pipeline_scale(tmp_path):
    from compliance.extractor import extract_compliance_data

    payload = {
        "page_index": 0,
        "scale": {"pixel_to_mm": 5.0},
        "rooms": [{"id": 1, "kind": "BEDROOM", "area_px2": 10000.0,
                   "polygon": [{"x": 0, "y": 0}, {"x": 100, "y": 0},
                                {"x": 100, "y": 100}, {"x": 0, "y": 100}]}],
    }
    doc = extract_compliance_data(payload, str(tmp_path), page_index=0)

    # pixel_to_mm=5.0 -> px_to_m=0.005 -> area_m2 = 10000 * 0.000025 = 0.25
    assert doc["metrics"]["px_to_m_scale"] == 0.005
    assert doc["rooms"][0]["area_m2"] == pytest.approx(0.25)
    assert doc["metrics"]["total_area_m2"] == pytest.approx(0.25)


def test_l1_extractor_falls_back_without_scale(tmp_path):
    from compliance.extractor import extract_compliance_data, DEFAULT_PX_TO_M

    payload = {
        "page_index": 0,
        "rooms": [{"id": 1, "kind": "BEDROOM", "area_px2": 10000.0,
                   "polygon": [{"x": 0, "y": 0}, {"x": 100, "y": 0},
                                {"x": 100, "y": 100}, {"x": 0, "y": 100}]}],
    }
    doc = extract_compliance_data(payload, str(tmp_path), page_index=0)
    assert doc["metrics"]["px_to_m_scale"] == DEFAULT_PX_TO_M
    assert doc["rooms"][0]["area_m2"] == pytest.approx(1.0)


# ================================================================
# L-2: 평가 데이터 부재 시 가짜「適合」금지, 判定不能 명시
# ================================================================
def test_l2_checksheet_without_data_returns_judgment_impossible(monkeypatch):
    project_id = "proj_sp1_nodata"
    comp_path = os.path.join("out", "projects", project_id, "page0_compliance.json")

    # 평가 데이터가 없는 상태 보장
    if os.path.exists(comp_path):
        os.remove(comp_path)

    fake_db = MagicMock()

    def table(name):
        if name == "profiles":
            return FakeTable([{"id": "user_123", "plan_type": "free", "credits": 10}])
        if name == "projects":
            # SP6/P0-1: 소유권 검증이 강제되므로 본인 소유 프로젝트를 넣어야 한다.
            #   과거에는 소유권 검증 실패를 try/except 로 삼키고 가짜 프로젝트를
            #   조립해 200 을 반환했다(IDOR 우회). 이제 미소유는 404 다.
            #   이 테스트의 검증 대상은 "평가 데이터 부재"이므로, 프로젝트는
            #   존재하고 소유하되 page0_compliance.json 만 없는 상태로 둔다.
            return FakeTable([
                {"id": project_id, "user_id": "user_123", "original_filename": "nodata.pdf"}
            ])
        return FakeTable([])

    fake_db.table.side_effect = table

    async def override():
        return {"user_id": "user_123", "db": fake_db}

    from app.api.deps import get_current_user_and_db
    app.dependency_overrides[get_current_user_and_db] = override
    try:
        res = client.get(f"/api/v1/projects/{project_id}/compliance-checksheet?format=json")
        assert res.status_code == 200
        data = res.json()
        assert data["overall_judgment"] == "判定不能"
        assert all(item["status"] != "PASS" for item in data["check_items"])
        assert any("判定不能" in item["item_name_jp"] for item in data["check_items"])
    finally:
        app.dependency_overrides.pop(get_current_user_and_db, None)
