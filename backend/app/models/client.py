"""
Modelo Client — cliente sintético para simulação.
Nenhum dado pessoal real.
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ClientRiskProfile(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Client(Base):
    """
    Cliente fictício para fins de simulação acadêmica.
    Saldo e dados são sintéticos — nenhuma operação real.
    """

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    document_hint: Mapped[str] = mapped_column(String(32))  # ex: "***.***.***-00" — fictício

    # Dados bancários fictícios para demonstração
    agency: Mapped[str] = mapped_column(String(16), default="0001")
    account_number: Mapped[str] = mapped_column(String(20), default="00000-0")
    account_type: Mapped[str] = mapped_column(String(32), default="Conta Corrente")

    # Saldo simulado com precisão monetária (Decimal — nunca float)
    balance: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2), default=Decimal("0.00"))
    # Saldo reservado — valor bloqueado por transações pendentes (não disponível)
    reserved_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0.00")
    )
    transfer_limit: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2), default=Decimal("5000.00"))

    # Perfil transacional
    risk_profile: Mapped[ClientRiskProfile] = mapped_column(
        Enum(ClientRiskProfile), default=ClientRiskProfile.LOW
    )
    account_age_days: Mapped[int] = mapped_column(Integer, default=365)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Metadados adicionais (JSON) — ex: preferências, canal de acesso habitual
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relacionamentos
    beneficiaries: Mapped[list["Beneficiary"]] = relationship(  # noqa: F821
        "Beneficiary", back_populates="client", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction", back_populates="client", cascade="all, delete-orphan"
    )
    contextual_events: Mapped[list["ContextualEvent"]] = relationship(  # noqa: F821
        "ContextualEvent", back_populates="client", cascade="all, delete-orphan"
    )
    behavioral_history: Mapped["BehavioralHistory | None"] = relationship(  # noqa: F821
        "BehavioralHistory", back_populates="client", uselist=False, cascade="all, delete-orphan"
    )
    statement_entries: Mapped[list["StatementEntry"]] = relationship(  # noqa: F821
        "StatementEntry", back_populates="client", cascade="all, delete-orphan"
    )
    credit_cards: Mapped[list["CreditCard"]] = relationship(  # noqa: F821
        "CreditCard", back_populates="client", cascade="all, delete-orphan"
    )
    credit_limit_requests: Mapped[list["CreditLimitRequest"]] = relationship(  # noqa: F821
        "CreditLimitRequest", back_populates="client", cascade="all, delete-orphan"
    )

    @property
    def available_balance(self) -> Decimal:
        """Saldo disponível = saldo total − valor reservado."""
        return self.balance - self.reserved_balance

    def __repr__(self) -> str:
        return f"<Client {self.external_id} name={self.name}>"
