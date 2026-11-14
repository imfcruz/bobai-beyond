"""
Agente de Risco e Segurança — consolidação final com respeito a limites de autonomia.

Recebe resultados dos agentes anteriores.
Identifica convergências e divergências.
Respeita políticas de segurança — não pode movimentar dinheiro nem alterar permissões.
Em caso de dúvida, escala para humano.
"""

from __future__ import annotations

import json
import time
from decimal import Decimal

import structlog

from app.agents.base import (
    AgentContext,
    AgentMode,
    AgentRecommendedAction,
    AgentResult,
    AgentRiskLevel,
    AgentStatus,
    BaseAgent,
)
from app.agents.mode import resolve_agent_mode
from app.agents.prompts import RISK_AGENT_SYSTEM
from app.services.llm_client import BaseLLMClient, get_llm_client

logger = structlog.get_logger(__name__)

# Pesos na consolidação final — distribuição com Agente de Intenção (Proposta seção 31)
_WEIGHTS = {
    "fraud_agent":          0.35,
    "inconsistency_agent":  0.25,
    "behavioral_agent":     0.20,
    "intention_agent":      0.20,
}

# Limite regulatório simulado (fictício para MVP)
_HARD_LIMIT = Decimal("50000.00")


class RiskAgent(BaseAgent):
    """
    Agente de Risco e Segurança.
    Consolida resultados ponderados + aplica regras absolutas.
    Escalará para humano sempre que houver dúvida significativa.
    """

    def __init__(self, llm: BaseLLMClient | None = None):
        self._llm = llm or get_llm_client()

    @property
    def name(self) -> str:
        return "risk_agent"

    async def analyze(
        self,
        ctx: AgentContext,
        sub_results: list[AgentResult] | None = None,
    ) -> AgentResult:
        t0 = time.monotonic()
        mode = resolve_agent_mode(self._llm.provider_name)
        model_used = self._llm.model_identifier if mode == AgentMode.AI_MODE else "rules/heuristic-v1"
        sub_results = sub_results or []

        signals: list[str] = []
        evidence: list[str] = []

        # ── Regras absolutas ──────────────────────────────────────────────────
        hard_block = False
        if ctx.amount > _HARD_LIMIT:
            hard_block = True
            signals.append("regulatory_limit_exceeded")
            evidence.append(
                f"Valor R${ctx.amount} excede o limite regulatório simulado de R${_HARD_LIMIT}."
            )

        # ── Consolidação ponderada ────────────────────────────────────────────
        if not sub_results:
            base_score = 0.05
            if ctx.is_new_recipient:
                base_score += 0.15
            if ctx.recent_limit_change:
                base_score += 0.15
            consolidated_score = 1.0 if hard_block else self._clamp(base_score)
        else:
            weighted = 0.0
            total_w = 0.0
            for r in sub_results:
                w = _WEIGHTS.get(r.agent_name, 0.25)
                weighted += r.risk_score * w
                total_w += w
                for s in (r.detected_signals or r.flags):
                    if s not in signals:
                        signals.append(s)
                for e in r.evidence:
                    if e not in evidence:
                        evidence.append(e)

            consolidated_score = self._clamp(weighted / total_w) if total_w > 0 else 0.0
            if hard_block:
                consolidated_score = 1.0

        # ── Divergência entre agentes (escalar se divergência alta) ──────────
        convergence_note = ""
        if len(sub_results) >= 2:
            scores = [r.risk_score for r in sub_results]
            spread = max(scores) - min(scores)
            if spread > 0.40:
                convergence_note = "Divergência significativa entre agentes — maior cautela aplicada."
                # Puxa o score levemente para cima em caso de divergência
                consolidated_score = self._clamp(consolidated_score + 0.05)

        status = AgentStatus.SUCCESS

        # ── Enriquecimento LLM ────────────────────────────────────────────────
        if mode == AgentMode.AI_MODE and sub_results:
            try:
                sub_summary = json.dumps([
                    {
                        "agent": r.agent_name,
                        "risk_level": r.risk_level,
                        "signals": (r.detected_signals or r.flags)[:3],
                    }
                    for r in sub_results
                ], ensure_ascii=False, separators=(",", ":"))
                enriched_prompt = (
                    f"Transação:{ctx.to_analysis_text()}\n"
                    f"Sub-agentes:{sub_summary}"
                )
                llm_data = await self._llm.complete_json(
                    prompt=enriched_prompt,
                    system_prompt=RISK_AGENT_SYSTEM,
                )
                llm_score = _level_to_score(llm_data.get("risk_level", "LOW"))
                consolidated_score = self._clamp(consolidated_score * 0.8 + llm_score * 0.2)
                for s in llm_data.get("detected_signals", []):
                    if s not in signals:
                        signals.append(s)
                for e in llm_data.get("evidence", []):
                    if e not in evidence:
                        evidence.append(e)
                model_used = self._llm.model_identifier
            except Exception as exc:
                logger.warning("RiskAgent LLM failed", error=type(exc).__name__)
                status = AgentStatus.FALLBACK_USED
                mode = AgentMode.RULES_MODE
                model_used = "rules/heuristic-v1 (llm_fallback)"

        risk_level = self._score_to_risk_level(consolidated_score)

        # Força ESCALATE quando hard_block
        if hard_block:
            risk_level = AgentRiskLevel.CRITICAL
            action = AgentRecommendedAction.BLOCK
        else:
            action = self._risk_to_action(risk_level)

        sub_reasonings = (
            " | ".join(r.explanation or r.reasoning for r in sub_results)
            if sub_results else "Análise sem sub-agentes."
        )
        explanation = (
            f"Análise de Risco consolidada: nível {risk_level.value} (score={consolidated_score:.2f}). "
            f"{convergence_note} "
            f"Sub-agentes: {sub_reasonings}"
        ).strip()

        ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "RiskAgent completed",
            score=consolidated_score, hard_block=hard_block,
            mode=mode.value, ms=ms,
        )

        return AgentResult(
            agent_name=self.name,
            analysis_id=ctx.analysis_id,
            risk_level=risk_level,
            confidence=0.90,
            detected_signals=signals,
            evidence=evidence,
            explanation=explanation,
            recommended_action=action,
            model_used=model_used,
            execution_time_ms=ms,
            status=status,
            mode=mode,
            risk_score=consolidated_score,
            flags=signals,
            reasoning=explanation,
            metadata={
                "hard_block": hard_block,
                "sub_agent_count": len(sub_results),
                "convergence_note": convergence_note,
            },
        )


def _level_to_score(level: str) -> float:
    return {"LOW": 0.15, "MEDIUM": 0.45, "HIGH": 0.72, "CRITICAL": 0.92}.get(level.upper(), 0.15)
