# Python 3.10-slim 기반
FROM python:3.10-slim

# 시스템 라이브러리 설치 (OpenCV, IfcOpenShell 등 의존성)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 업로드 및 출력 폴더 권한 설정
RUN mkdir -p uploads out && chmod 777 uploads out

# 서버 실행 (FastAPI 기본)
# 워커는 docker-compose에서 entrypoint를 덮어씌워 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
