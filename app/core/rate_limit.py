"""Per-identity Redis rate limiting (fixed window). Fail-open without Redis."""

import logging
import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core import security
from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.modules.auth import service as auth_service

logger = logging.getLogger("careerops.ratelimit")

SKIP_EXACT = {"/health", "/ready", "/openapi.json"}
SKIP_PREFIX = ("/docs", "/redoc")
WINDOW_SECONDS = 60


def _limit_per_minute() -> int:
    return get_settings().rate_limit_per_minute


def identity(request: Request) -> str:
    """Stable identity without DB hits: JWT sub → key hash → client IP."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        user_id = security.decode_access_token(auth[7:].strip(), auth_service.auth_secret())
        if user_id is not None:
            return f"user:{user_id}"
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"key:{security.sha256_hex(api_key)[:16]}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


async def allowed(ident: str, limit: int) -> tuple[bool, int]:
    """Fixed-window check. Returns (allowed, retry_after_seconds)."""
    bucket = int(time.time()) // WINDOW_SECONDS
    key = f"ratelimit:{bucket}:{ident}"
    try:
        client = get_redis()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, WINDOW_SECONDS + 5)
    except Exception as exc:
        logger.warning("rate limiter unavailable, allowing: %s", exc)
        return True, 0
    if count > limit:
        retry_after = (bucket + 1) * WINDOW_SECONDS - int(time.time())
        return False, max(retry_after, 1)
    return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject over-limit identities with a 429 envelope (else pass through)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in SKIP_EXACT or path.startswith(SKIP_PREFIX):
            return await call_next(request)
        ok, retry_after = await allowed(identity(request), _limit_per_minute())
        if not ok:
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited", "message": "rate limit exceeded"}},
                headers={
                    "Retry-After": str(retry_after),
                    "X-Request-ID": getattr(request.state, "request_id", "-"),
                },
            )
        return await call_next(request)
