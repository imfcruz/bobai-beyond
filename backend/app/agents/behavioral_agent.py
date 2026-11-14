"""
Agente Comportamental — compara operação atual com padrão histórico do cliente.

Distingue claramente comportamento incomum de fraude comprovada.
"""

from __future__ import annotations

import json
import time

import structlog

from app.agents.base import (
    AgentContext,
    AgentMode,
    AgentResult,
    AgentRiskLevel,
    AgentStatus,
    BaseAgent,
)
from app.agents.mode import resolve_agent_mode
from app.agents.prompts import BEHAVIORAL_AGENT_SYSTEM
from app.services.llm_client import BaseLLMClient, get_llm_client

logger = structlog.get_logger(__name__)


def _parse_typical_hours(json_str: str | None) -> list[tuple[int, int]]:
    if not json_str:
        return []
    try:
        ranges = json.loads(json_str)
        result = []
        for r in ranges:
            parts = r.split("-")
            if len(parts) == 2:
                start = int(parts[0].split(":")[0])
                end = int(parts[1].split(":")[0])
                result.append((start, end))
        return result
    except Exception:
        return []


class BehavioralAgent(BaseAgent):

    def __init__(self, llm: BaseLLMClient | None = None):
        self._llm = llm or get_llm_client()

    @property
    def name(self) -> str:
        return "behavioral_agent"

    async def analyze(self, ctx: AgentContext) -> AgentResult:
        t0 = time.monotonic()
        mode = resolve_agent_mode(self._llm.provider_name)
        model_used = self._llm.model_identifier if mode == AgentMode.AI_MODE else "rules/heuristic-v1"

        signals: list[str] = []
        evidence: list[str] = []
        score = 0.0

        # Desvio 1: Valor acima do máximo histórico
        if ctx.client_max_transfer > 0 and ctx.amount > ctx.client_max_transfer:
            ratio = float(ctx.amount / ctx.client_max_transfer)
            if ratio > 2:
                score += 0.30
                signals.append("amount_2x_above_max_historical")
                evidence.append(f"Valor {ratio:.1f}× acima do máximo histórico (R${ctx.client_max_transfer}).")
            else:
                score += 0.15
                signals.append("amount_above_max_historical")
                evidence.append(f"Valor acima do máximo histórico do cliente (R${ctx.client_max_transfer}).")

        # Desvio 2: Valor acima da média
        if ctx.client_avg_transfer > 0:
            avg_ratio = float(ctx.amount / ctx.client_avg_transfer)
            if avg_ratio > 10:
                score += 0.25
                signals.append("amount_10x_above_avg")
                evidence.append(f"Valor {avg_ratio:.1f}× acima da média histórica (R${ctx.client_avg_transfer}).")
            elif avg_ratio > 4:
                score += 0.15
                signals.append("amount_4x_above_avg")
                evidence.append(f"Valor {avg_ratio:.1f}× acima da média histórica.")

        # Desvio 3: Horário atípico
        typical = _parse_typical_hours(ctx.typical_hours)
        if typical:
            in_typical = any(s <= ctx.operation_hour < e for s, e in typical)
            if not in_typical:
                score += 0.10
                signals.append("atypical_operation_hour")
                evidence.append(
                    f"Operação às {ctx.operation_hour}h fora do horário habitual do cliente."
                )

        # Desvio 4: Beneficiário nunca utilizado
        if ctx.beneficiary_transfer_count == 0:
            score += 0.10
            signals.append("beneficiary_never_used")
            evidence.append("Beneficiário sem histórico de transferências anteriores.")

        # Desvio 5: Spike em perfil conservador
        if (
            ctx.client_account_age_days > 365
            and ctx.client_risk_profile == "low"
            and ctx.amount > ctx.client_max_transfer * 2
        ):
            score += 0.20
            signals.append("unusual_profile_spike")
            evidence.append(
                "Cliente com perfil historicamente conservador realizando operação muito acima do padrão."
            )

        score = self._clamp(score)
        status = AgentStatus.SUCCESS

        if mode == AgentMode.AI_MODE:
            try:
                llm_data = await self._llm.complete_json(
                    prompt=f"Dados da transação para análise:\n{ctx.to_analysis_text()}",
                    system_prompt=BEHAVIORAL_AGENT_SYSTEM,
                )
                llm_score = _level_to_score(llm_data.get("risk_level", "LOW"))
                score = self._clamp(score * 0.7 + llm_score * 0.3)
                for s in llm_data.get("detected_signals", []):
                    if s not in signals:
                        signals.append(s)
                for e in llm_data.get("evidence", []):
                    if e not in evidence:
                        evidence.append(e)
                model_used = self._llm.model_identifier
            except Exception as exc:
                logger.warning("BehavioralAgent LLM failed", error=type(exc).__name__)
                status = AgentStatus.FALLBACK_USED
                mode = AgentMode.RULES_MODE
                model_used = "rules/heuristic-v1 (llm_fallback)"

        risk_level = self._score_to_risk_level(score)
        action = self._risk_to_action(risk_level)
        explanation = _build_explanation(score, signals, risk_level)

        ms = int((time.monotonic() - t0) * 1000)
        logger.info("BehavioralAgent completed", score=score, signals=signals, mode=mode.value, ms=ms)

        return AgentResult(
            agent_name=self.name,
            analysis_id=ctx.analysis_id,
            risk_level=risk_level,
            confidence=_score_to_confidence(score),
            detected_signals=signals,
            evidence=evidence,
            explanation=explanation,
            recommended_action=action,
            model_used=model_used,
            execution_time_ms=ms,
            status=status,
            mode=mode,
            risk_score=score,
            flags=signals,
            reasoning=explanation,
            metadata={
                "operation_hour": ctx.operation_hour,
                "amount_to_avg_ratio": (
                    float(ctx.amount / ctx.client_avg_transfer)
                    if ctx.client_avg_transfer > 0 else None
                ),
            },
        )


def _level_to_score(level: str) -> float:
    return {"LOW": 0.15, "MEDIUM": 0.45, "HIGH": 0.72, "CRITICAL": 0.92}.get(level.upper(), 0.15)


def _score_to_confidence(score: float) -> float:
    return 0.75 if score < 0.25 or score > 0.70 else 0.60


def _build_explanation(score: float, signals: list[str], level: AgentRiskLevel) -> str:
    sig_str = ", ".join(signals) if signals else "nenhum"
    note = (
        "Desvio comportamental relevante — comportamento incomum não implica necessariamente fraude."
        if score >= 0.30
        else "Operação dentro do padrão comportamental histórico."
    )
    return (
        f"Análise Comportamental: nível {level.value} (score={score:.2f}). "
        f"Desvios detectados: {sig_str}. {note}"
    )
