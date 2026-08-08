"""
InferaV22 — Arm Cloud AI Inference Optimization Platform
FastAPI application factory.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.logging_config import configure_logging
from core.metrics import metrics_asgi_app, api_requests_total, api_request_duration_seconds

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    logger.info("InferaV22 starting up...")
    # Initialize database pool
    try:
        from db.connection import get_pool
        await get_pool()
        logger.info("PostgreSQL pool ready")
    except Exception as e:
        logger.warning(f"PostgreSQL unavailable at startup: {e}")

    # Initialize Redis
    try:
        from cache.redis_client import get_redis
        redis = await get_redis()
        await redis.ping()
        logger.info("Redis ready")
    except Exception as e:
        logger.warning(f"Redis unavailable at startup: {e}")

    logger.info(f"InferaV22 started | env={settings.ENVIRONMENT} | version={settings.APP_VERSION}")
    yield

    # Shutdown
    logger.info("InferaV22 shutting down...")
    try:
        from db.connection import close_pool
        await close_pool()
    except Exception:
        pass
    try:
        from cache.redis_client import close_redis
        await close_redis()
    except Exception:
        pass
    logger.info("Shutdown complete")


# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create app
app = FastAPI(
    title="InferaV22 — Arm Cloud AI Inference Optimizer",
    description="Autonomous LLM inference optimization pipeline for Arm Neoverse (Graviton4, Cobalt 100, Axion)",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — explicit origins only, never wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Mount Prometheus metrics endpoint
app.mount("/metrics", metrics_asgi_app)

# Include API routers
from api.runs import router as runs_router
from api.certificates import router as certificates_router
from api.analytics import router as analytics_router
from api.ws import router as ws_router

app.include_router(runs_router)
app.include_router(certificates_router)
app.include_router(analytics_router)
app.include_router(ws_router)

# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness probe. Checks connectivity to all backing services."""
    from db.connection import health_check as db_health
    from cache.redis_client import health_check as redis_health

    db_ok = False
    redis_ok = False
    try:
        db_ok = await db_health()
    except Exception:
        pass
    try:
        redis_ok = await redis_health()
    except Exception:
        pass

    overall = db_ok and redis_ok
    return JSONResponse(
        status_code=status.HTTP_200_OK if overall else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if overall else "degraded",
            "services": {
                "postgresql": "ok" if db_ok else "unavailable",
                "redis": "ok" if redis_ok else "unavailable",
            },
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }
    )


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "InferaV22",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }
