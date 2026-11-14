"""
Endpoints de Eventos Contextuais.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import ContextualEventResponse
from app.services.bank_service import BankService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/client/{client_external_id}",
    response_model=list[ContextualEventResponse],
    summary="Eventos contextuais de um cliente",
    tags=["Events"],
)
async def get_client_events(
    client_external_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list:
    svc = BankService(db)
    return await svc.get_client_events(client_external_id, limit)


@router.get(
    "/transaction/{transaction_external_id}",
    response_model=list[ContextualEventResponse],
    summary="Eventos de uma transação específica",
    tags=["Events"],
)
async def get_transaction_events(
    transaction_external_id: str, db: AsyncSession = Depends(get_db)
) -> list:
    svc = BankService(db)
    return await svc.get_transaction_events(transaction_external_id)
