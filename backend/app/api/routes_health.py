"""GET /health"""
from fastapi import APIRouter
from ..schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Simple liveness probe."""
    return HealthResponse(status="ok", service="anaemia-screening-backend")
