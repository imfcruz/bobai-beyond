"""
Modelo RiskAnalysis — resultado consolidado da análise multiagente.
Armazena o resultado individual de cada agente (JSON) e o score final.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RiskAnalysisStatus(str, enum.Enum):
    PENDING = "pending"          # Análise ainda não iniciada
    IN_PROGRESS = "in_progress"  # Agentes em execução
    COMPLETED = "completed"      # Análise concluída
    FAILED = "failed"            # Erro durante a análise


class RecommendedAction(str, enum.Enum):
    APPROVE = "approve"                      # Liberar automaticamente
    REQUEST_CONFIRMATION = "request_confirmation"  # Pedir confirmação contextual ao cliente
    ESCALATE_TO_HUMAN = "escalate_to_human"  # Encaminhar para atendente humano
    BLOCK = "block"                          # Bloquear a operação


class RiskAnalysis(Base):
    """
    Resultado consolidado da análise de risco para uma transação.
    Cada campo de agente será preenchido pela implementação correspondente.
    """

    __tablename__ = "risk_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transactions.id"), unique=True, index=True
    )

    # ── Resultados individuais por agente (JSON) ───────────────────────────────
    orchestrator_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    fraud_agent_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    inconsistency_agent_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavioral_agent_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    intention_agent_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_agent_result: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Resultado consolidado ──────────────────────────────────────────────────
    overall_risk_score: Mapped[float] = mapped_column(default=0.0)
    risk_level: Mapped[str] = mapped_column(
        String(16), default="low"  # low | medium | high | critical
    )
    recommended_action: Mapped[RecommendedAction] = mapped_column(
        Enum(RecommendedAction), default=RecommendedAction.APPROVE
    )

    # Justificativa em linguagem natural
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Flags identificadas pelos agentes (JSON: lista de strings)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Divergência e política (Etapa 6) ─────────────────────────────────────
    divergence_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    divergence_details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ── Confirmação contextual (Fase 2) ───────────────────────────────────────
    # Armazena a finalidade fornecida pelo cliente na fase de confirmação
    confirmation_purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Fase da análise: "initial" ou "confirmation"
    phase: Mapped[str] = mapped_column(String(16), default="initial")

    # ── Controle de estado ────────────────────────────────────────────────────
    status: Mapped[RiskAnalysisStatus] = mapped_column(
        Enum(RiskAnalysisStatus), default=RiskAnalysisStatus.PENDING
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relacionamentos
    transaction: Mapped["Transaction"] = relationship(  # noqa: F821
        "Transaction", back_populates="risk_analysis"
    )

    def __repr__(self) -> str:
        return (
            f"<RiskAnalysis {self.external_id} "
            f"score={self.overall_risk_score} action={self.recommended_action}>"
        )
