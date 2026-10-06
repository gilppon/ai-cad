# STATE Phase 3: Python 3.11 통일, 멀티스테이지, non-root, HEALTHCHECK
FROM python:3.11-slim AS base

# 시스템 라이브러리 (OpenCV, IfcOpenShell 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사 (.dockerignore로 uploads/vector_store/sessions/node_modules 제외)
COPY . .

# non-root 실행 + 최소권한 (777 금지)
RUN mkdir -p uploads out \
    && useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app/uploads /app/out
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
