import functools
import logging
import time

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit Breaker with time-based half-open recovery. (SP2/A-1)

    상태 전이:
      CLOSED  - 정상 통과, 연속 실패 max_failures 도달 시 OPEN 전이
      OPEN    - 호출 차단. recovery_timeout 경과 후 HALF-OPEN으로 자동 전이
      HALF-OPEN - 시험 호출 1회 허용. 성공 시 CLOSED 복구, 실패 시 즉시 재OPEN

    v1.0 결함(recovery_timeout 무시, 영구 잠금)은 code_remediation_plan_v1.0 §4 A-1에서 수정.
    """

    def __init__(self, max_failures=3, recovery_timeout=60):
        self.max_failures = max_failures
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.is_open = False
        self._half_open = False
        self._opened_at_monotonic: float | None = None

    def _open(self):
        self.is_open = True
        self._opened_at_monotonic = time.monotonic()
        logger.critical(f"[CircuitBreaker] OPENING circuit for {self._func_name} "
                        f"(recovery after {self.recovery_timeout}s)")

    def _allow_trial(self) -> bool:
        """OPEN 상태에서 recovery_timeout 경과 시 HALF-OPEN 시험을 허용한다."""
        elapsed = time.monotonic() - (self._opened_at_monotonic or 0.0)
        if elapsed >= self.recovery_timeout:
            self._half_open = True
            logger.info(f"[CircuitBreaker] Recovery timeout elapsed ({elapsed:.1f}s) - "
                        f"HALF-OPEN trial for {self._func_name}")
            return True
        return False

    def __call__(self, func):
        self._func_name = func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.is_open and not self._allow_trial():
                logger.error(f"[CircuitBreaker] Blocked call to {func.__name__} due to previous failures.")
                raise RuntimeError(f"Circuit breaker is OPEN for {func.__name__}")

            try:
                result = func(*args, **kwargs)
            except Exception as e:
                if self._half_open:
                    # HALF-OPEN 시험 실패 → 즉시 재차단 및 타이머 리셋
                    self._half_open = False
                    self._open()
                else:
                    self.failures += 1
                    logger.warning(
                        f"[CircuitBreaker] Failure {self.failures}/{self.max_failures} in {func.__name__}: {e}"
                    )
                    if self.failures >= self.max_failures:
                        self._open()
                raise e

            # 성공: CLOSED 완전 복구
            self.failures = 0
            self.is_open = False
            self._half_open = False
            if self._opened_at_monotonic is not None:
                logger.info(f"[CircuitBreaker] Circuit RECOVERED to CLOSED for {func.__name__}")
                self._opened_at_monotonic = None
            return result
        return wrapper


# Global instance for general use
default_breaker = CircuitBreaker(max_failures=3)


def circuit_breaker(failure_threshold: int = 3, recovery_timeout: int = 60):
    """
    Factory decorator for CircuitBreaker.
    Usage: @circuit_breaker(failure_threshold=3, recovery_timeout=60)
    """
    return CircuitBreaker(max_failures=failure_threshold, recovery_timeout=recovery_timeout)
