"""
FastAPI application entry point.

Startup order:
  1. Configure logging
  2. Load model adapter (once)
  3. Register routes
  4. Apply CORS middleware
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .core.logging_config import configure_logging, get_logger
from .services.ai_service import ai_service
from .api import routes_health, routes_prediction, routes_info

# ── Configure logging before anything else ───────────────────────────────────
configure_logging()
logger = get_logger(__name__)


# ── Lifespan — model loaded here, once ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== HemoScan AI Backend starting up ===")
    ai_service.initialize()
    logger.info("=== Startup complete — ready to serve ===")
    yield
    logger.info("=== HemoScan AI Backend shutting down ===")


# ── App ───────────────────────────────────────────────────────────────────────
settings = get_settings()

app = FastAPI(
    title="HemoScan AI — Anaemia Screening Backend",
    description=(
        "REST API for non-invasive haemoglobin estimation via smartphone imaging. "
        "Research prototype — not for clinical use."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "status": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(routes_health.router)
app.include_router(routes_prediction.router)
app.include_router(routes_info.router)


# ── Root redirect to docs ─────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
