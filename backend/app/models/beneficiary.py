"""
Modelo Beneficiary — destinatário de transferência simulada.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Beneficiary(Base):
    """
    Destinatário fictício de operações de transferência.
    Todos os identificadores são sintéticos.
    """

    __tablename__ = "beneficiaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id"), index=True
    )

    name: Mapped[str] = mapped_column(String(256))
    # Chave Pix ou agência/conta sintética — nunca real
    account_hint: Mapped[str] = mapped_column(String(128))
    bank_name: Mapped[str] = mapped_column(String(128), default="Banco Fictício")

    # Indicador de beneficiário conhecido ou novo
    is_known: Mapped[bool] = mapped_column(Boolean, default=False)
    # Contato marcado pelo cliente para acesso rápido.
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    # Quantas vezes esse cliente já transferiu para este beneficiário
    transfer_count: Mapped[int] = mapped_column(Integer, default=0)
    # Valor total transferido (sintético, Decimal)
    total_transferred: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0.00")
    )

    # Data do primeiro cadastro deste beneficiário pelo cliente
    first_registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Nota de risco do beneficiário (0.0 = baixo, 1.0 = alto)
    risk_hint: Mapped[float] = mapped_column(default=0.05)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relacionamentos
    client: Mapped["Client"] = relationship(  # noqa: F821
        "Client", back_populates="beneficiaries"
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction", back_populates="beneficiary"
    )

    def __repr__(self) -> str:
        return f"<Beneficiary {self.external_id} name={self.name} known={self.is_known}>"
