import os
from celery import Celery
import logging

logger = logging.getLogger(__name__)

# Redis 브로커 URL (Docker 환경 고려)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
)

# [하네스 서킷 브레이커 - 로컬/오프라인 환경 무장애 보장]
# Docker/Redis가 설치되지 않았거나 오프라인 개발 모드인 경우,
# 백엔드가 정지되지 않고 모든 비동기 태스크를 동기(Eager) 방식으로 실행하도록 자동 폴백합니다.
is_local_dev = os.getenv("ENV") != "production"

if is_local_dev:
    try:
        import redis
        client = redis.from_url(REDIS_URL, socket_timeout=1.0)
        client.ping()
        logger.info("[Harness] Connected to Redis successfully. Celery running in standard mode.")
    except Exception as e:
        logger.warning(
            f"[Harness Fallback] Redis connection failed ({str(e)}). "
            "Activating 'task_always_eager = True' with memory backend for seamless local in-process execution."
        )
        celery_app.conf.update(
            broker_url="memory://",
            result_backend="cache+memory://",
            task_always_eager=True,
            task_eager_propagates=True,
            task_store_eager_result=True,
        )

