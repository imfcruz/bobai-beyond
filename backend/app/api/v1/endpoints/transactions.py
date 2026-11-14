"""
Endpoints de Transações — iniciar, consultar, confirmar e revisar.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import (
    ConfirmTransferRequest,
    ConfirmTransferResponse,
    GatewayResponseSchema,
    HumanReviewRequest,
    HumanReviewResponse,
    RiskAnalysisResponse,
    TransactionCreate,
    TransactionResponse,
    TransactionWithParties,
    TransferInitiatedResponse,
)
from app.services.bank_service import BankService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=list[TransactionWithParties],
    summary="Listar todas as transações",
    tags=["Transactions"],
)
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list:
    from app.repositories.transaction_repo import TransactionRepository
    repo = TransactionRepository(db)
    txns = await repo.list_all(limit, offset)
    return [TransactionWithParties.from_orm_with_parties(t) for t in txns]


@router.post(
    "/",
    response_model=TransferInitiatedResponse,
    status_code=201,
    summary="Iniciar transferência simulada (pipeline multiagente)",
    description=(
        "Inicia uma transferência simulada via pipeline multiagente. "
        "Nenhum dinheiro real é movimentado. "
        "Executa: Orquestrador → Fraude + Inconsistência + Comportamental (paralelo) "
        "→ Agente de Risco → Decision Engine → Security Gateway. "
        "Suporta idempotency_key para evitar duplicação por reenvio."
    ),
    tags=["Transactions"],
)
async def initiate_transfer(
    payload: TransactionCreate, db: AsyncSession = Depends(get_db)
) -> dict:
    svc = BankService(db)
    result = await svc.initiate_transfer(
        client_external_id=payload.client_external_id,
        beneficiary_external_id=payload.beneficiary_external_id,
        amount_str=payload.amount,
        purpose=payload.purpose,
        device_recognized=payload.device_recognized,
        idempotency_key=payload.idempotency_key,
        funding_source=payload.funding_source,
        card_external_id=payload.card_external_id,
    )
    txn = result["transaction"]
    analysis = result["analysis"]
    gateway_dict = result.get("gateway")
    idempotent = result.get("idempotent", False)
    pipeline_failed = result.get("pipeline_failed", False)
    failure_reason = result.get("failure_reason")

    status_messages = {
        "released": "✅ Transferência liberada automaticamente.",
        "awaiting_confirmation": "⚠️ Confirmação contextual necessária.",
        "under_verification": "⚠️ Transferência requer verificação adicional.",
        "human_review_pending": "🔴 Transferência encaminhada para revisão humana.",
        "escalated_to_human": "🔴 Transferência escalada para análise humana.",
        "rejected": "❌ Transferência rejeitada pela política de segurança.",
        "pending": "⏳ Transferência em análise.",
    }

    if idempotent:
        msg = "♻️ Resultado idempotente — esta solicitação já foi processada."
    elif pipeline_failed:
        msg = f"⚠️ {failure_reason or 'Pipeline falhou — transação mantida como PENDING.'}"
    else:
        msg = status_messages.get(txn.status.value if hasattr(txn.status, "value") else txn.status, "Status atualizado.")

    gateway_schema = GatewayResponseSchema(**gateway_dict) if gateway_dict else None

    return TransferInitiatedResponse(
        transaction=TransactionResponse.model_validate(txn),
        analysis=RiskAnalysisResponse.model_validate(analysis),
        gateway=gateway_schema,
        message=msg,
        idempotent=idempotent,
        pipeline_failed=pipeline_failed,
        failure_reason=failure_reason,
    )


@router.post(
    "/{external_id}/confirm",
    response_model=ConfirmTransferResponse,
    status_code=200,
    summary="Confirmar transferência (Fase 2 — confirmação contextual)",
    description=(
        "Fase 2 do fluxo de confirmação contextual. "
        "O cliente fornece a finalidade da transferência. "
        "A resposta NÃO é aceita automaticamente — o sistema reavalia o contexto. "
        "Apenas transações com status 'awaiting_confirmation' podem ser confirmadas."
    ),
    tags=["Transactions"],
)
async def confirm_transfer(
    external_id: str,
    payload: ConfirmTransferRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = BankService(db)
    result = await svc.confirm_transfer(
        transaction_external_id=external_id,
        confirmation_purpose=payload.confirmation_purpose,
    )
    txn = result["transaction"]
    analysis = result["analysis"]
    new_status = result["new_status"]
    reasoning = result["reasoning"]
    coercion_detected = result["coercion_detected"]

    status_messages = {
        "released": "✅ Confirmação aceita — operação liberada.",
        "human_review_pending": "🔴 Confirmação registrada — encaminhado para revisão humana.",
        "rejected": "❌ Operação rejeitada após confirmação.",
    }
    msg = status_messages.get(new_status, f"Status atualizado: {new_status}.")
    if coercion_detected:
        msg = "⚠️ " + msg + " Possível indicador de coerção detectado."

    return ConfirmTransferResponse(
        transaction=TransactionResponse.model_validate(txn),
        analysis=RiskAnalysisResponse.model_validate(analysis),
        new_status=new_status,
        reasoning=reasoning,
        coercion_detected=coercion_detected,
        message=msg,
    )


@router.post(
    "/{external_id}/human-review/{action}",
    response_model=HumanReviewResponse,
    status_code=200,
    summary="Revisão humana — aprovar ou rejeitar",
    description=(
        "Ação explícita de revisão humana. "
        "Apenas transações com status 'human_review_pending' ou 'escalated_to_human' "
        "podem ser revisadas. "
        "A IA NÃO pode executar esta ação. "
        "reviewer_id deve ser um identificador humano real (não 'ai', 'bot', 'auto', etc.)."
    ),
    tags=["Transactions"],
)
async def human_review(
    external_id: str,
    action: str,
    payload: HumanReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if action not in ("approve", "reject"):
        from app.core.errors import ValidationError
        raise ValidationError("action deve ser 'approve' ou 'reject'.")

    svc = BankService(db)
    result = await svc.human_review(
        transaction_external_id=external_id,
        action=action,
        reviewer_id=payload.reviewer_id,
        reviewer_notes=payload.reviewer_notes,
    )
    txn = result["transaction"]
    new_status = result["new_status"]

    action_messages = {
        "approve": "✅ Transação aprovada pelo revisor humano.",
        "reject": "❌ Transação rejeitada pelo revisor humano.",
    }
    msg = action_messages.get(action, f"Revisão concluída: {action}.")

    return HumanReviewResponse(
        transaction=TransactionResponse.model_validate(txn),
        new_status=new_status,
        action=action,
        reviewer_id=result["reviewer_id"],
        reasoning=result["reasoning"],
        message=msg,
    )


@router.get(
    "/{external_id}",
    response_model=TransactionWithParties,
    summary="Consultar status de transferência",
    tags=["Transactions"],
)
async def get_transaction(external_id: str, db: AsyncSession = Depends(get_db)):
    svc = BankService(db)
    txn = await svc.get_transaction(external_id)
    return TransactionWithParties.from_orm_with_parties(txn)


@router.get(
    "/client/{client_external_id}",
    response_model=list[TransactionWithParties],
    summary="Histórico transacional de um cliente",
    tags=["Transactions"],
)
async def get_client_history(
    client_external_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list:
    svc = BankService(db)
    txns = await svc.get_client_transaction_history(client_external_id, limit)
    return [TransactionWithParties.from_orm_with_parties(t) for t in txns]
