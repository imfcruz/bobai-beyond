"""
Endpoints de Clientes — consulta, extrato e gestão de limites.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import (
    ClientResponse,
    ClientSummary,
    BehavioralHistoryResponse,
    StatementEntryResponse,
    LimitInfoResponse,
    LimitChangeRequest,
    LimitChangeResponse,
    BeneficiaryCreate,
    BeneficiaryResponse,
)
from app.services.bank_service import BankService
from app.core.errors import AppError

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=list[ClientSummary],
    summary="Listar clientes sintéticos",
    tags=["Clients"],
)
async def list_clients(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list:
    svc = BankService(db)
    return await svc.list_clients(limit, offset)


@router.get(
    "/{external_id}",
    response_model=ClientResponse,
    summary="Consultar cliente",
    tags=["Clients"],
)
async def get_client(external_id: str, db: AsyncSession = Depends(get_db)):
    svc = BankService(db)
    return await svc.get_client(external_id)


@router.get(
    "/{external_id}/behavioral-history",
    response_model=BehavioralHistoryResponse,
    summary="Histórico comportamental do cliente",
    tags=["Clients"],
)
async def get_behavioral_history(external_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.client import Client
    from app.models.behavioral_history import BehavioralHistory
    from fastapi import HTTPException

    result = await db.execute(
        select(Client)
        .where(Client.external_id == external_id)
        .options(selectinload(Client.behavioral_history))
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail=f"Cliente '{external_id}' não encontrado.")
    if client.behavioral_history is None:
        raise HTTPException(status_code=404, detail="Histórico comportamental não encontrado.")
    return client.behavioral_history


# ── Extrato bancário ──────────────────────────────────────────────────────────

@router.get(
    "/{external_id}/statement",
    response_model=list[StatementEntryResponse],
    summary="Extrato bancário do cliente",
    description=(
        "Retorna os lançamentos do extrato bancário simulado. "
        "Apenas transferências efetivadas (released/human_approved) aparecem como DEBIT. "
        "Operações pendentes ou rejeitadas não geram lançamentos definitivos."
    ),
    tags=["Clients", "Statement"],
)
async def get_statement(
    external_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    entry_type: str | None = Query(default=None, description="Filtrar por tipo: debit, credit, reserve, release"),
    status: str | None = Query(default=None, description="Filtrar por status: posted, pending, reversed"),
    db: AsyncSession = Depends(get_db),
) -> list:
    svc = BankService(db)
    entries = await svc.get_statement(
        client_external_id=external_id,
        limit=limit,
        offset=offset,
        entry_type=entry_type,
        status=status,
    )
    return [StatementEntryResponse.model_validate(e) for e in entries]


# ── Gestão de limites ─────────────────────────────────────────────────────────

@router.get(
    "/{external_id}/limits",
    response_model=LimitInfoResponse,
    summary="Consultar limites do cliente",
    tags=["Clients", "Limits"],
)
async def get_limit_info(external_id: str, db: AsyncSession = Depends(get_db)):
    svc = BankService(db)
    info = await svc.get_limit_info(external_id)
    return LimitInfoResponse(**info)


@router.post(
    "/{external_id}/limits",
    response_model=LimitChangeResponse,
    summary="Solicitar alteração de limite",
    description=(
        "Solicita alteração do limite de transferência. "
        "Aumentos até 2× o limite atual são aprovados automaticamente. "
        "Aumentos maiores ficam pendentes de revisão. "
        "Toda alteração gera um evento contextual ALTERACAO_LIMITE visível aos agentes."
    ),
    tags=["Clients", "Limits"],
)
async def request_limit_change(
    external_id: str,
    payload: LimitChangeRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = BankService(db)
    result = await svc.request_limit_change(
        client_external_id=external_id,
        requested_limit=payload.requested_limit,
        reason=payload.reason,
    )
    return LimitChangeResponse(**result)


# ── Beneficiários ─────────────────────────────────────────────────────────────

@router.post(
    "/{external_id}/beneficiaries",
    response_model=BeneficiaryResponse,
    status_code=201,
    summary="Cadastrar novo beneficiário",
    description=(
        "Cadastra um novo beneficiário para o cliente. "
        "Gera evento contextual CADASTRO_BENEFICIARIO visível aos agentes de segurança."
    ),
    tags=["Clients", "Beneficiaries"],
)
async def add_beneficiary(
    external_id: str,
    payload: BeneficiaryCreate,
    db: AsyncSession = Depends(get_db),
):
    svc = BankService(db)
    ben = await svc.add_beneficiary(
        client_external_id=external_id,
        name=payload.name,
        account_hint=payload.account_hint,
        bank_name=payload.bank_name,
    )
    return BeneficiaryResponse.model_validate(ben)
