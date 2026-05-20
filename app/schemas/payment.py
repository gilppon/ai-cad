# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import Optional

class CheckoutSessionRequest(BaseModel):
    plan_type: str = Field(..., description="요금제 구분: 'single' (건당 1,500엔), 'basic' (월 4,900엔), 'pro' (월 9,800엔)")

class CheckoutSessionResponse(BaseModel):
    session_id: str = Field(..., description="Stripe 세션 식별자")
    checkout_url: str = Field(..., description="Stripe 결제용 리다이렉션 URL")
    mode: str = Field(..., description="결제 연동 모드: 'live' 또는 'mock'")
    plan: str = Field(..., description="선택 요금제")
    amount: int = Field(..., description="결제 금액 (JPY 엔화)")

class PaymentWebhookPayload(BaseModel):
    user_id: str = Field(..., description="대상 사용자 식별자")
    plan_type: str = Field("single", description="구매 요금제")
    session_id: str = Field("mock_session", description="결제 세션 식별자")

class PaymentStatusResponse(BaseModel):
    plan_type: str = Field(..., description="현재 보유 요금제")
    credits: int = Field(..., description="잔여 사용가능 크레딧")
    active: bool = Field(..., description="유료 서비스 접근 허용 상태 여부")
    circuit_state: str = Field("CLOSED", description="결제 게이트웨이 회로 차단 상태 ('CLOSED', 'OPEN')")
