import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import router as api_router

app = FastAPI(
    title="Kodari CAD SaaS API",
    description="CAD PDF to IFC Conversion Engine API",
    version="0.1.0"
)

# CORS 설정 (프로덕션 및 로컬 개발 환경 분리) — SP4/H-3
# allow_credentials=True 상태에서는 브라우저 보안 표준에 의해 와일드카드(*) 오리진 사용이 불가하므로 명시적 도메인 바인딩 적용
environment = os.getenv("ENV", "development")
if environment == "production":
    origins = [
        "https://japanbuild-bim3d.jp",
        "https://www.japanbuild-bim3d.jp",
        "https://japanbuild-bim3d-app.pages.dev"
    ]
else:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

# 배포 환경별 오리진은 ALLOWED_ORIGINS(콤마 구분)로 오버라이드 가능 (SP4/H-3)
if os.getenv("ALLOWED_ORIGINS", "").strip():
    origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    # SP4/H-3: 와일드카드 메서드 축소 - 실제 라우터가 사용하는 메서드만 허용
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


# 라우터 연결
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Welcome to Kodari CAD SaaS API",
        "docs": "/docs",
        "status": "operational"
    }
