from contextlib import asynccontextmanager
from time import perf_counter

import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.api import api_router
from app.core.database import get_engine, init_development_database
from app.core.observability import (
    configure_logging,
    log_structured,
    request_trace_id,
    reset_current_trace_id,
    set_current_trace_id,
)
from app.core.redis import get_redis_connection

logger = logging.getLogger(__name__)
HEALTH_CHECK_TIMEOUT_SECONDS = 2.0

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_development_database()
    yield


app = FastAPI(title="Parserly ATS Resume Analyzer API", lifespan=lifespan)


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    trace_id = request_trace_id(request)
    trace_token = set_current_trace_id(trace_id)
    started_at = perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = trace_id
        return response
    finally:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        log_structured(
            logger,
            logging.INFO if status_code < 500 else logging.ERROR,
            "http_request",
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=duration_ms,
            user_id=getattr(request.state, "user_id", None),
        )
        reset_current_trace_id(trace_token)


app.include_router(api_router)


@app.get("/health", tags=["health"])
@app.get("/api/v1/health", tags=["health"], include_in_schema=False)
async def health_check() -> JSONResponse:
    checks = {
        "api": {"ok": True},
        "database": await _run_health_check(_check_database),
        "redis": await _run_health_check(_check_redis),
    }
    healthy = all(check["ok"] for check in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "checks": checks,
        },
        headers={"Cache-Control": "no-store"},
    )


async def _run_health_check(check):
    try:
        await asyncio.wait_for(check(), timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
    except Exception as exc:
        return {"ok": False, "error": exc.__class__.__name__}

    return {"ok": True}


async def _check_database() -> None:
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _check_redis() -> None:
    redis_client = get_redis_connection()
    if not await redis_client.ping():
        raise RuntimeError("Redis ping failed")
