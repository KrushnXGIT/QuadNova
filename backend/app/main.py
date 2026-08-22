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
from fastapi.responses import HTMLResponse, JSONResponse

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
    docs_url=None,
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.get("/docs", include_in_schema=False)
async def custom_docs() -> HTMLResponse:
        """Serve interactive API docs in the HemoScan visual language."""
        return HTMLResponse(
                content="""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#faf3e7">
    <title>HemoScan AI | API documentation</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        :root { --cream: #faf3e7; --paper: #f4f0e8; --white: #fff; --peach: #fde8d8;
            --terracotta: #d97757; --terracotta-dark: #c15f3c; --ink: #141413;
            --muted: #6b6560; --line: #e8e0d4; }
        * { box-sizing: border-box; }
        body { margin: 0; background: var(--cream); color: var(--ink);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; }
        .masthead { display: flex; align-items: center; justify-content: space-between; gap: 20px;
            width: min(1120px, calc(100% - 40px)); margin: 0 auto; padding: 28px 0 24px; }
        .brand { display: flex; align-items: center; gap: 10px; color: var(--terracotta);
            font-size: 13px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
        .brand i { width: 12px; height: 12px; display: block; border-radius: 50%; background: var(--terracotta); }
        .masthead p { margin: 0; color: var(--muted); font-size: 13px; }
        .swagger-ui { width: min(1120px, calc(100% - 40px)); margin: 0 auto; }
        .swagger-ui .topbar { display: none; }
        .swagger-ui .information-container { padding: 28px 0 20px; }
        .swagger-ui .info { margin: 0; }
        .swagger-ui .info .title { color: var(--ink); font-size: 30px; letter-spacing: -.03em; }
        .swagger-ui .info .description p, .swagger-ui .info li { color: var(--muted); line-height: 1.6; }
        .swagger-ui .scheme-container { padding: 16px 20px; background: var(--paper);
            box-shadow: none; border: 1px solid var(--line); border-radius: 10px; }
        .swagger-ui .opblock-tag { color: var(--ink); border-bottom-color: var(--line); font-size: 18px; }
        .swagger-ui .opblock { border-radius: 10px; box-shadow: none; border-color: var(--line); }
        .swagger-ui .opblock .opblock-summary { border-color: var(--line); }
        .swagger-ui .opblock.opblock-get { background: rgba(61, 153, 112, .07); border-color: #b8d9c8; }
        .swagger-ui .opblock.opblock-post { background: rgba(217, 119, 87, .07); border-color: #efc5b4; }
        .swagger-ui .btn.authorize { color: var(--terracotta-dark); border-color: var(--terracotta); }
        .swagger-ui .btn.execute { background: var(--terracotta); border-color: var(--terracotta); }
        .swagger-ui .btn.execute:hover { background: var(--terracotta-dark); }
        .swagger-ui .model-title, .swagger-ui section.models h4 { color: var(--ink); }
        .swagger-ui .models { border-color: var(--line); }
        @media (max-width: 600px) { .masthead { width: calc(100% - 28px); padding-top: 20px; }
            .masthead p { display: none; } .swagger-ui { width: calc(100% - 28px); }
            .swagger-ui .information-container { padding-top: 18px; }
            .swagger-ui .info .title { font-size: 25px; } }
    </style>
</head>
<body>
    <header class="masthead"><div class="brand"><i></i> HemoScan AI</div>
        <p>Non-invasive anaemia screening API</p></header>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = () => SwaggerUIBundle({
            url: '/openapi.json', dom_id: '#swagger-ui', deepLinking: true,
            persistAuthorization: true, displayRequestDuration: true,
            presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
            layout: 'BaseLayout'
        });
    </script>
</body>
</html>""",
                headers={"Cache-Control": "no-store"},
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
