import time
import threading
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request, Response, status


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._check_count = 0

    def reset(self) -> None:
        """清空所有限流记录（测试与手动放行场景使用）"""
        with self._lock:
            self._events.clear()
            self._check_count = 0

    def _prune(self, bucket: Deque[float], window_seconds: int, now: float) -> None:
        threshold = now - window_seconds
        while bucket and bucket[0] <= threshold:
            bucket.popleft()

    def _cleanup_empty_buckets(self) -> None:
        if len(self._events) > 1000:
            empty = [k for k, v in self._events.items() if not v]
            for k in empty:
                del self._events[k]

    def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        response: Response | None = None,
    ) -> None:
        now = time.time()
        with self._lock:
            self._check_count += 1
            if self._check_count % 100 == 0:
                self._cleanup_empty_buckets()
            bucket = self._events[key]
            self._prune(bucket, window_seconds, now)
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                if response is not None:
                    response.headers["Retry-After"] = str(retry_after)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="请求过于频繁，请稍后再试",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)


rate_limiter = SlidingWindowRateLimiter()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
