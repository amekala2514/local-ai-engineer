"""Per-IP rate limiting for sensitive endpoints (login).

In-memory, single-process. For multi-worker deployments this would need
to move to Redis, but for the single-user local app this is sufficient.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock


class RateLimiter:
    """Track recent attempts per IP. Block when too many in the window."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds).

        If allowed=False, retry_after_seconds tells the caller how long
        to wait before the oldest attempt falls out of the window.
        """
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            attempts = self._attempts.setdefault(key, deque())
            while attempts and attempts[0] < cutoff:
                attempts.popleft()
            if len(attempts) >= self._max:
                retry_after = max(1, int(self._window - (now - attempts[0])))
                return False, retry_after
            attempts.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        """Clear all attempts for this key (e.g., on successful login)."""
        with self._lock:
            self._attempts.pop(key, None)


# Login: 5 attempts per IP per minute
login_limiter = RateLimiter(max_attempts=5, window_seconds=60)
