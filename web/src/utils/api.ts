// 환경변수 기반 백엔드 API 서버 주소 관리 (부재 시 로컬 Uvicorn 포트 8000 fallback)
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
