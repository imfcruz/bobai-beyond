"""
Endpoints de Análises de Risco.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import RiskAnalysisResponse
from app.services.bank_service import BankService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=list[RiskAnalysisResponse],
    summary="Listar análises de risco",
    tags=["Risk Analyses"],
)
async def list_risk_analyses(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list:
    svc = BankService(db)
    return await svc.list_risk_analyses(limit, offset)


@router.get(
    "/transaction/{transaction_external_id}",
    response_model=RiskAnalysisResponse,
    summary="Análise de risco de uma transação",
    tags=["Risk Analyses"],
)
async def get_risk_analysis(
    transaction_external_id: str, db: AsyncSession = Depends(get_db)
):
    svc = BankService(db)
    return await svc.get_risk_analysis(transaction_external_id)
