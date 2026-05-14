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
    """
    token = credentials.credentials
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials (missing sub)",
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
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
