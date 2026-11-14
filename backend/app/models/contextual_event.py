"""
Modelo ContextualEvent — eventos que antecedem ou cercam uma transação.
Esses eventos formam a "história da operação" analisada pelos agentes.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventType(str, enum.Enum):
    LOGIN = "LOGIN"
    ALTERACAO_LIMITE = "ALTERACAO_LIMITE"
    CADASTRO_BENEFICIARIO = "CADASTRO_BENEFICIARIO"
    INICIO_TRANSFERENCIA = "INICIO_TRANSFERENCIA"
    CONFIRMACAO_CONTEXTUAL = "CONFIRMACAO_CONTEXTUAL"
    RESPOSTA_CLIENTE = "RESPOSTA_CLIENTE"
    REVISAO_HUMANA = "REVISAO_HUMANA"  # Revisão por operador humano (Etapa 6)
    SOLICITACAO_AUMENTO_LIMITE_CREDITO = "SOLICITACAO_AUMENTO_LIMITE_CREDITO"
    AUMENTO_LIMITE_CREDITO_APROVADO = "AUMENTO_LIMITE_CREDITO_APROVADO"
    AUMENTO_LIMITE_CREDITO_REJEITADO = "AUMENTO_LIMITE_CREDITO_REJEITADO"
    INICIO_PIX_CREDITO = "INICIO_PIX_CREDITO"


class ContextualEvent(Base):
    """
    Evento contextual associado a um cliente.
    A sequência de eventos revela o contexto de risco da operação.
    """

    __tablename__ = "contextual_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id"), index=True
    )
    # Transação associada (opcional — nem todo evento precede uma transação)
    transaction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transactions.id"), nullable=True, index=True
    )

    event_type: Mapped[EventType] = mapped_column(Enum(EventType), index=True)

    # Metadados livres do evento em JSON
    # Ex: {"valor_novo": 25000, "valor_anterior": 5000} para ALTERACAO_LIMITE
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Identificador de correlação — agrupa eventos de uma mesma sessão
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relacionamentos
    client: Mapped["Client"] = relationship(  # noqa: F821
        "Client", back_populates="contextual_events"
    )
    transaction: Mapped["Transaction | None"] = relationship(  # noqa: F821
        "Transaction", back_populates="contextual_events"
    )

    def __repr__(self) -> str:
        return f"<ContextualEvent {self.event_type} client_id={self.client_id}>"
