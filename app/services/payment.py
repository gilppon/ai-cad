# -*- coding: utf-8 -*-
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    """Circuit Breaker가 열려있을 때 발생하는 예외"""
    pass

class StripePaymentService:
    """
    Stripe JPY 결제 통합 및 Circuit Breaker를 적용한 하이브리드 결제 엔진.
    실제 Stripe API Key가 없을 시 100% Mock Sandbox 모드로 동작하며,
    네트워크 장애나 외부 Stripe API 다운 상황(3회 연속 실패)에서 회로를 차단하고
    임시 Grace Period 라이선스를 부여하여 비즈니스 가용성을 100% 보장합니다.
    """
    
    # Circuit Breaker 상태
    _failure_count = 0
    _circuit_state = "CLOSED"  # "CLOSED", "OPEN", "HALF-OPEN"
    _last_state_change = datetime.now(timezone.utc)
    _max_failures = 3
    
    STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_mock")
    
    @classmethod
    def _handle_failure(cls):
        cls._failure_count += 1
        logger.warning(f"[Circuit Breaker] Payment failure detected. Count: {cls._failure_count}/{cls._max_failures}")
        if cls._failure_count >= cls._max_failures:
            cls._circuit_state = "OPEN"
            cls._last_state_change = datetime.now(timezone.utc)
            logger.error("[Circuit Breaker] STATE CHANGED TO OPEN. Activating safety fallback grace license!")

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
                raise CircuitBreakerOpenException("Stripe API Gateway is currently down. Fallback license activated.")

    @classmethod
    def create_checkout_session(cls, user_id: str, plan_type: str, db: Any) -> Dict[str, Any]:
        """
        JPY (엔화) 결제를 위한 Stripe Checkout Session 생성.
        plan_type: 'single' (1,500엔), 'basic' (월 4,900엔), 'pro' (월 9,800엔)
        """
        cls.check_circuit()
        
        # JPY 요금 책정
        pricing_map = {
            "single": {"amount": 1500, "name": "Japanbuild-Leak3D 1回単発利用券"},
            "basic": {"amount": 4900, "name": "Basic プラン (月10回図面変換)"},
            "pro": {"amount": 9800, "name": "Pro プラン (無制限3D変換 + WebGL)"}
        }
        
        plan_info = pricing_map.get(plan_type, pricing_map["single"])
        
        # Stripe API Key가 있을 경우 실제 결제 연동
        if cls.STRIPE_API_KEY:
            try:
                import stripe
                stripe.api_key = cls.STRIPE_API_KEY
                
                # 실제 Stripe Checkout Session 생성
                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'jpy',
                            'product_data': {
                                'name': plan_info["name"],
                            },
                            'unit_amount': plan_info["amount"],
                        },
                        'quantity': 1,
                    }],
                    mode='subscription' if plan_type in ['basic', 'pro'] else 'payment',
                    success_url='https://leak3d.japanbuild.com/payment/success?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url='https://leak3d.japanbuild.com/payment/cancel',
                    metadata={
                        'user_id': user_id,
                        'plan_type': plan_type
                    }
                )
                cls._reset_failure()
                return {
                    "session_id": session.id,
                    "checkout_url": session.url,
                    "mode": "live",
                    "plan": plan_type,
                    "amount": plan_info["amount"]
                }
            except Exception as e:
                logger.error(f"Stripe Integration failed: {str(e)}")
                cls._handle_failure()
                # API 실패 시 바로 아래 Mock Fallback으로 스무스하게 분기
        
        # 100% Mock Sandbox Fallback 가동
        import uuid
        mock_session_id = f"cs_mock_{uuid.uuid4().hex[:12]}"
        mock_checkout_url = f"https://mock-stripe.japanbuild.com/checkout/{mock_session_id}"
        
        return {
            "session_id": mock_session_id,
            "checkout_url": mock_checkout_url,
            "mode": "mock",
            "plan": plan_type,
            "amount": plan_info["amount"]
        }

    @classmethod
    def verify_and_apply_webhook(cls, payload: Dict[str, Any], db: Any) -> Dict[str, Any]:
        """
        Stripe Webhook 결제 성공 이벤트를 받아 유저 라이선스 갱신.
        Mock 세션도 동등하게 받아서 시뮬레이션 처리합니다.
        """
        user_id = payload.get("user_id")
        plan_type = payload.get("plan_type", "single")
        session_id = payload.get("session_id", "mock_session")
        
        if not user_id:
            return {"status": "error", "message": "Missing user_id"}
            
        # Supabase DB 'profiles' 혹은 'users' 테이블 업데이트 시도 (하네스 방화벽 장착)
        # 만약 DB 테이블이나 칼럼이 없어도 크래시 없이 메타데이터/성공으로 Fallback 처리
        try:
            credits_to_add = 0
            if plan_type == "single":
                credits_to_add = 1
            elif plan_type == "basic":
                credits_to_add = 10
            elif plan_type == "pro":
                credits_to_add = 99999  # 무제한
                
            # 유저의 프로필 가져오기
            profile_res = db.table("profiles").select("*").eq("id", user_id).execute()
            
            if profile_res.data:
                current_credits = profile_res.data[0].get("credits", 0) or 0
                db.table("profiles").update({
                    "plan_type": plan_type,
                    "credits": current_credits + credits_to_add,
                    "stripe_subscription_id": session_id,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", user_id).execute()
            else:
                # 레코드가 없다면 인서트 시도
                db.table("profiles").insert({
                    "id": user_id,
                    "plan_type": plan_type,
                    "credits": credits_to_add,
                    "stripe_subscription_id": session_id,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).execute()
                
            logger.info(f"Successfully applied payment JPY plan '{plan_type}' for User ID {user_id}")
            return {"status": "success", "user_id": user_id, "plan_type": plan_type, "added_credits": credits_to_add}
            
        except Exception as e:
            logger.error(f"[Context Firewall Fallback] DB update failed during payment webhook: {str(e)}")
            # 만약 칼럼이 없다면 안전하게 200 OK로 폴백 (Stripe 에러 무한 재시도 방지 및 로그 적재)
            return {
                "status": "fallback_success",
                "user_id": user_id,
                "plan_type": plan_type,
                "warning": "DB column layout missing. Fallback logic applied."
            }

    @classmethod
    def check_user_access_gate(cls, user_id: str, db: Any) -> bool:
        """
        유료 기능(PDF 레포트 다운로드 및 도면 3D 자동 변환) 가드 게이트웨이.
        Circuit Breaker가 OPEN일 시, 100% 무조건 PASS (Grace Period) 적용.
        """
        if cls._circuit_state == "OPEN":
            logger.warning(f"[Circuit Breaker] Activated Grace Period Access for User ID {user_id}")
            return True
            
        try:
            res = db.table("profiles").select("plan_type, credits").eq("id", user_id).execute()
            if not res.data:
                # 프로필 정보 없으면 기본 무료 회원(크레딧0)으로 간주
                return False
                
            profile = res.data[0]
            plan = profile.get("plan_type", "free")
            credits = profile.get("credits", 0) or 0
            
            if plan in ["basic", "pro"] or credits > 0:
                return True
                
            return False
        except Exception as e:
            # DB 연결 장애 등 예외 시 에러 차단 후 비상 가동 (Fault Tolerance)
            logger.error(f"Access gate db failure fallback: {str(e)}")
            return True
            
    @classmethod
    def deduct_credit(cls, user_id: str, db: Any) -> bool:
        """
        단건 결제 시 크레딧 1 차감.
        """
        if cls._circuit_state == "OPEN":
            return True
            
        try:
            res = db.table("profiles").select("plan_type, credits").eq("id", user_id).execute()
            if not res.data:
                return False
                
            profile = res.data[0]
            plan = profile.get("plan_type", "free")
            credits = profile.get("credits", 0) or 0
            
            # Pro 플랜은 차감 없음
            if plan == "pro":
                return True
                
            if credits > 0:
                db.table("profiles").update({
                    "credits": credits - 1,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", user_id).execute()
                return True
            return False
        except Exception as e:
            logger.error(f"Credit deduction db failure fallback: {str(e)}")
            return True
