"""GET /api/v1/info"""
from fastapi import APIRouter
from ..schemas.common import InfoResponse
from ..services.ai_service import ai_service

router = APIRouter(prefix="/api/v1", tags=["Info"])


@router.get("/info", response_model=InfoResponse)
async def project_info() -> InfoResponse:
    """Project and model metadata — safe for Flutter to display."""
    status = ai_service.get_model_info()
    model = status.get("model", {})
    return InfoResponse(
        application="HemoScan AI — Non-Invasive Anaemia Screening",
        api_version="1.0.0",
        model_name=model.get("name", "MobileNetV3-small") if isinstance(model, dict) else str(model),
        model_available=bool(status["available"]),
        disclaimer=(
            "This application is a research prototype. Results are screening "
            "estimates only and must not be used for clinical diagnosis. "
            "Confirmatory testing by a qualified healthcare professional "
            "is always recommended."
        ),
    )
