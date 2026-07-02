import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project-url.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "your-jwt-secret")

security = HTTPBearer()

def get_supabase_client() -> Client:
    """Returns a Supabase client instance."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verifies the Supabase JWT token and returns the user ID (sub).
    Supports a mock fallback circuit breaker for local/offline B2B sandbox environments.
    """
    token = credentials.credentials
    
    # [하네스 서킷 브레이커] 로컬 샌드박스 또는 Mock 세션 대응 (통신 장애 및 로컬 무인증 무장애 확보)
    is_mock_token = token in ("mock-key", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock-key") or token.endswith(".mock-key")
    is_local_dev = JWT_SECRET == "your-jwt-secret" or os.getenv("ENV") in ("development", "local", "test")
    
    if is_mock_token and is_local_dev:
        # 가상의 B2B 적격 임기 대표자 ID 반환하여 프론트/백 크래시 전면 방지
        return "user_123"
        
    try:
        # Verify the JWT token using the Supabase JWT secret
        # Supabase uses HS256 algorithm by default
        payload = jwt.decode(
            token, 
            JWT_SECRET, 
            algorithms=["HS256"], 
            options={"verify_aud": False}
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            if is_local_dev:
                return "user_123"
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials (missing sub)",
            )
        return user_id
    except jwt.ExpiredSignatureError:
        if is_local_dev:
            return "user_123"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        if is_local_dev:
            # 로컬 개발/오프라인 환경일 경우 검증 오류가 나더라도 무중단 UX를 위해 user_123으로 자동 포워딩
            return "user_123"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )

# Dependency wrapper to get both user_id and supabase client
async def get_current_user_and_db(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase_client)
):
    return {"user_id": user_id, "db": db}
