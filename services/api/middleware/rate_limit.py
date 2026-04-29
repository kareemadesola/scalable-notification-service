"""
Redis-backed sliding window rate limiter middleware.
Default: 100 requests per 60 seconds per IP.
Returns HTTP 429 with Retry-After header when exceeded.
"""
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from cache.redis_client import get_redis

RATE_LIMIT_REQUESTS = 100   # max requests
RATE_LIMIT_WINDOW = 60      # per N seconds

# Endpoints exempt from rate limiting
EXEMPT_PATHS = {"/health", "/metrics"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        window_key = int(time.time() // RATE_LIMIT_WINDOW)
        redis_key = f"api_rate:{client_ip}:{window_key}"

        redis = await get_redis()
        pipe = redis.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, RATE_LIMIT_WINDOW)
        results = await pipe.execute()
        request_count = results[0]

        if request_count > RATE_LIMIT_REQUESTS:
            retry_after = RATE_LIMIT_WINDOW - (int(time.time()) % RATE_LIMIT_WINDOW)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(max(0, RATE_LIMIT_REQUESTS - request_count))
        return response
