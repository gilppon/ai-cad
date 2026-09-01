import logging
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# 환경설정 (SP6/P0-1)
#
# 과거: SUPABASE_URL / SUPABASE_KEY / SUPABASE_JWT_SECRET 이 플레이스홀더 기본값을
#       가져, 환경변수 누락 상태로도 서버가 기동되었다. 잘못된 URL은 런타임에
#       조용한 실패로 이어져 원인 추적이 불가능했다.
# 현재: 운영 환경에서 미설정 시 명시적으로 기동을 거부한다 (fail-closed).
# ---------------------------------------------------------------------------
def _is_production() -> bool:
    """
    운영 환경 여부를 **호출 시점**에 평가한다.

    과거: 모듈 임포트 시점의 스냅샷(`_IS_PRODUCTION = os.getenv("ENV") == "production"`).
          프로세스 기동 후 ENV 를 바꾸는 일은 없지만, 이 방식에는 두 가지 문제가 있다.
            1. `load_dotenv()` 보다 먼저 평가되면 .env 값이 반영되지 않아
               운영 배포가 개발 모드로 조용히 기동될 수 있다.
            2. 운영 가드(우회 무시, 기본 시크릿 거부)를 테스트로 검증할 수 없다.
    현재: 매 호출 시점에 평가한다. env 조회는 마이크로초 단위로 저렴하다.
    """
    return os.getenv("ENV", "development") == "production"

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# 사용자 요청 대리용 anon 키 — 요청마다 사용자 JWT를 실어 RLS를 통과시킨다.
SUPABASE_ANON_KEY = os.getenv("SUPABASE_KEY", "")
# 신뢰 백엔드(Celery 워커 / 서버 내부 작업) 전용 service_role 키 — RLS를 우회한다.
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

if _is_production():
    _missing = [
        name
        for name, value in (
            ("SUPABASE_URL", SUPABASE_URL),
            ("SUPABASE_KEY", SUPABASE_ANON_KEY),
            ("SUPABASE_JWT_SECRET", JWT_SECRET),
        )
        if not value
    ]
    if _missing:
        raise RuntimeError(
            f"Missing required environment variables in production: {', '.join(_missing)}"
        )
else:
    # 로컬 개발 편의를 위해서만 플레이스홀더를 허용한다.
    SUPABASE_URL = SUPABASE_URL or "https://your-project-url.supabase.co"
    SUPABASE_ANON_KEY = SUPABASE_ANON_KEY or "your-anon-key"
    JWT_SECRET = JWT_SECRET or "your-jwt-secret"

security = HTTPBearer()


def _auth_bypass_enabled() -> bool:
    """
    명시적으로 설정된 로컬 개발 우회 플래그만 허용 (기본값: 비활성).
    운영(production) 환경에서는 설정 여부와 무관하게 절대 우회를 허용하지 않는다.
    """
    return os.getenv("ALLOW_AUTH_BYPASS", "") == "1" and not _is_production()


def _build_client(key: str, access_token: str | None = None) -> Client:
    """
    Supabase 클라이언트를 생성한다.

    access_token 이 주어지면 PostgREST 요청에 사용자 JWT를 실어 보낸다.
    이 토큰이 있어야 Supabase RLS 의 auth.uid() 가 요청 주체로 해석된다.

    과거: 무토큰 anon 클라이언트를 사용해 RLS 가 항상 NULL 로 평가되었고,
          애플리케이션 레벨 소유권 검증이 유일한 방어선이었다 (C1 결함).

    참고: postgrest.auth() 는 클라이언트 내부 상태를 변경하므로, 요청 간
          클라이언트를 공유하면 토큰이 섞인다. 요청마다 생성하는 것이 안전하다.
          (성능 최적화가 필요하면 요청 스코프 캐시를 별도로 도입할 것)
    """
    client = create_client(SUPABASE_URL, key or SUPABASE_ANON_KEY)

    if not access_token:
        return client

    # supabase-py v2: postgrest.auth(token) 이 Authorization 헤더를 설정한다.
    try:
        client.postgrest.auth(access_token)
        return client
    except Exception as exc:  # 버전별 API 차이 대비
        logger.warning(f"[Auth] postgrest.auth() unavailable ({exc}); falling back to header injection.")

    try:
        headers = dict(getattr(getattr(client, "options", None), "headers", None) or {})
        headers["Authorization"] = f"Bearer {access_token}"
        client.options.headers.update(headers)
    except Exception as exc:
        # 토큰을 실을 수 없으면 RLS 가 요청을 거부한다. 이 상태로 진행하면
        # 500/404 로 이어지므로 명시적으로 실패시켜 조기 탐지되게 한다.
        logger.error(f"[Auth] Failed to attach user token to Supabase client: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to establish an authenticated database session.",
        )

    return client


def get_supabase_client() -> Client:
    """
    신뢰 백엔드(Celery 워커 등)용 service_role 클라이언트.

    RLS 를 우회하므로 **사용자 요청 경로에서 절대 사용하면 안 된다.**
    사용자 요청은 반드시 get_current_user_and_db() 를 사용할 것.
    """
    if not SUPABASE_SERVICE_ROLE_KEY:
        # 서비스 키 미설정 시 anon 으로 동작하면 워커의 상태 갱신이 RLS 에 막혀
        # 조용히 실패한다. 개발 단계에서 즉시 드러나도록 경고를 남긴다.
        logger.warning(
            "[Supabase] SUPABASE_SERVICE_ROLE_KEY is not set; worker DB writes "
            "will be subject to RLS and may be rejected."
        )
        return _build_client(SUPABASE_ANON_KEY)
    return _build_client(SUPABASE_SERVICE_ROLE_KEY)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verifies the Supabase JWT token and returns the user ID (sub).

    보안 정책 (SP1/S-1, fail-closed):
      - 만료·변조·서명 불일치 토큰은 ENV와 무관하게 항상 401로 거부한다.
      - 무인증 우회는 ALLOW_AUTH_BYPASS=1 이 명시적으로 설정된 비운영 환경에서만 허용된다.
    """
    token = credentials.credentials

    if _is_production() and JWT_SECRET == "your-jwt-secret":
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


async def get_current_user_and_db(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_id: str = Depends(get_current_user),
):
    """
    사용자 요청 처리용 인증 컨텍스트.

    Returns:
        {"user_id": str, "db": Client}

    db 는 사용자 JWT를 실은 클라이언트이므로, PostgREST 의 RLS 가 auth.uid() 를
    요청 주체로 해석한다. 애플리케이션 레벨 소유권 필터와 결합해 2중 방어를
    구성한다 (C1 대응).
    """
    # ALLOW_AUTH_BYPASS 로 승격된 로컬 샌드박스 사용자는 실제 토큰이 없다.
    token = credentials.credentials
    if _auth_bypass_enabled() and user_id == "user_123":
        token = None

    return {"user_id": user_id, "db": _build_client(SUPABASE_ANON_KEY, token)}


def require_project(db: Client, project_id: str, user_id: str, select: str = "id") -> dict:
    """
    프로젝트를 **소유자 기준으로** 조회한다. 없으면 404.

    과거: `.eq("id", project_id)` 단독 조회 — 인증된 사용자라면 누구나 타인의
          project_id 로 접근할 수 있었다 (IDOR, C1).
    현재: `.eq("id", ...).eq("user_id", ...)` 로 소유권을 강제한다. RLS 가
          켜져 있어도, 꺼져 있어도 이 필터가 방어선이 된다.

    Raises:
        HTTPException 404 — 프로젝트가 없거나 본인 소유가 아님.
                            (어느 쪽인지 구분하지 않는다: 타인 프로젝트의
                             존재 여부 열람을 막기 위함)
        HTTPException 503 — DB 조회 자체가 실패. 과거에는 이 경우 인증 검사를
                            건너뛰고 진행하는 fail-open 결함이 있었다.
    """
    try:
        res = (
            db.table("projects")
            .select(select)
            .eq("id", project_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        # SP6/P0-1: DB 장애를 인증 우회의 기회로 만들지 않는다 (fail-closed).
        logger.error(f"[Auth] Project ownership check failed for project={project_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify project ownership. Please retry shortly.",
        )

    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    return res.data[0]
