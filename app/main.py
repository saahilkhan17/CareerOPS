"""FastAPI application factory with health checks and standard error envelope."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestIdMiddleware
from app.db.session import get_engine
from app.modules.auth.router import router as auth_router
from app.modules.tracker.router import router as tracker_router

logger = logging.getLogger("careerops.app")

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
}


def error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    """Build the standard error envelope."""
    return {"error": {"code": code, "message": message}}


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(auth_router)
    app.include_router(tracker_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:  # DB down, wrong DSN, etc.
            logger.warning("readiness check failed: %s", exc)
            return JSONResponse(
                status_code=503,
                content=error_body("service_unavailable", "database not reachable"),
            )
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = STATUS_CODES.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) else code
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers={REQUEST_ID_HEADER: getattr(request.state, "request_id", "-")},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "unexpected server error"),
            headers={REQUEST_ID_HEADER: getattr(request.state, "request_id", "-")},
        )

    return app


app = create_app()
