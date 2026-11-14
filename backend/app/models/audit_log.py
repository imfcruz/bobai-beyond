"""
Modelo de Log de Auditoria — rastreia todas as ações dos agentes e do sistema.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AuditLog(Base):
    """
    Registra cada ação dos agentes e do Security Gateway.
    Permite rastreabilidade completa de decisões e mudanças de estado.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transaction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transactions.id"), nullable=True, index=True
    )

    # Componente responsável pelo registro (ex: "fraud_agent", "security_gateway")
    component: Mapped[str] = mapped_column(String(128), index=True)
    # Mantido para compatibilidade com Etapa 1
    agent_name: Mapped[str] = mapped_column(String(128), index=True)

    action: Mapped[str] = mapped_column(String(256))
    event: Mapped[str | None] = mapped_column(String(256), nullable=True)
    result: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Detalhes da análise
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resultado
    risk_score: Mapped[float | None] = mapped_column(nullable=True)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Identificador de correlação — agrupa registros de uma mesma operação
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Rastreabilidade da política e performance (Etapa 6)
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_contributions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relacionamento
    transaction: Mapped["Transaction"] = relationship(  # noqa: F821
        "Transaction",
        back_populates="audit_logs",
        foreign_keys=[transaction_id],
    )

    def __repr__(self) -> str:
        return f"<AuditLog component={self.component} action={self.action}>"
