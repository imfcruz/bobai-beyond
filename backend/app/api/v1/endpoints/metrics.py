"""
Endpoint de métricas — indicadores de desempenho do pipeline multiagente.

GET /api/v1/metrics/summary  → resumo completo de todas as métricas
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.metrics_service import MetricsService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/summary",
    summary="Resumo de métricas do pipeline",
    description=(
        "Calcula métricas de desempenho a partir de dados reais do simulador. "
        "Inclui: volume, distribuição de risco, taxas de confirmação/revisão, "
        "tempo de análise, divergências, falhas por componente, "
        "distribuição de ações e métricas de classificação (quando disponíveis). "
        "Todas as métricas são calculadas em tempo de execução — nenhum valor é estático."
    ),
    tags=["Metrics"],
)
async def get_metrics_summary(db: AsyncSession = Depends(get_db)) -> dict:
    svc = MetricsService(db)
    result = await svc.compute_summary()
    logger.debug("Metrics summary computed", total_txn=result["volume"]["total_transactions"])
    return result
