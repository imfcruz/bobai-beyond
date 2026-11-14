"""
Endpoints de Beneficiários.
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import BeneficiaryFavoriteUpdate, BeneficiaryResponse
from app.services.bank_service import BankService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/client/{client_external_id}",
    response_model=list[BeneficiaryResponse],
    summary="Listar beneficiários de um cliente",
    tags=["Beneficiaries"],
)
async def list_beneficiaries(
    client_external_id: str, db: AsyncSession = Depends(get_db)
) -> list:
    svc = BankService(db)
    return await svc.list_beneficiaries(client_external_id)


@router.patch(
    "/{external_id}/favorite",
    response_model=BeneficiaryResponse,
    summary="Favoritar ou desfavoritar contato",
    tags=["Beneficiaries"],
)
async def set_favorite(
    external_id: str,
    payload: BeneficiaryFavoriteUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await BankService(db).set_beneficiary_favorite(
        external_id, payload.is_favorite
    )


@router.get(
    "/{external_id}",
    response_model=BeneficiaryResponse,
    summary="Consultar beneficiário",
    tags=["Beneficiaries"],
)
async def get_beneficiary(external_id: str, db: AsyncSession = Depends(get_db)):
    svc = BankService(db)
    return await svc.get_beneficiary(external_id)
