"""
Endpoint de health check.
"""

import structlog
from fastapi import APIRouter

from app.core.config import settings
from app.schemas.schemas import HealthResponse

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Verifica se a aplicação está em funcionamento.",
    tags=["System"],
)
async def health_check() -> HealthResponse:
    logger.debug("Health check requested")
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database="sqlite",
        llm_provider=settings.LLM_PROVIDER,
    )
