"""
Modelo de Transação — operação financeira simulada com FK para Client/Beneficiary.
Não movimenta dinheiro real — dados 100% sintéticos.
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FundingSource(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"                              # Iniciada, aguardando análise
    RELEASED = "released"                            # Liberada automaticamente (baixo risco)
    UNDER_VERIFICATION = "under_verification"        # Em verificação adicional
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Fase 2: aguardando confirmação do cliente
    ESCALATED_TO_HUMAN = "escalated_to_human"        # Encaminhada para atendente
    HUMAN_REVIEW_PENDING = "human_review_pending"    # Em fila de revisão humana
    HUMAN_APPROVED = "human_approved"                # Aprovada por revisor humano
    HUMAN_REJECTED = "human_rejected"                # Rejeitada por revisor humano
    REJECTED = "rejected"                            # Rejeitada pela política de segurança
    # Mantido para compatibilidade com Etapa 1 (schema legado)
    APPROVED = "approved"
    REQUIRES_VERIFICATION = "requires_verification"
    BLOCKED = "blocked"


# Transições válidas de estado — impede mudanças incoerentes
# A LLM não pode alterar estes limiares nem contornar transições bloqueadas.
VALID_TRANSITIONS: dict[TransactionStatus, set[TransactionStatus]] = {
    TransactionStatus.PENDING: {
        TransactionStatus.RELEASED,
        TransactionStatus.UNDER_VERIFICATION,
        TransactionStatus.AWAITING_CONFIRMATION,
        TransactionStatus.ESCALATED_TO_HUMAN,
        TransactionStatus.HUMAN_REVIEW_PENDING,
        TransactionStatus.REJECTED,
        # Legado
        TransactionStatus.APPROVED,
        TransactionStatus.REQUIRES_VERIFICATION,
        TransactionStatus.BLOCKED,
    },
    TransactionStatus.UNDER_VERIFICATION: {
        TransactionStatus.RELEASED,
        TransactionStatus.AWAITING_CONFIRMATION,
        TransactionStatus.ESCALATED_TO_HUMAN,
        TransactionStatus.HUMAN_REVIEW_PENDING,
        TransactionStatus.REJECTED,
        TransactionStatus.APPROVED,
        TransactionStatus.BLOCKED,
    },
    TransactionStatus.AWAITING_CONFIRMATION: {
        TransactionStatus.RELEASED,
        TransactionStatus.UNDER_VERIFICATION,
        TransactionStatus.ESCALATED_TO_HUMAN,
        TransactionStatus.HUMAN_REVIEW_PENDING,
        TransactionStatus.REJECTED,
    },
    TransactionStatus.REQUIRES_VERIFICATION: {
        TransactionStatus.RELEASED,
        TransactionStatus.ESCALATED_TO_HUMAN,
        TransactionStatus.REJECTED,
        TransactionStatus.APPROVED,
        TransactionStatus.BLOCKED,
    },
    TransactionStatus.ESCALATED_TO_HUMAN: {
        TransactionStatus.HUMAN_REVIEW_PENDING,
        TransactionStatus.RELEASED,
        TransactionStatus.REJECTED,
        TransactionStatus.APPROVED,
    },
    TransactionStatus.HUMAN_REVIEW_PENDING: {
        TransactionStatus.HUMAN_APPROVED,
        TransactionStatus.HUMAN_REJECTED,
        TransactionStatus.RELEASED,
        TransactionStatus.REJECTED,
    },
    # Estados terminais — sem saída
    TransactionStatus.RELEASED: set(),
    TransactionStatus.APPROVED: set(),
    TransactionStatus.REJECTED: set(),
    TransactionStatus.BLOCKED: set(),
    TransactionStatus.HUMAN_APPROVED: set(),
    TransactionStatus.HUMAN_REJECTED: set(),
}


def is_valid_transition(current: TransactionStatus, next_status: TransactionStatus) -> bool:
    return next_status in VALID_TRANSITIONS.get(current, set())


def is_terminal_status(status: TransactionStatus) -> bool:
    """Retorna True se o status é terminal (sem transições válidas)."""
    return not VALID_TRANSITIONS.get(status)


class Transaction(Base):
    """
    Representa uma operação financeira simulada.
    Não movimenta dinheiro real — dados 100% sintéticos.
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Chave de idempotência — impede duplicação por reenvio
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )

    # FK para entidades do domínio
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id"), index=True
    )
    beneficiary_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("beneficiaries.id"), index=True
    )
    card_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("credit_cards.id"), nullable=True, index=True
    )

    # Valor simulado com precisão Decimal
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    funding_source: Mapped[FundingSource] = mapped_column(
        Enum(FundingSource), default=FundingSource.DEBIT
    )

    # Contexto da operação (snapshot no momento da criação)
    is_new_recipient: Mapped[bool] = mapped_column(default=False)
    recent_limit_change: Mapped[bool] = mapped_column(default=False)
    device_recognized: Mapped[bool] = mapped_column(default=True)

    # Resultado da análise de risco
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel), default=RiskLevel.LOW
    )
    risk_score: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), default=TransactionStatus.PENDING
    )

    # Resultado dos agentes e justificativa (preenchidos pela análise)
    agent_results: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relacionamentos
    client: Mapped["Client"] = relationship(  # noqa: F821
        "Client", back_populates="transactions"
    )
    beneficiary: Mapped["Beneficiary"] = relationship(  # noqa: F821
        "Beneficiary", back_populates="transactions"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        "AuditLog", back_populates="transaction", cascade="all, delete-orphan",
        foreign_keys="AuditLog.transaction_id",
    )
    contextual_events: Mapped[list["ContextualEvent"]] = relationship(  # noqa: F821
        "ContextualEvent", back_populates="transaction"
    )
    risk_analysis: Mapped["RiskAnalysis | None"] = relationship(  # noqa: F821
        "RiskAnalysis",
        back_populates="transaction",
        primaryjoin="Transaction.id == foreign(RiskAnalysis.transaction_id)",
        uselist=False,
        viewonly=True,
    )
    statement_entries: Mapped[list["StatementEntry"]] = relationship(  # noqa: F821
        "StatementEntry", back_populates="transaction",
        foreign_keys="StatementEntry.transaction_id",
    )
    card: Mapped["CreditCard | None"] = relationship(  # noqa: F821
        "CreditCard", back_populates="transactions"
    )
    # Flag de idempotência de liquidação — impede que a mesma transferência seja debitada duas vezes
    settlement_applied: Mapped[bool] = mapped_column(default=False)
    credit_reservation_applied: Mapped[bool] = mapped_column(default=False)

    def __repr__(self) -> str:
        return f"<Transaction {self.external_id} amount={self.amount} status={self.status}>"
