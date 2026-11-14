"""
Modelo StatementEntry — lançamento no extrato bancário simulado.

Cada movimentação financeira efetivada gera um lançamento nesta tabela.
Dados 100% sintéticos — nenhum dinheiro real é movimentado.
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EntryType(str, enum.Enum):
    DEBIT = "debit"       # Saída da conta do cliente (transferência enviada)
    CREDIT = "credit"     # Entrada na conta do cliente (transferência recebida)
    RESERVE = "reserve"   # Reserva temporária de saldo (transação pendente)
    RELEASE = "release"   # Liberação de reserva (transação cancelada/rejeitada)


class EntryStatus(str, enum.Enum):
    POSTED = "posted"       # Efetivado — debita/credita o saldo contábil
    PENDING = "pending"     # Reserva — ainda não efetivado
    REVERSED = "reversed"   # Estornado


class StatementEntry(Base):
    """
    Lançamento no extrato bancário simulado.
    Um lançamento é criado para cada movimentação financeira real.
    """

    __tablename__ = "statement_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Referência ao cliente
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id"), index=True
    )

    # Transação que originou o lançamento (pode ser NULL para créditos manuais demo)
    transaction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transactions.id"), nullable=True, index=True
    )

    # Tipo e valor
    entry_type: Mapped[EntryType] = mapped_column(Enum(EntryType), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")

    # Descrição legível para o extrato
    description: Mapped[str] = mapped_column(String(512))

    # Contraparte (nome do beneficiário ou origem)
    counterpart_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    counterpart_bank: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Status e saldo resultante (snapshot do saldo após o lançamento)
    status: Mapped[EntryStatus] = mapped_column(
        Enum(EntryStatus), default=EntryStatus.POSTED, index=True
    )
    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0.00")
    )

    # Metadados adicionais (JSON)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relacionamentos
    client: Mapped["Client"] = relationship(  # noqa: F821
        "Client", back_populates="statement_entries"
    )
    transaction: Mapped["Transaction | None"] = relationship(  # noqa: F821
        "Transaction", back_populates="statement_entries", foreign_keys=[transaction_id]
    )

    def __repr__(self) -> str:
        return f"<StatementEntry {self.entry_type} amount={self.amount} client={self.client_id}>"
