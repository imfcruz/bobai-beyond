"""
Modelo BehavioralHistory — histórico comportamental sintético de um cliente.
Usado pelos agentes para detectar desvios de padrão.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BehavioralHistory(Base):
    """
    Resumo do comportamento transacional histórico de um cliente.
    Calculado sobre dados sintéticos — usado como baseline para análise de desvios.
    """

    __tablename__ = "behavioral_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id"), unique=True, index=True
    )

    # Valores de referência (calculados sobre histórico sintético)
    avg_transfer_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0.00")
    )
    max_transfer_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0.00")
    )
    min_transfer_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0.00")
    )

    # Frequência — transações por mês (média)
    avg_monthly_transactions: Mapped[int] = mapped_column(Integer, default=0)

    # Beneficiários recorrentes (JSON: lista de external_ids)
    recurring_beneficiary_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Horários habituais (JSON: lista de faixas, ex: ["09:00-12:00", "14:00-18:00"])
    typical_hours: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Canais habituais (ex: "mobile", "web")
    typical_channels: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Última atualização do histórico
    last_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relacionamento
    client: Mapped["Client"] = relationship(  # noqa: F821
        "Client", back_populates="behavioral_history"
    )

    def __repr__(self) -> str:
        return f"<BehavioralHistory client_id={self.client_id} avg={self.avg_transfer_value}>"
