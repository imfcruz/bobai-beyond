"""Cartões e solicitações de aumento de limite do simulador acadêmico."""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CardStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class CreditLimitRequestStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class CreditCard(Base):
    """Cartão de crédito sintético vinculado a um cliente da demonstração."""

    __tablename__ = "credit_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), index=True)
    nickname: Mapped[str] = mapped_column(String(80), default="Ourocard")
    masked_number: Mapped[str] = mapped_column(String(24))
    brand: Mapped[str] = mapped_column(String(32), default="Elo")
    color_start: Mapped[str] = mapped_column(String(16), default="#3333BD")
    color_end: Mapped[str] = mapped_column(String(16), default="#465EFF")
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"))
    used_credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"))
    reserved_credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"))
    due_day: Mapped[int] = mapped_column(Integer, default=10)
    closing_day: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[CardStatus] = mapped_column(Enum(CardStatus), default=CardStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship("Client", back_populates="credit_cards")  # noqa: F821
    limit_requests: Mapped[list["CreditLimitRequest"]] = relationship(
        "CreditLimitRequest", back_populates="card", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction", back_populates="card"
    )

    @property
    def available_credit(self) -> Decimal:
        return max(
            Decimal("0.00"),
            Decimal(str(self.credit_limit))
            - Decimal(str(self.used_credit))
            - Decimal(str(self.reserved_credit)),
        )


class CreditLimitRequest(Base):
    """Pedido de limite: análise automatizada informativa e decisão humana obrigatória."""

    __tablename__ = "credit_limit_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), index=True)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("credit_cards.id"), index=True)
    current_limit: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    requested_limit: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CreditLimitRequestStatus] = mapped_column(
        Enum(CreditLimitRequestStatus), default=CreditLimitRequestStatus.PENDING_REVIEW
    )
    risk_score: Mapped[float] = mapped_column(default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    agent_assessment: Mapped[str] = mapped_column(Text, default="{}")
    reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship("Client", back_populates="credit_limit_requests")  # noqa: F821
    card: Mapped["CreditCard"] = relationship("CreditCard", back_populates="limit_requests")
