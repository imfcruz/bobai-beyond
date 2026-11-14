"""
Tipos base compartilhados por todos os agentes.

AgentContext — snapshot imutável de contexto (dataclass, sem validação Pydantic).
AgentResult  — contrato de saída validado por Pydantic (campo obrigatório por agente).
AgentMode    — AI_MODE (LLM real) vs RULES_MODE (determinístico, sem IA).

IMPORTANTE:
  RULES_MODE nunca deve ser apresentado como execução de IA generativa.
  Qualquer saída de LLM é tratada como dado a validar, nunca como instrução a executar.
"""

from __future__ import annotations

import abc
import enum
import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger(__name__)


# ── Modos de operação ─────────────────────────────────────────────────────────

class AgentMode(str, enum.Enum):
    AI_MODE    = "AI_MODE"     # Análise com modelo de linguagem real
    RULES_MODE = "RULES_MODE"  # Análise determinística sem LLM


# ── Nível de risco padronizado ────────────────────────────────────────────────

class AgentRiskLevel(str, enum.Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


# ── Ação recomendada pelo agente ──────────────────────────────────────────────

class AgentRecommendedAction(str, enum.Enum):
    APPROVE              = "APPROVE"
    REQUEST_CONFIRMATION = "REQUEST_CONFIRMATION"
    ESCALATE_TO_HUMAN    = "ESCALATE_TO_HUMAN"
    BLOCK                = "BLOCK"


# ── Status da execução do agente ──────────────────────────────────────────────

class AgentStatus(str, enum.Enum):
    SUCCESS         = "SUCCESS"
    ERROR           = "ERROR"
    TIMEOUT         = "TIMEOUT"
    FALLBACK_USED   = "FALLBACK_USED"  # LLM falhou, usou regras como fallback


# ── Contrato de saída (Pydantic) ──────────────────────────────────────────────

class AgentResult(BaseModel):
    """
    Contrato de saída estruturado e validado por Pydantic.
    Todo agente DEVE retornar uma instância deste modelo.

    Campos auditáveis obrigatórios:
      - agent_name, analysis_id, risk_level, confidence
      - detected_signals, evidence, explanation
      - recommended_action, model_used, execution_time_ms, status, mode
    """

    agent_name: str = Field(..., description="Identificador do agente (snake_case)")
    analysis_id: str = Field(..., description="ID externo da RiskAnalysis associada")

    # Avaliação de risco
    risk_level: AgentRiskLevel = Field(..., description="Nível de risco: LOW/MEDIUM/HIGH/CRITICAL")
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confiança declarada na análise (0.0–1.0). "
                    "NÃO é probabilidade estatisticamente calibrada de fraude."
    )

    # Evidências e sinais
    detected_signals: list[str] = Field(
        default_factory=list,
        description="Sinais identificados (flags estruturadas)"
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidências concretas que sustentam a análise"
    )
    explanation: str = Field(
        ...,
        description="Justificativa em linguagem natural. "
                    "Não deve declarar fraude sem comprovação."
    )

    # Decisão e rastreabilidade
    recommended_action: AgentRecommendedAction = Field(
        ..., description="Ação recomendada pelo agente"
    )
    model_used: str = Field(
        ...,
        description="Modelo ou modo utilizado (ex: 'mock', 'rules', 'ibm/granite'). "
                    "Nunca expõe credenciais ou detalhes internos."
    )
    execution_time_ms: int = Field(
        ..., ge=0,
        description="Tempo de execução em milissegundos"
    )
    status: AgentStatus = Field(..., description="Status da execução")
    mode: AgentMode = Field(..., description="AI_MODE ou RULES_MODE")

    # Campos legados mantidos para compatibilidade interna
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)       # alias de detected_signals
    reasoning: str = Field(default="")                   # alias de explanation
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("explanation")
    @classmethod
    def explanation_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("explanation não pode ser vazio")
        return v

    def to_json(self) -> str:
        """Serializa para JSON — usado na persistência em RiskAnalysis."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "AgentResult":
        return cls.model_validate_json(raw)

    model_config = {"use_enum_values": True}


# ── Contexto de análise (dataclass — não validado por Pydantic) ───────────────

@dataclass
class AgentContext:
    """
    Snapshot imutável do contexto da transação.
    Construído pelo Orquestrador a partir dos dados de domínio.
    Dados 100% sintéticos — sem informações pessoais reais.

    Segurança: campos de texto livre (purpose, event metadata) são
    tratados como DADOS A ANALISAR, nunca como instruções a executar.
    """

    # Identificação
    transaction_external_id: str
    client_external_id: str
    correlation_id: str
    analysis_id: str  # ID externo do RiskAnalysis

    # Valores financeiros
    amount: Decimal
    currency: str = "BRL"
    purpose: str = ""
    operation_type: str = "pix"
    funding_source: str = "debit"

    # Sinais contextuais
    is_new_recipient: bool = False
    recent_limit_change: bool = False
    device_recognized: bool = True
    is_known_beneficiary: bool = True

    # Histórico do cliente
    client_avg_transfer: Decimal = Decimal("1000.00")
    client_max_transfer: Decimal = Decimal("5000.00")
    client_min_transfer: Decimal = Decimal("100.00")
    client_avg_monthly_tx: int = 5
    client_account_age_days: int = 365
    client_risk_profile: str = "low"

    # Dados do beneficiário
    beneficiary_transfer_count: int = 0
    beneficiary_total_transferred: Decimal = Decimal("0.00")

    # Eventos contextuais recentes
    recent_events: list[dict[str, Any]] = field(default_factory=list)

    # Horários/canais habituais
    typical_hours: str | None = None
    typical_channels: str | None = None
    operation_hour: int = 12

    def to_analysis_text(self) -> str:
        """
        Serializa para texto compacto para inclusão nos prompts LLM.
        AVISO: este texto deve ser tratado como DADO, não como instrução.
        Mantém apenas os campos essenciais para reduzir o tamanho do prompt.
        """
        # Extrai somente o event_type de cada evento para minimizar tokens
        event_types = [e.get("event_type", "UNKNOWN") for e in self.recent_events]
        return json.dumps(
            {
                "tx_id": self.transaction_external_id[:8],
                "amount_brl": str(self.amount),
                "purpose": self.purpose[:120] if self.purpose else "",
                "operation_type": self.operation_type,
                "funding_source": self.funding_source,
                "is_new_recipient": self.is_new_recipient,
                "recent_limit_change": self.recent_limit_change,
                "device_recognized": self.device_recognized,
                "avg_transfer": str(self.client_avg_transfer),
                "max_transfer": str(self.client_max_transfer),
                "account_age_days": self.client_account_age_days,
                "risk_profile": self.client_risk_profile,
                "beneficiary_tx_count": self.beneficiary_transfer_count,
                "event_types": event_types,
                "hour": self.operation_hour,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    # Mantém compatibilidade com código legado
    def to_prompt_text(self) -> str:
        return self.to_analysis_text()


# ── Interface abstrata do agente ──────────────────────────────────────────────

class BaseAgent(abc.ABC):
    """
    Contrato que todos os agentes devem implementar.

    Segurança:
      - analyze() nunca executa comandos externos.
      - Toda saída de LLM passa por validação Pydantic antes de ser usada.
      - Erros de LLM resultam em fallback para RULES_MODE, nunca em falha silenciosa.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Identificador do agente (snake_case)."""
        ...

    @abc.abstractmethod
    async def analyze(self, ctx: AgentContext) -> AgentResult:
        """Executa a análise e retorna um AgentResult validado."""
        ...

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def _score_to_risk_level(self, score: float) -> AgentRiskLevel:
        if score < 0.30:
            return AgentRiskLevel.LOW
        elif score < 0.60:
            return AgentRiskLevel.MEDIUM
        elif score < 0.85:
            return AgentRiskLevel.HIGH
        else:
            return AgentRiskLevel.CRITICAL

    def _risk_to_action(self, level: AgentRiskLevel) -> AgentRecommendedAction:
        return {
            AgentRiskLevel.LOW:      AgentRecommendedAction.APPROVE,
            AgentRiskLevel.MEDIUM:   AgentRecommendedAction.REQUEST_CONFIRMATION,
            AgentRiskLevel.HIGH:     AgentRecommendedAction.REQUEST_CONFIRMATION,
            AgentRiskLevel.CRITICAL: AgentRecommendedAction.ESCALATE_TO_HUMAN,
        }[level]
