# -*- coding: utf-8 -*-
"""
P0-8 / P0-9 결제 무결성 회귀 테스트.

검증 대상 (commercialization_roadmap_v1.0 §1 CRITICAL 대응):

  1. Stripe 미설정/장애 시 가짜 결제 세션(mock)으로 흡수하지 않는다 (fail-closed).
  2. 서명 없는 웹훅은 명시적 개발 환경에서만 허용된다.
  3. 동일 이벤트 재전달 시 크레딧이 중복 지급되지 않는다 (멱등성).
  4. DB 반영 실패를 성공(fallback_success)으로 위장하지 않는다.
  5. 크레딧 차감은 원자 연산(RPC)을 우선 사용하고, 실패 시 무료 사용을 허용하지 않는다.
"""
import json
import sys
from types import SimpleNamespace

import pytest

from app.services import payment as payment_mod
from app.services.payment import CircuitBreakerOpenException, StripePaymentService


# ---------------------------------------------------------------------------
# 테스트 더블
# ---------------------------------------------------------------------------
class FakeResult:
    def __init__(self, data=None):
        self.data = data if data is not None else []


class FakeQuery:
    """PostgREST 체인 API 최소 에뮬레이터."""

    def __init__(self, db, name):
        self.db = db
        self.name = name
        self._op = None
        self._payload = None
        self._filters = []

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def execute(self):
        return self.db._execute(self)


class FakeRpc:
    """supabase-py 의 rpc() 는 쿼리 빌더를 반환하고 .execute() 로 확정된다."""

    def __init__(self, db, fn, params):
        self.db = db
        self.fn = fn
        self.params = params

    def execute(self):
        self.db.rpc_calls.append((self.fn, self.params))
        if self.db.rpc_raises:
            raise RuntimeError("rpc unavailable")
        # PostgREST 는 스칼라 함수를 [value] 또는 value 로 반환한다
        return FakeResult(self.db.rpc_result)


class FakeSupabase:
    """profiles / processed_payment_events 최소 동작 에뮬레이터."""

    def __init__(self, profiles=None, fail_profile_update=False, rpc_result=None, rpc_raises=False):
        self.events = {}
        self.profiles = dict(profiles or {})
        self.fail_profile_update = fail_profile_update
        self.rpc_result = rpc_result
        self.rpc_raises = rpc_raises
        self.rpc_calls = []
        self.profile_updates = []

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, fn, params):
        return FakeRpc(self, fn, params)

    # -- 체인 실행 ----------------------------------------------------------
    def _execute(self, q):
        if q.name == "processed_payment_events":
            return self._exec_events(q)
        if q.name == "profiles":
            return self._exec_profiles(q)
        raise AssertionError(f"unexpected table: {q.name}")

    def _exec_events(self, q):
        if q._op == "insert":
            event_id = q._payload["event_id"]
            if event_id in self.events:
                raise RuntimeError(f"duplicate key value violates unique constraint: {event_id}")
            self.events[event_id] = dict(q._payload)
            return FakeResult([dict(q._payload)])
        if q._op == "delete":
            target = dict(q._filters).get("event_id")
            existed = self.events.pop(target, None)
            return FakeResult([existed] if existed else [])
        if q._op == "select":
            return FakeResult(list(self.events.values()))
        raise AssertionError(f"unexpected op: {q._op}")

    def _exec_profiles(self, q):
        if q._op == "select":
            return FakeResult(list(self.profiles.values()))
        if q._op == "update":
            if self.fail_profile_update:
                raise RuntimeError("profiles update failed")
            # 대상 행은 payload 가 아니라 .eq("id", ...) 필터로 지정된다.
            # CAS 폴백은 .eq("credits", <읽은값>) 을 추가하므로, 잔액이 그대로일
            # 때에만 갱신이 반영된다 (갱신 분실 방지).
            filters = dict(q._filters)
            row = self.profiles.get(filters.get("id"))
            if row is None:
                return FakeResult([])
            if "credits" in filters and row.get("credits") != filters["credits"]:
                return FakeResult([])  # 충돌 -> 갱신 없음
            row.update(q._payload)
            self.profile_updates.append(dict(q._payload))
            return FakeResult([row])
        if q._op == "insert":
            self.profiles[q._payload["id"]] = dict(q._payload)
            return FakeResult([dict(q._payload)])
        raise AssertionError(f"unexpected op: {q._op}")


class ExplodingStripe:
    """항상 실패하는 stripe 모듈 스텁."""

    api_key = None

    class checkout:
        class Session:
            @staticmethod
            def create(**_kwargs):
                raise RuntimeError("Stripe API is unreachable")


@pytest.fixture(autouse=True)
def _reset_payment_state(monkeypatch):
    """회로 차단기와 mock 허용 플래그를 테스트마다 초기화한다."""
    monkeypatch.setattr(StripePaymentService, "_circuit_state", "CLOSED", raising=False)
    monkeypatch.setattr(StripePaymentService, "_failure_count", 0, raising=False)
    monkeypatch.setattr(StripePaymentService, "STRIPE_API_KEY", "", raising=False)
    monkeypatch.setattr(StripePaymentService, "STRIPE_WEBHOOK_SECRET", "whsec_test", raising=False)
    # service_role 클라이언트 캐시가 테스트 간에 새지 않도록 초기화한다
    monkeypatch.setattr(StripePaymentService, "_service_db_cache", None, raising=False)
    # 기본 상태: 개발 ENV 지정 + mock 플래그 없음 -> mock 불가 (fail-closed)
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("PAYMENT_ALLOW_MOCK_WEBHOOK", raising=False)
    yield


# ---------------------------------------------------------------------------
# 1. Checkout fail-closed
# ---------------------------------------------------------------------------
def test_checkout_fails_closed_when_stripe_key_missing():
    """Stripe 키가 없으면 가짜 결제 URL 을 발급하지 않고 예외를 던진다."""
    with pytest.raises(CircuitBreakerOpenException):
        StripePaymentService.create_checkout_session("user-1", "basic", FakeSupabase())


def test_checkout_mock_only_in_explicit_dev_env(monkeypatch):
    """명시적 개발 환경 + 플래그 조합에서만 mock 세션을 발급한다."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")
    result = StripePaymentService.create_checkout_session("user-1", "single", FakeSupabase())
    assert result["mode"] == "mock"
    assert result["amount"] == 1500


def test_mock_payment_denied_when_env_unset(monkeypatch):
    """
    ENV 미설정은 화이트리스트에 없으므로 mock 결제가 열리지 않는다.

    과거 `os.getenv("ENV") != "production"` 은 ENV 미설정 시 항상 참이 되어,
    운영 배포에서 ENV 를 빼먹기만 해도 mock 결제가 열렸다.
    """
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")

    with pytest.raises(CircuitBreakerOpenException):
        StripePaymentService.create_checkout_session("user-1", "single", FakeSupabase())


def test_mock_payment_denied_in_production_even_with_flag(monkeypatch):
    """운영 환경에서는 플래그가 있어도 mock 결제를 절대 발급하지 않는다."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")

    with pytest.raises(CircuitBreakerOpenException):
        StripePaymentService.create_checkout_session("user-1", "single", FakeSupabase())


def test_checkout_does_not_fall_back_to_mock_on_stripe_error(monkeypatch):
    """
    Stripe 호출 실패를 mock 으로 흡수하지 않는다.

    과거: except 블록에서 그대로 mock 세션을 반환해, 고객은 결제 화면으로
          안내되지만 실제 결제 수단은 없는 상태가 되었다 (매출 누수 + 고객 오인).
    """
    monkeypatch.setattr(StripePaymentService, "STRIPE_API_KEY", "sk_test_dummy")
    monkeypatch.setitem(sys.modules, "stripe", ExplodingStripe)

    with pytest.raises(RuntimeError, match="Stripe API is unreachable"):
        StripePaymentService.create_checkout_session("user-1", "pro", FakeSupabase())

    # 실패가 회로 차단기에 기록되어야 한다
    assert StripePaymentService._failure_count == 1


def test_checkout_rejects_unknown_plan():
    with pytest.raises(ValueError):
        StripePaymentService.create_checkout_session("user-1", "enterprise", FakeSupabase())


# ---------------------------------------------------------------------------
# 2. Webhook 인증 (fail-closed)
# ---------------------------------------------------------------------------
def test_unsigned_webhook_rejected_by_default():
    """서명 없는 웹훅은 기본 거부된다."""
    body = json.dumps({"user_id": "user-1", "plan_type": "pro"}).encode()
    result = StripePaymentService.verify_and_apply_webhook(body, None, FakeSupabase())

    assert result["status"] == "error"
    assert result["retryable"] is False


def test_unsigned_webhook_allowed_only_with_explicit_flag(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")
    svc = FakeSupabase()
    monkeypatch.setattr(StripePaymentService, "_service_db", classmethod(lambda cls: svc))

    body = json.dumps(
        {"user_id": "user-1", "plan_type": "basic", "session_id": "cs_1", "event_id": "evt_1"}
    ).encode()
    result = StripePaymentService.verify_and_apply_webhook(body, None, svc)

    assert result["status"] == "success"
    assert result["added_credits"] == 10


def test_signed_webhook_rejected_when_secret_unconfigured(monkeypatch):
    """서명은 있으나 웹훅 시크릿이 없으면 검증 불가 -> 거부 (fail-closed)."""
    monkeypatch.setattr(StripePaymentService, "STRIPE_WEBHOOK_SECRET", "", raising=False)
    result = StripePaymentService.verify_and_apply_webhook(b"{}", "t=1,v1=abc", FakeSupabase())

    assert result["status"] == "error"
    assert result["retryable"] is False


# ---------------------------------------------------------------------------
# 3. 멱등성
# ---------------------------------------------------------------------------
def test_duplicate_event_is_not_credited_twice(monkeypatch):
    """
    동일 이벤트 재전달 시 크레딧이 중복 지급되지 않는다.

    Stripe 는 at-least-once 전달이므로 재시도/재전달이 정상적으로 발생한다.
    """
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")
    svc = FakeSupabase(profiles={"user-1": {"id": "user-1", "credits": 0, "plan_type": "free"}})
    monkeypatch.setattr(StripePaymentService, "_service_db", classmethod(lambda cls: svc))

    body = json.dumps(
        {"user_id": "user-1", "plan_type": "single", "session_id": "cs_1", "event_id": "evt_dup"}
    ).encode()

    first = StripePaymentService.verify_and_apply_webhook(body, None, svc)
    second = StripePaymentService.verify_and_apply_webhook(body, None, svc)

    assert first["status"] == "success"
    assert first["added_credits"] == 1
    assert second["status"] == "duplicate"
    assert second["added_credits"] == 0
    assert svc.profiles["user-1"]["credits"] == 1, "재전달로 크레딧이 중복 지급되었다"


# ---------------------------------------------------------------------------
# 4. DB 실패를 성공으로 위장하지 않음
# ---------------------------------------------------------------------------
def test_profile_update_failure_is_reported_as_retryable_error(monkeypatch):
    """
    과거: DB 반영 실패 시 {"status": "fallback_success"} 를 반환했다.
          결제는 완료됐는데 크레딧은 지급되지 않고, 시스템은 성공으로 기록되었다.
    현재: 재시도 가능 오류로 반환하고 멱등 선점을 해제해 재전달로 복구되게 한다.
    """
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")
    svc = FakeSupabase(
        profiles={"user-1": {"id": "user-1", "credits": 0, "plan_type": "free"}},
        fail_profile_update=True,
    )
    monkeypatch.setattr(StripePaymentService, "_service_db", classmethod(lambda cls: svc))

    body = json.dumps(
        {"user_id": "user-1", "plan_type": "single", "session_id": "cs_1", "event_id": "evt_db_fail"}
    ).encode()

    result = StripePaymentService.verify_and_apply_webhook(body, None, svc)

    assert result["status"] == "error"
    assert result["retryable"] is True
    # 재전달로 복구될 수 있도록 선점이 해제되어야 한다
    assert "evt_db_fail" not in svc.events


def test_webhook_without_user_id_is_rejected(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "1")
    svc = FakeSupabase()
    monkeypatch.setattr(StripePaymentService, "_service_db", classmethod(lambda cls: svc))

    body = json.dumps({"plan_type": "pro", "event_id": "evt_no_user"}).encode()
    result = StripePaymentService.verify_and_apply_webhook(body, None, svc)

    assert result["status"] == "error"
    assert "user_id" in result["message"]


# ---------------------------------------------------------------------------
# 5. 원자적 크레딧 차감
# ---------------------------------------------------------------------------
def test_deduct_credit_prefers_atomic_rpc(monkeypatch):
    """차감은 SELECT->UPDATE 분리 대신 원자 RPC 를 사용한다 (lost update 방지)."""
    svc = FakeSupabase(rpc_result=[True])
    monkeypatch.setattr(StripePaymentService, "_service_db", classmethod(lambda cls: svc))

    ok = StripePaymentService.deduct_credit("user-1", svc, amount=3)

    assert ok is True
    assert svc.rpc_calls == [("deduct_credits", {"p_user_id": "user-1", "p_amount": 3})]


def test_deduct_credit_returns_false_when_rpc_denies(monkeypatch):
    svc = FakeSupabase(rpc_result=[False])
    monkeypatch.setattr(StripePaymentService, "_service_db", classmethod(lambda cls: svc))

    assert StripePaymentService.deduct_credit("user-1", svc, amount=1) is False


def test_deduct_credit_falls_back_to_cas_without_double_spend(monkeypatch):
    """
    RPC 미배포 환경의 CAS 폴백이 잔액을 초과 사용하지 않는지 검증한다.

    profiles UPDATE 정책은 본인만 가능하므로 사용자 토큰 클라이언트로도 동작한다.
    """
    svc = FakeSupabase(
        profiles={"user-1": {"id": "user-1", "credits": 1, "plan_type": "free"}},
        rpc_raises=True,
    )
    monkeypatch.setattr(StripePaymentService, "_service_db", classmethod(lambda cls: svc))

    assert StripePaymentService.deduct_credit("user-1", svc, amount=1) is True
    assert svc.profiles["user-1"]["credits"] == 0
    # 잔액 0 에서 재차 차감 시도는 거부되어야 한다
    assert StripePaymentService.deduct_credit("user-1", svc, amount=1) is False


def test_deduct_credit_denied_when_circuit_open(monkeypatch):
    monkeypatch.setattr(StripePaymentService, "_circuit_state", "OPEN")
    svc = FakeSupabase(rpc_result=[True])
    monkeypatch.setattr(StripePaymentService, "_service_db", classmethod(lambda cls: svc))

    assert StripePaymentService.deduct_credit("user-1", svc, amount=1) is False
    assert svc.rpc_calls == []


def test_deduct_credit_rejects_non_positive_amount():
    svc = FakeSupabase(rpc_result=[True])
    assert StripePaymentService.deduct_credit("user-1", svc, amount=0) is False
    assert StripePaymentService.deduct_credit("user-1", svc, amount=-1) is False


# ---------------------------------------------------------------------------
# 6. 접근 게이트 (fail-closed 유지 확인)
# ---------------------------------------------------------------------------
def test_access_gate_denies_when_profile_missing():
    assert StripePaymentService.check_user_access_gate("ghost", FakeSupabase()) is False


def test_access_gate_allows_pro_plan_without_credits():
    svc = FakeSupabase(profiles={"u": {"id": "u", "plan_type": "pro", "credits": 0}})
    assert StripePaymentService.check_user_access_gate("u", svc, amount=10) is True
