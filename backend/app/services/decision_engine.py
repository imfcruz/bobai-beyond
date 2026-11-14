"""
Motor de Decisão — converte o AgentResult final em uma decisão estruturada.

Aplica políticas configuráveis, versionadas e testáveis.
Os limiares são parâmetros demonstrativos documentados —
NÃO representam critérios oficiais do Banco do Brasil.

SEGURANÇA:
  A LLM não tem autoridade para modificar limiares ou aprovar ações proibidas.
  Divergências entre agentes são registradas e influenciam a decisão final.
  Falha de agente nunca produz aprovação automática.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import structlog

from app.agents.base import AgentResult
from app.core.config import settings
from app.models.risk_analysis import RecommendedAction
from app.models.transaction import RiskLevel, TransactionStatus

logger = structlog.get_logger(__name__)

# ── Política de decisão versionada ───────────────────────────────────────────
# Limiares demonstrativos para o MVP acadêmico.
# NÃO representam critérios do Banco do Brasil.

POLICY_VERSION = "1.0.0"

POLICY_DOC = (
    "Política demonstrativa v1.0.0 — MVP Acadêmico. "
    "Limiares: LOW<0.30, MEDIUM<0.60, HIGH<0.85, CRITICAL>=0.85. "
    "Divergência >0.40 entre agentes eleva cautela. "
    "Hard-block é absoluto e não pode ser contornado."
)


@dataclass
class AgentContribution:
    """Score e flags de um agente individual — para auditoria."""
    agent_name: str
    risk_score: float
    flags: list[str]


@dataclass
class Decision:
    """Resultado estruturado do motor de decisão."""

    risk_level: RiskLevel
    recommended_action: RecommendedAction
    transaction_status: TransactionStatus
    risk_score: float
    reasoning: str
    flags: list[str]

    # Rastreabilidade da política
    policy_version: str = POLICY_VERSION
    divergence_detected: bool = False
    divergence_details: str | None = None
    agent_contributions: list[AgentContribution] = field(default_factory=list)

    # Tempo de execução do motor
    decision_time_ms: int = 0


def make_decision(
    result: AgentResult,
    sub_results: list[AgentResult] | None = None,
) -> Decision:
    """
    Converte um AgentResult em uma Decision usando a política versionada.

    Limiares demonstrativos (MVP):
        score < 0.30   → LOW    → APPROVE       → RELEASED
        score < 0.60   → MEDIUM → REQUEST_CONFIRMATION → UNDER_VERIFICATION
        score < 0.85   → HIGH   → REQUEST_CONFIRMATION → UNDER_VERIFICATION
        score >= 0.85  → CRITICAL → ESCALATE_TO_HUMAN  → HUMAN_REVIEW_PENDING
        hard_block     → CRITICAL → BLOCK        → REJECTED (absoluto)

    Divergência entre agentes:
        Se spread entre scores > 0.40, registra divergência e eleva cautela.

    A LLM NÃO pode modificar estes limiares nem aprovar transações bloqueadas.
    """
    t0 = time.monotonic()
    score = result.risk_score
    sub_results = sub_results or []

    # ── Análise de divergência ────────────────────────────────────────────────
    divergence_detected = False
    divergence_details: str | None = None
    agent_contributions: list[AgentContribution] = []

    if sub_results:
        agent_scores = [r.risk_score for r in sub_results if r.agent_name != "risk_agent"]
        agent_contributions = [
            AgentContribution(
                agent_name=r.agent_name,
                risk_score=r.risk_score,
                flags=list(r.flags),
            )
            for r in sub_results
        ]
        if len(agent_scores) >= 2:
            spread = max(agent_scores) - min(agent_scores)
            if spread > 0.40:
                divergence_detected = True
                # Identifica quais agentes discordaram
                high_agents = [r.agent_name for r in sub_results if r.risk_score >= 0.60]
                low_agents = [r.agent_name for r in sub_results if r.risk_score < 0.30]
                divergence_details = json.dumps({
                    "spread": round(spread, 3),
                    "high_risk_agents": high_agents,
                    "low_risk_agents": low_agents,
                    "note": (
                        "Divergência significativa detectada. Avaliações discordantes "
                        "não foram descartadas — resultado conservador aplicado."
                    ),
                })
                logger.warning(
                    "Decision: agent divergence detected",
                    spread=spread,
                    high_agents=high_agents,
                    low_agents=low_agents,
                )
                # Não descarta avaliações de alto risco — eleva levemente
                score = min(1.0, score + 0.05)

    # ── Hard block é absoluto — não pode ser contornado pela LLM ─────────────
    if result.metadata.get("hard_block"):
        level = RiskLevel.CRITICAL
        action = RecommendedAction.BLOCK
        status = TransactionStatus.REJECTED
        reasoning = f"[BLOQUEIO ABSOLUTO — {POLICY_VERSION}] Transação bloqueada por regra determinística. {result.reasoning}"
        logger.warning(
            "Decision: HARD BLOCK (absolute — LLM cannot override)",
            score=score,
            flags=result.flags,
            policy=POLICY_VERSION,
        )

    # ── LOW ───────────────────────────────────────────────────────────────────
    elif score < settings.RISK_THRESHOLD_LOW:
        level = RiskLevel.LOW
        action = RecommendedAction.APPROVE
        status = TransactionStatus.RELEASED
        reasoning = f"[{POLICY_VERSION}] {result.reasoning}"
        logger.info("Decision: APPROVE", score=score, policy=POLICY_VERSION)

    # ── MEDIUM ────────────────────────────────────────────────────────────────
    elif score < settings.RISK_THRESHOLD_MEDIUM:
        level = RiskLevel.MEDIUM
        action = RecommendedAction.REQUEST_CONFIRMATION
        status = TransactionStatus.AWAITING_CONFIRMATION
        reasoning = f"[{POLICY_VERSION}] Confirmação contextual necessária. {result.reasoning}"
        logger.info("Decision: REQUEST_CONFIRMATION (medium)", score=score, policy=POLICY_VERSION)

    # ── HIGH ──────────────────────────────────────────────────────────────────
    elif score < settings.RISK_THRESHOLD_HIGH:
        level = RiskLevel.HIGH
        action = RecommendedAction.REQUEST_CONFIRMATION
        status = TransactionStatus.AWAITING_CONFIRMATION
        reasoning = f"[{POLICY_VERSION}] Verificação adicional necessária — risco elevado. {result.reasoning}"
        logger.info("Decision: REQUEST_CONFIRMATION (high)", score=score, policy=POLICY_VERSION)

    # ── CRITICAL ─────────────────────────────────────────────────────────────
    else:
        level = RiskLevel.CRITICAL
        action = RecommendedAction.ESCALATE_TO_HUMAN
        status = TransactionStatus.HUMAN_REVIEW_PENDING
        reasoning = f"[{POLICY_VERSION}] Revisão humana obrigatória — risco crítico. {result.reasoning}"
        logger.warning(
            "Decision: ESCALATE_TO_HUMAN (critical)",
            score=score,
            flags=result.flags,
            policy=POLICY_VERSION,
        )

    # Divergência pode elevar status de AWAITING_CONFIRMATION para HUMAN_REVIEW_PENDING
    if divergence_detected and status == TransactionStatus.AWAITING_CONFIRMATION:
        status = TransactionStatus.HUMAN_REVIEW_PENDING
        action = RecommendedAction.ESCALATE_TO_HUMAN
        reasoning += " | Divergência significativa entre agentes — encaminhado para revisão humana."

    decision_time_ms = int((time.monotonic() - t0) * 1000)

    return Decision(
        risk_level=level,
        recommended_action=action,
        transaction_status=status,
        risk_score=score,
        reasoning=reasoning,
        flags=result.flags,
        policy_version=POLICY_VERSION,
        divergence_detected=divergence_detected,
        divergence_details=divergence_details,
        agent_contributions=agent_contributions,
        decision_time_ms=decision_time_ms,
    )
