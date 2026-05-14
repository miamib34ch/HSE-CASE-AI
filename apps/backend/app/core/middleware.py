import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config.settings import get_settings


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-Id", str(uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._requests: defaultdict[str, list[float]] = defaultdict(list)
        self._settings = get_settings()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        identifier = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60
        bucket = [value for value in self._requests[identifier] if value >= window_start]
        if len(bucket) >= self._settings.api_rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Превышен лимит запросов")
        bucket.append(now)
        self._requests[identifier] = bucket
        return await call_next(request)
