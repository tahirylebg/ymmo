"""Minimal in-memory login throttling (brute-force protection).

KISS: a single-process dictionary is enough for one app container. With several
replicas this would move to Redis; the interface would not change.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from app.core.exceptions import DomainError


class TooManyAttemptsError(DomainError):
    status_code = 429
    default_message = "Trop de tentatives. Réessayez dans quelques minutes."


class LoginThrottle:
    def __init__(self, max_failures: int = 5, window_seconds: int = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        attempts = self._failures[key]
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()
        return attempts

    def check(self, key: str) -> None:
        with self._lock:
            if len(self._prune(key, time.monotonic())) >= self.max_failures:
                raise TooManyAttemptsError()

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


login_throttle = LoginThrottle()
