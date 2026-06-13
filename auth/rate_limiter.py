"""
Rate Limiter — Simple In-Memory Rate Limiting
===============================================
Tracks request counts per key (IP + endpoint) with a sliding window.

NOTE: For production with multiple backend instances, migrate to
Redis / ElastiCache for distributed rate limiting.
"""

import time
import threading
from typing import Dict, List
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Simple thread-safe in-memory rate limiter using sliding window."""

    def __init__(self):
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Check if a request is allowed under the rate limit.

        Args:
            key: Unique identifier (e.g., "login:192.168.1.1")
            max_requests: Maximum allowed requests in the window
            window_seconds: Time window in seconds

        Returns:
            True if request is allowed

        Raises:
            HTTPException with 429 if rate limit exceeded
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            # Remove expired timestamps
            self._requests[key] = [
                ts for ts in self._requests[key] if ts > cutoff
            ]

            if len(self._requests[key]) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait before trying again.",
                )

            self._requests[key].append(now)
            return True

    def cleanup(self):
        """Remove expired entries to prevent memory leak. Call periodically."""
        now = time.time()
        with self._lock:
            expired_keys = [
                key for key, timestamps in self._requests.items()
                if not timestamps or max(timestamps) < now - 300  # 5 min stale
            ]
            for key in expired_keys:
                del self._requests[key]


def get_client_ip(request: Request) -> str:
    """Extract real client IP, handling proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Module-level singleton
rate_limiter = RateLimiter()
