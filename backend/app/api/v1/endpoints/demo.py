"""
Endpoint de reset/seed — reinicializa os cenários de demonstração.
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import SeedResponse
from app.services.seed_service import seed_database

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/reset",
    response_model=SeedResponse,
    summary="Reinicializar cenários de demonstração",
    description=(
        "Apaga todos os dados existentes e recria os três cenários de demonstração "
        "(A: operação normal, B: operação incomum, C: possível engenharia social). "
        "⚠️ Esta operação é destrutiva — todos os dados serão perdidos."
    ),
    tags=["Demo"],
)
async def reset_demo(db: AsyncSession = Depends(get_db)) -> dict:
    logger.warning("Demo reset requested — all data will be cleared")
    summary = await seed_database(db)
    return SeedResponse(
        message="Cenários de demonstração reinicializados com sucesso.",
        summary=summary,
    )


@router.get(
    "/status",
    summary="Status dos dados de demonstração",
    tags=["Demo"],
)
async def demo_status(db: AsyncSession = Depends(get_db)) -> dict:
    from sqlalchemy import select, func
    from app.models.client import Client
    from app.models.transaction import Transaction
    from app.models.risk_analysis import RiskAnalysis

    client_count = (await db.execute(select(func.count()).select_from(Client))).scalar_one()
    txn_count = (await db.execute(select(func.count()).select_from(Transaction))).scalar_one()
    analysis_count = (await db.execute(select(func.count()).select_from(RiskAnalysis))).scalar_one()

    return {
        "seeded": client_count > 0,
        "clients": client_count,
        "transactions": txn_count,
        "risk_analyses": analysis_count,
        "hint": "POST /api/v1/demo/reset para reinicializar os dados.",
    }
