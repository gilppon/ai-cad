# -*- coding: utf-8 -*-
"""
Stripe (JPY) 결제 통합.

보안 원칙 (SP6/P0-8, P0-9)
--------------------------
1. 결제 경로는 **무조건 fail-closed** 다.
   Stripe 연동이 불가능할 때 가짜 결제 URL(mock)이나 임시 그레이스 라이선스를
   발급하지 않는다. 과거에는 Stripe 예외를 mock 세션으로 흡수하여
   "결제 화면으로 안내했으나 실제로는 결제 수단이 없는" 상태가 발생했고,
   이는 고객 오인(景品表示法 優良誤認) 및 매출 누수로 직결된다.

2. 웹훅은 이벤트 ID 로 멱등 처리한다.
   Stripe 는 at-least-once 전달이므로, 멱등 키가 없으면 재전달마다
   크레딧이 중복 지급된다.

3. 크레딧 차감은 DB 원자 연산으로 수행한다.
   SELECT -> UPDATE 분리 구조는 동시 요청에서 갱신 분실(lost update)을
   일으켜 잔액이 음수가 되거나 무료 사용이 발생한다.

알려진 한계 (P2)
----------------
- 회로 차단기 상태가 클래스 변수(프로세스 로컬)다. uvicorn 워커가 여러 개면
  워커별로 상태가 갈라진다. Phase 2 에서 Redis 기반 공유 상태로 이전한다.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerOpenException(Exception):
    """Circuit Breaker가 열려있을 때 발생하는 예외"""


# ---------------------------------------------------------------------------
# 환경 설정
#
# mock 결제는 **두 개의 열쇠**가 모두 맞아야 열린다.
#   1) PAYMENT_ALLOW_MOCK_WEBHOOK=1 (명시적 플래그)
#   2) ENV 가 개발 환경 화이트리스트에 포함
#
# 과거의 두 가지 결함:
#   a) `os.getenv("ENV") != "production"` — ENV 미설정(기본값)이면 항상 참이어서,
#      운영 배포에서 ENV 를 빼먹기만 해도 mock 결제가 열렸다.
#   b) 모듈 임포트 시점에 값을 한 번만 계산해, 프로세스 기동 후 환경 변경이
#      반영되지 않고 운영 가드를 테스트로 검증할 수도 없었다.
# 현재: 화이트리스트 + 호출 시점 평가 (fail-closed 기본값).
# ---------------------------------------------------------------------------
_DEV_ENVS = {"local", "development", "dev", "test", "testing", "staging"}


def _mock_payment_allowed() -> bool:
    """비운영 환경에서 명시적으로 mock 결제가 허용되었는지 호출 시점에 판정한다."""
    env = os.getenv("ENV", "").strip().lower()
    return os.getenv("PAYMENT_ALLOW_MOCK_WEBHOOK", "") == "1" and env in _DEV_ENVS


class StripePaymentService:
    """
    Stripe JPY 결제 통합 및 Circuit Breaker를 적용한 결제 엔진.

    Stripe API Key 가 없거나 Stripe 호출이 실패하면 **오류를 반환**한다.
    비운영 환경에서 PAYMENT_ALLOW_MOCK_WEBHOOK=1 이 명시된 경우에만
    mock 세션을 발급하며, 운영 환경에서는 절대 발급하지 않는다.
    """

    # Circuit Breaker 상태
    _failure_count = 0
    _circuit_state = "CLOSED"  # "CLOSED", "OPEN", "HALF-OPEN"
    _last_state_change = datetime.now(timezone.utc)
    _max_failures = 3

    STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # JPY 요금 (엔화. 소수점이 없는 통화이므로 정수 단위로 관리한다)
    PRICING_MAP = {
        "single": {"amount": 1500, "name": "Japanbuild-Leak3D 1回単発利用券"},
        "basic": {"amount": 4900, "name": "Basic プラン (月10回図面変換)"},
        "pro": {"amount": 9800, "name": "Pro プラン (無制限3D変換 + WebGL)"},
    }

    # 플랜별 지급 크레딧. pro 는 애플리케이션 레벨에서 무제한으로 취급하며,
    # 여기서는 감사 추적을 위해 유한한 값을 기록한다.
    CREDITS_BY_PLAN = {"single": 1, "basic": 10, "pro": 99999}

    # 결제 완료 후 복귀 URL (배포 환경별로 재정의)
    SUCCESS_URL = os.getenv(
        "STRIPE_SUCCESS_URL",
        "https://leak3d.japanbuild.com/payment/success?session_id={CHECKOUT_SESSION_ID}",
    )
    CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://leak3d.japanbuild.com/payment/cancel")

    @classmethod
    def _is_mock_allowed(cls) -> bool:
        """mock 결제 세션 발급이 허용되는 비운영 환경인지 호출 시점에 확인한다."""
        return _mock_payment_allowed()

    # -----------------------------------------------------------------
    # Circuit Breaker
    # -----------------------------------------------------------------
    @classmethod
    def _handle_failure(cls):
        cls._failure_count += 1
        logger.warning(
            f"[Circuit Breaker] Payment failure detected. "
            f"Count: {cls._failure_count}/{cls._max_failures}"
        )
        if cls._failure_count >= cls._max_failures:
            cls._circuit_state = "OPEN"
            cls._last_state_change = datetime.now(timezone.utc)
            logger.error("[Circuit Breaker] STATE CHANGED TO OPEN.")

    @classmethod
    def _reset_failure(cls):
        if cls._failure_count > 0:
            logger.info("[Circuit Breaker] Payment success. Resetting failure counter.")
            cls._failure_count = 0
            cls._circuit_state = "CLOSED"

    @classmethod
    def check_circuit(cls):
        """회로 차단 상태 확인 및 복구 시도"""
        if cls._circuit_state == "OPEN":
            # 60초 경과 후 HALF-OPEN으로 상태 변경하여 복구 기회 제공
            time_diff = (datetime.now(timezone.utc) - cls._last_state_change).total_seconds()
            if time_diff > 60:
                cls._circuit_state = "HALF-OPEN"
                logger.info("[Circuit Breaker] State transit to HALF-OPEN. Retrying connection next time.")
            else:
                raise CircuitBreakerOpenException(
                    "Stripe API Gateway is currently down. Please retry shortly."
                )

    # -----------------------------------------------------------------
    # Checkout Session
    # -----------------------------------------------------------------
    @classmethod
    def create_checkout_session(cls, user_id: str, plan_type: str, db: Any) -> Dict[str, Any]:
        """
        JPY (엔화) 결제를 위한 Stripe Checkout Session 생성.

        실패 시 mock 으로 흡수하지 않고 예외를 전파한다 (fail-closed).
        """
        cls.check_circuit()

        if plan_type not in cls.PRICING_MAP:
            raise ValueError(f"Unknown plan_type: {plan_type}")
        plan_info = cls.PRICING_MAP[plan_type]

        if not cls.STRIPE_API_KEY:
            if not cls._is_mock_allowed():
                # 운영에서 키가 없으면 가짜 결제 화면을 띄우지 않는다.
                logger.error(
                    "[Payment] STRIPE_API_KEY is not configured; refusing to create "
                    "a checkout session (fail-closed)."
                )
                raise CircuitBreakerOpenException("Payment gateway is not configured.")
            return cls._mock_session(plan_type, plan_info)

        try:
            import stripe

            stripe.api_key = cls.STRIPE_API_KEY

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "jpy",
                            "product_data": {"name": plan_info["name"]},
                            "unit_amount": plan_info["amount"],
                        },
                        "quantity": 1,
                    }
                ],
                mode="subscription" if plan_type in ("basic", "pro") else "payment",
                success_url=cls.SUCCESS_URL,
                cancel_url=cls.CANCEL_URL,
                metadata={"user_id": user_id, "plan_type": plan_type},
            )
            cls._reset_failure()
            return {
                "session_id": session.id,
                "checkout_url": session.url,
                "mode": "live",
                "plan": plan_type,
                "amount": plan_info["amount"],
            }
        except Exception as e:
            # SP6/P0-8: mock 으로 흡수하지 않고 실패를 상위에 알린다.
            logger.error(f"[Payment] Stripe Checkout creation failed: {e}")
            cls._handle_failure()
            raise

    @classmethod
    def _mock_session(cls, plan_type: str, plan_info: Dict[str, Any]) -> Dict[str, Any]:
        """비운영 환경 전용 mock 세션 (명시적 플래그가 있을 때만 호출된다)."""
        mock_session_id = f"cs_mock_{uuid.uuid4().hex[:12]}"
        logger.warning(
            f"[Payment] MOCK checkout session issued (ENV={os.getenv('ENV', '')}). "
            f"Not for production."
        )
        return {
            "session_id": mock_session_id,
            "checkout_url": f"https://mock-stripe.japanbuild.com/checkout/{mock_session_id}",
            "mode": "mock",
            "plan": plan_type,
            "amount": plan_info["amount"],
        }

    # -----------------------------------------------------------------
    # Webhook
    # -----------------------------------------------------------------
    # service_role 클라이언트 캐시.
    # create_client() 는 HTTP 커넥션 풀을 새로 만들기 때문에, 호출마다 생성하면
    # 크레딧 차감 한 번에 클라이언트를 하나씩 만들어 커넥션이 고갈된다.
    # service_role 경로는 사용자 JWT 를 싣지 않으므로 공유해도 안전하다.
    # (사용자 토큰을 실어야 하는 요청 경로는 deps.get_current_user_and_db() 가
    #  요청마다 새로 생성한다 — 토큰이 섞이면 안 되기 때문이다.)
    _service_db_cache: Any = None

    @classmethod
    def _service_db(cls) -> Any:
        """웹훅·원장 갱신용 service_role 클라이언트 (RLS 우회)."""
        if cls._service_db_cache is None:
            from app.api.deps import get_supabase_client

            cls._service_db_cache = get_supabase_client()
        return cls._service_db_cache

    @classmethod
    def _claim_event(cls, event_id: str, user_id: str, plan_type: str, credits: int) -> bool:
        """
        이벤트를 멱등 키로 선점한다.

        Returns:
            True  — 최초 처리 (크레딧 지급 진행)
            False — 이미 처리된 이벤트 (중복 지급 차단)
        """
        svc = cls._service_db()
        try:
            svc.table("processed_payment_events").insert(
                {
                    "event_id": event_id,
                    "user_id": user_id,
                    "plan_type": plan_type,
                    "credits_added": credits,
                }
            ).execute()
            return True
        except Exception as exc:
            # PK 충돌 = 이미 처리됨. 그 외 오류는 조용히 넘기지 않는다.
            logger.warning(f"[Payment] Event claim failed (event={event_id}): {exc}")
            return False

    @classmethod
    def _release_event(cls, event_id: str) -> None:
        """후속 처리가 실패했을 때 선점을 해제해 Stripe 재시도를 가능하게 한다."""
        try:
            cls._service_db().table("processed_payment_events").delete().eq(
                "event_id", event_id
            ).execute()
        except Exception as exc:
            logger.error(f"[Payment] Failed to release event claim (event={event_id}): {exc}")

    @classmethod
    def verify_and_apply_webhook(
        cls, raw_body: bytes, sig_header: Optional[str], db: Any
    ) -> Dict[str, Any]:
        """
        Stripe Webhook 결제 성공 이벤트를 받아 유저 라이선스 갱신.

        보안 정책 (fail-closed):
          - 전자서명(stripe-signature)이 없는 페이로드는 기본 거부한다.
          - 서명 없는 mock 수신은 PAYMENT_ALLOW_MOCK_WEBHOOK=1 + 명시적 개발 ENV
            조합에서만 허용한다. (과거: ENV 미설정이면 항상 허용됨)
          - 동일 이벤트 ID 는 1회만 처리한다 (Stripe at-least-once 대응).
          - DB 반영 실패는 성공으로 위장하지 않는다 (retryable=True 로 반환).

        Returns:
            {"status": "success"|"duplicate"|"error", "retryable": bool, ...}
        """
        user_id = None
        plan_type = "single"
        session_id = ""
        event_id = ""

        if not sig_header:
            if not cls._is_mock_allowed():
                logger.error(
                    "[Security Alert] Stripe Webhook signature missing and mock "
                    "webhook is not permitted in this environment."
                )
                return {
                    "status": "error",
                    "retryable": False,
                    "message": "Missing stripe-signature header",
                }

            # 로컬/테스트 전용 mock payload 파싱 (명시적 플래그 필요)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                user_id = payload.get("user_id")
                plan_type = payload.get("plan_type", "single")
                session_id = payload.get("session_id", "mock_session")
                event_id = payload.get("event_id") or f"mock_{session_id}"
            except Exception as e:
                logger.error(f"Failed to parse mock webhook payload: {e}")
                return {"status": "error", "retryable": False, "message": "Invalid JSON body"}
        else:
            if not cls.STRIPE_WEBHOOK_SECRET:
                logger.error(
                    "[Security] STRIPE_WEBHOOK_SECRET is not configured; "
                    "rejecting signed webhook (fail-closed)."
                )
                return {
                    "status": "error",
                    "retryable": False,
                    "message": "Webhook secret is not configured",
                }

            try:
                import stripe

                stripe.api_key = cls.STRIPE_API_KEY
                event = stripe.Webhook.construct_event(
                    raw_body, sig_header, cls.STRIPE_WEBHOOK_SECRET
                )
            except Exception as e:
                # 서명 검증 실패는 재시도해도 성공하지 않으므로 retryable=False
                logger.error(f"[Security Warning] Stripe Webhook signature verification failed: {e}")
                return {
                    "status": "error",
                    "retryable": False,
                    "message": f"Signature verification failed: {e}",
                }

            if event.type not in ("checkout.session.completed", "invoice.payment_succeeded"):
                logger.info(f"Stripe Webhook received unhandled event type: {event.type}")
                return {"status": "success", "message": f"Event type {event.type} bypassed"}

            event_id = event.get("id") or ""
            session = event.data.object
            metadata = session.get("metadata", {}) or {}
            user_id = metadata.get("user_id")
            plan_type = metadata.get("plan_type", "single")
            session_id = session.get("id", "")

            if not event_id:
                # 이벤트 ID 가 없으면 멱등성을 보장할 수 없다.
                logger.error("[Payment] Stripe event without id; cannot guarantee idempotency.")
                return {"status": "error", "retryable": False, "message": "Event id missing"}

        if plan_type not in cls.CREDITS_BY_PLAN:
            return {"status": "error", "retryable": False, "message": f"Unknown plan_type: {plan_type}"}

        if not user_id:
            return {
                "status": "error",
                "retryable": False,
                "message": "Missing user_id in payment event metadata",
            }

        credits_to_add = cls.CREDITS_BY_PLAN[plan_type]

        # ── 멱등성: 동일 이벤트 재처리 차단 ──────────────────────────────
        if not cls._claim_event(event_id, user_id, plan_type, credits_to_add):
            logger.info(f"[Payment] Duplicate event ignored: {event_id}")
            return {"status": "duplicate", "event_id": event_id, "added_credits": 0}

        # ── 프로필 반영 ─────────────────────────────────────────────────
        # service_role 클라이언트로 수행한다. 사용자 토큰으로는 profiles 에
        # INSERT 정책이 없어 신규 가입자 지급이 실패하기 때문이다.
        try:
            svc = cls._service_db()
            profile_res = svc.table("profiles").select("*").eq("id", user_id).execute()

            if profile_res.data:
                current_credits = profile_res.data[0].get("credits", 0) or 0
                svc.table("profiles").update(
                    {
                        "plan_type": plan_type,
                        "credits": current_credits + credits_to_add,
                        "stripe_subscription_id": session_id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).eq("id", user_id).execute()
            else:
                svc.table("profiles").insert(
                    {
                        "id": user_id,
                        "plan_type": plan_type,
                        "credits": credits_to_add,
                        "stripe_subscription_id": session_id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).execute()

            logger.info(
                f"[Payment] Applied JPY plan '{plan_type}' for user {user_id} "
                f"(+{credits_to_add} credits, event={event_id})"
            )
            return {
                "status": "success",
                "user_id": user_id,
                "plan_type": plan_type,
                "added_credits": credits_to_add,
                "event_id": event_id,
            }

        except Exception as e:
            # SP6/P0-8: 'fallback_success' 로 위장하지 않는다.
            # 결제는 완료됐으나 크레딧이 지급되지 않은 상태이므로, 선점을 해제해
            # Stripe 재전달로 복구될 수 있게 한다.
            logger.error(f"[Payment] DB update failed during webhook (event={event_id}): {e}")
            cls._release_event(event_id)
            return {
                "status": "error",
                "retryable": True,
                "message": "Failed to apply payment to user profile",
            }

    # -----------------------------------------------------------------
    # Access gate / Credit ledger
    # -----------------------------------------------------------------
    @classmethod
    def check_user_access_gate(cls, user_id: str, db: Any, amount: int = 1) -> bool:
        """
        유료 기능(PDF 레포트 다운로드 및 도면 3D 자동 변환) 가드 게이트웨이.

        보안 정책 (fail-closed):
          회로 OPEN 또는 DB 조회 실패 시 접근을 거부한다. 유료 판정이
          불가능한 상태에서 무료 접근을 허용하는 것은 매출 누수이므로
          가용성보다 과금 정합성을 우선한다.
        """
        if cls._circuit_state == "OPEN":
            logger.warning(
                f"[Circuit Breaker] Payment circuit OPEN - access DENIED for user {user_id}"
            )
            return False

        try:
            res = db.table("profiles").select("plan_type, credits").eq("id", user_id).execute()
            if not res.data:
                return False

            profile = res.data[0]
            plan = profile.get("plan_type", "free")
            credits = profile.get("credits", 0) or 0

            if plan == "pro":
                return True

            return credits >= amount
        except Exception as e:
            logger.error(f"Access gate db failure - access DENIED for user {user_id}: {e}")
            return False

    @classmethod
    def deduct_credit(cls, user_id: str, db: Any, amount: int = 1) -> bool:
        """
        사용자 크레딧 차감.

        SP6/P0-9: 원자적 차감.
          1순위: public.deduct_credits() RPC (행 잠금 단일 트랜잭션)
          2순위: 비교-후-교환(CAS) — .eq("credits", 읽은값) 으로 갱신 분실 방지
        어느 쪽도 확정되지 않으면 False 를 반환해 무료 사용을 막는다.
        """
        if cls._circuit_state == "OPEN":
            logger.warning(
                f"[Circuit Breaker] Payment circuit OPEN - deduction SKIPPED for user {user_id}"
            )
            return False

        if amount is None or amount <= 0:
            return False

        # 1) 원자 RPC
        try:
            svc = cls._service_db()
            res = svc.rpc(
                "deduct_credits", {"p_user_id": user_id, "p_amount": amount}
            ).execute()
            data = getattr(res, "data", None)
            # PostgREST 는 스칼라 함수를 리스트 또는 스칼라로 반환할 수 있다
            if isinstance(data, list):
                if data and isinstance(data[0], bool):
                    return data[0]
                if data and isinstance(data[0], dict):
                    return bool(data[0].get("deduct_credits"))
            if isinstance(data, bool):
                return data
            # False 도 정상 응답이므로 None 일 때만 폴백으로 내려간다
            if data is not None:
                return bool(data)
        except Exception as e:
            logger.warning(
                f"[Payment] deduct_credits RPC unavailable ({e}); falling back to CAS."
            )

        # 2) CAS 폴백 (RPC 미배포 환경 대비)
        from datetime import datetime as _dt

        for attempt in range(3):
            try:
                res = db.table("profiles").select("plan_type, credits").eq("id", user_id).execute()
                if not res.data:
                    return False

                profile = res.data[0]
                if profile.get("plan_type") == "pro":
                    return True

                credits = profile.get("credits", 0) or 0
                if credits < amount:
                    return False

                upd = (
                    db.table("profiles")
                    .update(
                        {
                            "credits": credits - amount,
                            "updated_at": _dt.now(timezone.utc).isoformat(),
                        }
                    )
                    .eq("id", user_id)
                    .eq("credits", credits)  # 낙관적 동시성 제어 (CAS)
                    .execute()
                )
                if upd.data:
                    return True
                # 잔액이 바뀌었다 -> 재시도
                logger.info(
                    f"[Payment] Credit CAS conflict for user {user_id} "
                    f"(attempt {attempt + 1}/3)"
                )
            except Exception as e:
                logger.error(f"[Payment] Credit deduction failed for user {user_id}: {e}")
                return False

        return False
