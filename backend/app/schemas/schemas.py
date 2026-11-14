"""
Schemas Pydantic v2 — validação e serialização de todos os domínios.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.client import ClientRiskProfile
from app.models.contextual_event import EventType
from app.models.risk_analysis import RecommendedAction, RiskAnalysisStatus
from app.models.transaction import FundingSource, RiskLevel, TransactionStatus
from app.models.card import CardStatus, CreditLimitRequestStatus
from app.models.statement_entry import EntryType, EntryStatus


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────

class ClientResponse(BaseModel):
    id: int
    external_id: str
    name: str
    document_hint: str
    agency: str = "0001"
    account_number: str = "00000-0"
    account_type: str = "Conta Corrente"
    balance: Decimal
    reserved_balance: Decimal = Decimal("0.00")
    available_balance: Decimal = Decimal("0.00")
    transfer_limit: Decimal
    risk_profile: ClientRiskProfile
    account_age_days: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientSummary(BaseModel):
    """Versão compacta para listagens."""
    id: int
    external_id: str
    name: str
    risk_profile: ClientRiskProfile
    is_active: bool

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Beneficiary
# ─────────────────────────────────────────────────────────────────────────────

class BeneficiaryResponse(BaseModel):
    id: int
    external_id: str
    client_id: int
    name: str
    account_hint: str
    bank_name: str
    is_known: bool
    is_favorite: bool = False
    transfer_count: int
    total_transferred: Decimal
    risk_hint: float
    first_registered_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# ContextualEvent
# ─────────────────────────────────────────────────────────────────────────────

class ContextualEventResponse(BaseModel):
    id: int
    client_id: int
    transaction_id: int | None
    event_type: EventType
    metadata_json: str | None
    correlation_id: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# BehavioralHistory
# ─────────────────────────────────────────────────────────────────────────────

class BehavioralHistoryResponse(BaseModel):
    id: int
    client_id: int
    avg_transfer_value: Decimal
    max_transfer_value: Decimal
    min_transfer_value: Decimal
    avg_monthly_transactions: int
    recurring_beneficiary_ids: str | None
    typical_hours: str | None
    typical_channels: str | None
    last_computed_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Transaction
# ─────────────────────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    client_external_id: str = Field(..., min_length=1, max_length=64)
    beneficiary_external_id: str = Field(..., min_length=1, max_length=64)
    amount: str = Field(..., description="Valor em BRL como string decimal (ex: '1200.00')")
    purpose: str | None = Field(default=None, max_length=1024)
    device_recognized: bool = True
    funding_source: FundingSource = FundingSource.DEBIT
    card_external_id: str | None = Field(default=None, max_length=64)
    idempotency_key: str | None = Field(
        default=None, max_length=128,
        description="Chave de idempotência opcional — evita duplicação por reenvio."
    )

    @field_validator("amount")
    @classmethod
    def validate_amount_format(cls, v: str) -> str:
        try:
            val = Decimal(v)
            if val <= 0:
                raise ValueError("O valor deve ser positivo.")
        except Exception as exc:
            raise ValueError(f"Formato inválido para amount: '{v}'") from exc
        return v


class TransactionResponse(BaseModel):
    id: int
    external_id: str
    client_id: int
    beneficiary_id: int
    amount: Decimal
    currency: str
    purpose: str | None
    funding_source: FundingSource = FundingSource.DEBIT
    card_id: int | None = None
    is_new_recipient: bool
    recent_limit_change: bool
    device_recognized: bool
    risk_level: RiskLevel
    risk_score: float
    status: TransactionStatus
    decision_reasoning: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionWithParties(TransactionResponse):
    """Transação com dados embutidos de cliente e beneficiário."""
    client_name: str | None = None
    beneficiary_name: str | None = None

    @classmethod
    def from_orm_with_parties(cls, txn) -> "TransactionWithParties":
        data = TransactionWithParties.model_validate(txn)
        if txn.client:
            data.client_name = txn.client.name
        if txn.beneficiary:
            data.beneficiary_name = txn.beneficiary.name
        return data


# ─────────────────────────────────────────────────────────────────────────────
# RiskAnalysis
# ─────────────────────────────────────────────────────────────────────────────

class RiskAnalysisResponse(BaseModel):
    id: int
    external_id: str
    transaction_id: int
    overall_risk_score: float
    risk_level: str
    recommended_action: RecommendedAction
    reasoning: str | None
    flags: str | None
    status: RiskAnalysisStatus
    orchestrator_result: str | None
    fraud_agent_result: str | None
    inconsistency_agent_result: str | None
    behavioral_agent_result: str | None
    intention_agent_result: str | None = None
    risk_agent_result: str | None
    # Etapa 6
    divergence_detected: bool = False
    divergence_details: str | None = None
    policy_version: str | None = None
    confirmation_purpose: str | None = None
    phase: str = "initial"
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# AgentResult schema (espelho do dataclass app.agents.base.AgentResult)
# ─────────────────────────────────────────────────────────────────────────────

class AgentResult(BaseModel):
    agent_name: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)
    reasoning: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AnalysisResponse(BaseModel):
    transaction_id: str
    overall_risk_score: float
    risk_level: RiskLevel
    status: TransactionStatus
    agent_results: list[AgentResult]
    decision_reasoning: str


# ─────────────────────────────────────────────────────────────────────────────
# AuditLog
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: int
    transaction_id: int | None
    component: str
    agent_name: str
    action: str
    event: str | None
    result: str | None
    input_summary: str | None
    output_summary: str | None
    reasoning: str | None
    risk_score: float | None
    flags: str | None
    correlation_id: str | None
    # Etapa 6
    policy_version: str | None = None
    execution_time_ms: int | None = None
    agent_contributions: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Gateway response
# ─────────────────────────────────────────────────────────────────────────────

class GatewayResponseSchema(BaseModel):
    authorized: bool
    final_status: str
    final_action: str
    risk_level: str
    risk_score: float
    requires_confirmation: bool
    requires_human_review: bool
    gateway_reasoning: str
    flags: list[str]
    # Etapa 6
    policy_version: str | None = None
    divergence_detected: bool = False
    unauthorized_action_attempted: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Transfer initiation response
# ─────────────────────────────────────────────────────────────────────────────

class TransferInitiatedResponse(BaseModel):
    transaction: TransactionResponse
    analysis: RiskAnalysisResponse
    gateway: GatewayResponseSchema | None = None
    message: str
    idempotent: bool = False  # True = resultado de reenvio idempotente
    pipeline_failed: bool = False  # True = pipeline falhou (timeout/erro crítico)
    failure_reason: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Confirmação contextual (Fase 2)
# ─────────────────────────────────────────────────────────────────────────────

class ConfirmTransferRequest(BaseModel):
    confirmation_purpose: str = Field(
        ..., min_length=1, max_length=2048,
        description=(
            "Finalidade declarada pelo cliente na fase de confirmação. "
            "Tratada como dado a analisar — não como verdade automática."
        ),
    )


class ConfirmTransferResponse(BaseModel):
    transaction: TransactionResponse
    analysis: RiskAnalysisResponse
    new_status: str
    reasoning: str
    coercion_detected: bool
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Revisão humana
# ─────────────────────────────────────────────────────────────────────────────

class HumanReviewRequest(BaseModel):
    reviewer_id: str = Field(
        ..., min_length=1, max_length=64,
        description="Identificador do operador humano. A IA não pode usar este campo.",
    )
    reviewer_notes: str | None = Field(
        default=None, max_length=2048,
        description="Notas do revisor humano sobre a decisão.",
    )


class HumanReviewResponse(BaseModel):
    transaction: TransactionResponse
    new_status: str
    action: str
    reviewer_id: str
    reasoning: str
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Seed / Reset
# ─────────────────────────────────────────────────────────────────────────────

class SeedResponse(BaseModel):
    message: str
    summary: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Health Check (preservado da Etapa 1)
# ─────────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    llm_provider: str


# ─────────────────────────────────────────────────────────────────────────────
# StatementEntry
# ─────────────────────────────────────────────────────────────────────────────

class StatementEntryResponse(BaseModel):
    id: int
    client_id: int
    transaction_id: int | None
    entry_type: EntryType
    amount: Decimal
    currency: str
    description: str
    counterpart_name: str | None
    counterpart_bank: str | None
    status: EntryStatus
    balance_after: Decimal
    posted_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Limit Management
# ─────────────────────────────────────────────────────────────────────────────

class LimitInfoResponse(BaseModel):
    client_external_id: str
    transfer_limit: Decimal
    used_today: Decimal
    available_limit: Decimal
    balance: Decimal
    reserved_balance: Decimal
    available_balance: Decimal


class LimitChangeRequest(BaseModel):
    requested_limit: str = Field(
        ..., description="Novo limite em BRL como string decimal (ex: '10000.00')"
    )
    reason: str | None = Field(default=None, max_length=512)

    @field_validator("requested_limit")
    @classmethod
    def validate_limit_format(cls, v: str) -> str:
        try:
            val = Decimal(v)
            if val <= 0:
                raise ValueError("O limite deve ser positivo.")
        except Exception as exc:
            raise ValueError(f"Formato inválido para limit: '{v}'") from exc
        return v


class LimitChangeResponse(BaseModel):
    previous_limit: Decimal
    requested_limit: Decimal
    approved_limit: Decimal | None
    status: str
    approved: bool
    client_external_id: str
    event_correlation_id: str
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Credit card and human limit review
# ─────────────────────────────────────────────────────────────────────────────

class CreditCardResponse(BaseModel):
    id: int
    external_id: str
    client_id: int
    nickname: str
    masked_number: str
    brand: str
    color_start: str
    color_end: str
    credit_limit: Decimal
    used_credit: Decimal
    reserved_credit: Decimal
    available_credit: Decimal
    due_day: int
    closing_day: int
    status: CardStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditLimitRequestCreate(BaseModel):
    requested_limit: str
    reason: str | None = Field(default=None, max_length=1024)

    @field_validator("requested_limit")
    @classmethod
    def validate_requested_credit_limit(cls, value: str) -> str:
        try:
            if Decimal(value) <= 0:
                raise ValueError("O valor deve ser positivo.")
        except Exception as exc:
            raise ValueError("Informe um limite válido.") from exc
        return value


class CreditLimitReviewRequest(BaseModel):
    reviewer_id: str = Field(..., min_length=1, max_length=64)
    reviewer_notes: str | None = Field(default=None, max_length=2048)


class CreditLimitRequestResponse(BaseModel):
    id: int
    external_id: str
    client_id: int
    card_id: int
    current_limit: Decimal
    requested_limit: Decimal
    reason: str | None
    status: CreditLimitRequestStatus
    risk_score: float
    risk_level: str
    agent_assessment: str
    reviewer_id: str | None
    reviewer_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime
    card: CreditCardResponse | None = None
    client_name: str | None = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Beneficiary creation
# ─────────────────────────────────────────────────────────────────────────────

class BeneficiaryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    account_hint: str = Field(..., min_length=1, max_length=128)
    bank_name: str = Field(default="Banco Fictício", max_length=128)


class BeneficiaryFavoriteUpdate(BaseModel):
    is_favorite: bool
