"""GET /health"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from ..schemas.common import HealthResponse
from ..services.ai_service import ai_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(request: Request) -> HealthResponse | HTMLResponse:
        """Return JSON for clients, or a human-readable status page in a browser."""
        if "text/html" not in request.headers.get("accept", ""):
                return HealthResponse(status="ok", service="anaemia-screening-backend")

        model_status = ai_service.get_model_info()
        model_ready = bool(model_status.get("available"))
        model_label = "Ready for screening" if model_ready else "Model unavailable"
        model_class = "ready" if model_ready else "waiting"

        return HTMLResponse(
                content=f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#faf3e7">
    <title>HemoScan AI | Server health</title>
    <style>
        :root {{
            --cream: #faf3e7; --paper: #f4f0e8; --white: #fff;
            --peach: #fde8d8; --terracotta: #d97757; --ink: #141413;
            --muted: #6b6560; --line: #e8e0d4; --green: #3d9970;
        }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; min-height: 100vh; background: var(--cream); color: var(--ink);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; }}
        main {{ width: min(680px, calc(100% - 40px)); margin: 0 auto; padding: 12vh 0 48px; }}
        .mark {{ display: inline-flex; align-items: center; gap: 10px; color: var(--terracotta);
            font-size: 13px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }}
        .mark i {{ width: 12px; height: 12px; display: block; border-radius: 50%; background: var(--terracotta); }}
        h1 {{ margin: 24px 0 10px; font-size: clamp(36px, 8vw, 62px); line-height: 1.02;
            letter-spacing: -.045em; font-weight: 800; }}
        .intro {{ max-width: 500px; margin: 0; color: var(--muted); font-size: 17px; line-height: 1.6; }}
        .panel {{ margin-top: 36px; overflow: hidden; background: var(--white); border: 1px solid var(--line);
            border-radius: 14px; box-shadow: 0 18px 45px rgba(80, 55, 35, .07); }}
        .headline {{ display: flex; align-items: center; gap: 14px; padding: 22px 24px; background: var(--peach);
            border-bottom: 1px solid var(--line); font-weight: 750; }}
        .dot {{ width: 11px; height: 11px; border-radius: 50%; background: var(--green);
            box-shadow: 0 0 0 5px rgba(61, 153, 112, .14); }}
        .rows {{ padding: 6px 24px; }}
        .row {{ display: flex; justify-content: space-between; gap: 20px; padding: 17px 0;
            border-bottom: 1px solid var(--line); font-size: 14px; }}
        .row:last-child {{ border-bottom: 0; }}
        .label {{ color: var(--muted); }}
        .value {{ text-align: right; font-weight: 700; }}
        .value.ready {{ color: var(--green); }}
        .value.waiting {{ color: var(--terracotta); }}
        footer {{ display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-top: 22px;
            color: var(--muted); font-size: 12px; line-height: 1.5; }}
        a {{ color: var(--terracotta); font-weight: 700; text-decoration: none; }}
        @media (max-width: 480px) {{ main {{ width: min(100% - 28px, 680px); padding-top: 9vh; }}
            .headline, .rows {{ padding-left: 18px; padding-right: 18px; }} footer {{ align-items: flex-start; flex-direction: column; }} }}
    </style>
</head>
<body>
    <main>
        <div class="mark"><i></i> HemoScan AI</div>
        <h1>Server is online.</h1>
        <p class="intro">The screening backend is reachable and ready to receive requests from your connected device.</p>
        <section class="panel" aria-label="Service status">
            <div class="headline"><span class="dot"></span> All systems responding</div>
            <div class="rows">
                <div class="row"><span class="label">Service</span><span class="value">Anaemia screening backend</span></div>
                <div class="row"><span class="label">API status</span><span class="value ready">Operational</span></div>
                <div class="row"><span class="label">AI model</span><span class="value {model_class}">{model_label}</span></div>
            </div>
        </section>
        <footer><span>Research prototype. Screening estimates are not a diagnosis.</span><a href="/docs">Open API docs</a></footer>
    </main>
</body>
</html>""",
                headers={"Cache-Control": "no-store"},
        )
