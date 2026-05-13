import functools
import logging

class CircuitBreaker:
    def __init__(self, max_failures=3):
        self.max_failures = max_failures
        self.failures = 0
        self.is_open = False

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.is_open:
                logging.error(f"[CircuitBreaker] Blocked call to {func.__name__} due to previous failures.")
                raise RuntimeError(f"Circuit breaker is OPEN for {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                self.failures = 0  # Reset on success
                return result
            except Exception as e:
                self.failures += 1
                logging.warning(f"[CircuitBreaker] Failure {self.failures}/{self.max_failures} in {func.__name__}: {e}")
                if self.failures >= self.max_failures:
                    self.is_open = True
                    logging.critical(f"[CircuitBreaker] OPENING circuit for {func.__name__}")
                raise e
        return wrapper

# Global instance for general use
default_breaker = CircuitBreaker(max_failures=3)


def circuit_breaker(failure_threshold: int = 3, recovery_timeout: int = 60):
    """
    Factory decorator for CircuitBreaker.
    Usage: @circuit_breaker(failure_threshold=3, recovery_timeout=60)
    """
    return CircuitBreaker(max_failures=failure_threshold)

