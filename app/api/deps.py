import logging
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project-url.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "your-jwt-secret")

security = HTTPBearer()


def _auth_bypass_enabled() -> bool:
    """
    명시적으로 설정된 로컬 개발 우회 플래그만 허용 (기본값: 비활성).
    운영(production) 환경에서는 설정 여부와 무관하게 절대 우회를 허용하지 않는다.
    """
    return os.getenv("ALLOW_AUTH_BYPASS", "") == "1" and os.getenv("ENV") != "production"

def get_supabase_client() -> Client:
    """Returns a Supabase client instance."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verifies the Supabase JWT token and returns the user ID (sub).

    보안 정책 (SP1/S-1, fail-closed):
      - 만료·변조·서명 불일치 토큰은 ENV와 무관하게 항상 401로 거부한다.
      - 무인증 우회는 ALLOW_AUTH_BYPASS=1 이 명시적으로 설정된 비운영 환경에서만 허용된다.
    """
    token = credentials.credentials

    if os.getenv("ENV") == "production" and JWT_SECRET == "your-jwt-secret":
        # 기본 시크릿으로 운영 배포된 경우 조용한 전면 우회보다 기동 실패가 안전하다.
        raise RuntimeError("SUPABASE_JWT_SECRET must be configured before running in production.")

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
    except jwt.PyJWTError as e:
        if _auth_bypass_enabled():
            logger.warning("[Auth] ALLOW_AUTH_BYPASS is active: invalid token promoted to local sandbox user.")
            return "user_123"
        detail = "Token has expired" if isinstance(e, jwt.ExpiredSignatureError) else f"Invalid token: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    user_id: str = payload.get("sub")
    if not user_id:
        if _auth_bypass_enabled():
            logger.warning("[Auth] ALLOW_AUTH_BYPASS is active: token without sub promoted to local sandbox user.")
            return "user_123"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials (missing sub)",
        )
    return user_id

# Dependency wrapper to get both user_id and supabase client
async def get_current_user_and_db(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase_client)
):
    return {"user_id": user_id, "db": db}
