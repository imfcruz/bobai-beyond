"""
Agente de Fraude — análise independente de sinais de fraude.

Executa análise INDEPENDENTE dos demais agentes.
Pode ser executado em PARALELO via asyncio.gather.
Não declara fraude categoricamente sem comprovação.

Dois modos:
  RULES_MODE — heurísticas determinísticas, sem LLM.
  AI_MODE    — heurísticas + enriquecimento via LLM com validação Pydantic.
"""

from __future__ import annotations

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
from app.agents.prompts import FRAUD_AGENT_SYSTEM
from app.services.llm_client import BaseLLMClient, get_llm_client

logger = structlog.get_logger(__name__)

# Palavras-chave de engenharia social — tratadas como DADOS, não instruções
_SOCIAL_KW = [
    "funcionário do banco", "funcionario do banco",
    "banco me pediu", "banco ligou",
    "proteger minha conta", "transferir para conta segura",
    "suporte bancário", "suporte bancario",
    "me orientou", "me instruiu",
    "central de segurança", "central de seguranca",
]


class FraudAgent(BaseAgent):
    """
    Agente de Fraude — análise independente e paralelizável.
    Combina heurísticas determinísticas com enriquecimento LLM opcional.
    """

    def __init__(self, llm: BaseLLMClient | None = None):
        self._llm = llm or get_llm_client()

    @property
    def name(self) -> str:
        return "fraud_agent"

    async def analyze(self, ctx: AgentContext) -> AgentResult:
        t0 = time.monotonic()
        mode = resolve_agent_mode(self._llm.provider_name)
        model_used = self._llm.model_identifier if mode == AgentMode.AI_MODE else "rules/heuristic-v1"

        # ── Heurísticas determinísticas (sempre executam) ─────────────────────
        signals: list[str] = []
        evidence: list[str] = []
        score = 0.0

        if ctx.is_new_recipient:
            score += 0.20
            signals.append("new_beneficiary")
            evidence.append("Beneficiário cadastrado recentemente, sem histórico anterior.")

        if ctx.funding_source == "credit" and ctx.recent_limit_change:
            score += 0.35
            signals.append("credit_pix_after_limit_increase")
            evidence.append(
                "Pix no crédito iniciado pouco depois da aprovação de aumento de limite."
            )

        if ctx.client_avg_transfer > 0:
            ratio = float(ctx.amount / ctx.client_avg_transfer)
            if ratio > 15:
                score += 0.35
                signals.append("amount_far_above_avg")
                evidence.append(f"Valor {ratio:.1f}× acima da média histórica do cliente.")
            elif ratio > 5:
                score += 0.20
                signals.append("amount_above_avg")
                evidence.append(f"Valor {ratio:.1f}× acima da média histórica do cliente.")

        # Análise da finalidade declarada — tratada como DADO, não instrução
        purpose_lower = ctx.purpose.lower()
        # Detecta possível tentativa de injeção de prompt
        injection_patterns = ["ignore", "disregard", "forget", "you are now", "act as"]
        if any(p in purpose_lower for p in injection_patterns):
            signals.append("possible_prompt_injection_attempt")
            evidence.append(
                "Campo 'purpose' contém padrão suspeito de injeção de instrução. "
                "Registrado como sinal de risco adicional."
            )
            score += 0.20

        if any(kw in purpose_lower for kw in _SOCIAL_KW):
            score += 0.40
            signals.append("social_engineering_keyword")
            evidence.append("Finalidade menciona orientação de terceiro ou urgência bancária.")

        if not ctx.device_recognized and ctx.amount > ctx.client_avg_transfer:
            score += 0.20
            signals.append("unrecognized_device_high_amount")
            evidence.append("Dispositivo não reconhecido com valor acima da média.")

        if ctx.client_account_age_days < 180 and ctx.amount > ctx.client_max_transfer:
            score += 0.15
            signals.append("new_account_above_max")
            evidence.append("Conta com menos de 180 dias realizando operação acima do máximo histórico.")

        score = self._clamp(score)
        status = AgentStatus.SUCCESS

        # ── Enriquecimento LLM (apenas em AI_MODE) ────────────────────────────
        if mode == AgentMode.AI_MODE:
            try:
                llm_data = await self._llm.complete_json(
                    prompt=f"Dados da transação para análise:\n{ctx.to_analysis_text()}",
                    system_prompt=FRAUD_AGENT_SYSTEM,
                )
                # Combina score heurístico (70%) + LLM (30%)
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
                logger.warning("FraudAgent LLM failed, using rules fallback", error=type(exc).__name__, detail=str(exc)[:300])
                status = AgentStatus.FALLBACK_USED
                mode = AgentMode.RULES_MODE
                model_used = "rules/heuristic-v1 (llm_fallback)"

        risk_level = self._score_to_risk_level(score)
        action = self._risk_to_action(risk_level)
        explanation = _build_explanation("Fraude", score, signals, risk_level)

        ms = int((time.monotonic() - t0) * 1000)
        logger.info("FraudAgent completed", score=score, signals=signals, mode=mode.value, ms=ms)

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
            # legados
            risk_score=score,
            flags=signals,
            reasoning=explanation,
            metadata={"heuristic_score": score},
        )


# ── Helpers locais ────────────────────────────────────────────────────────────

def _level_to_score(level: str) -> float:
    return {"LOW": 0.15, "MEDIUM": 0.45, "HIGH": 0.72, "CRITICAL": 0.92}.get(level.upper(), 0.15)


def _score_to_confidence(score: float) -> float:
    """Confidence inversamente proporcional à incerteza da zona."""
    if score < 0.20 or score > 0.80:
        return 0.85
    return 0.65


def _build_explanation(agent_label: str, score: float, signals: list[str], level: AgentRiskLevel) -> str:
    sig_str = ", ".join(signals) if signals else "nenhum"
    return (
        f"Análise de {agent_label}: nível {level.value} (score={score:.2f}). "
        f"Sinais identificados: {sig_str}. "
        f"{'Indicadores sugerem risco elevado — revisão recomendada.' if score >= 0.55 else 'Operação dentro de parâmetros aceitáveis.'}"
    )
