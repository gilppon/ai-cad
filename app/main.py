from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import router as api_router

app = FastAPI(
    title="Kodari CAD SaaS API",
    description="CAD PDF to IFC Conversion Engine API",
    version="0.1.0"
)

# CORS 설정 (프론트엔드 연동 대비)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
