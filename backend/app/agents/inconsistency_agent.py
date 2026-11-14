"""
Agente de Inconsistência — detecta contradições entre eventos e finalidade declarada.

Compara a finalidade declarada com a sequência de eventos observados.
Identifica sinais de orientação de terceiros e incoerências operacionais.
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
from app.agents.prompts import INCONSISTENCY_AGENT_SYSTEM
from app.services.llm_client import BaseLLMClient, get_llm_client

logger = structlog.get_logger(__name__)

# Frases que sugerem orientação de terceiro — tratadas como DADOS
_THIRD_PARTY_KW = [
    "me pediu", "me orientou", "me instruiu", "me mandou",
    "funcionário", "funcionario", "gerente", "suporte",
    "central", "ligou", "enviou mensagem",
]


class InconsistencyAgent(BaseAgent):

    def __init__(self, llm: BaseLLMClient | None = None):
        self._llm = llm or get_llm_client()

    @property
    def name(self) -> str:
        return "inconsistency_agent"

    async def analyze(self, ctx: AgentContext) -> AgentResult:
        t0 = time.monotonic()
        mode = resolve_agent_mode(self._llm.provider_name)
        model_used = self._llm.model_identifier if mode == AgentMode.AI_MODE else "rules/heuristic-v1"

        signals: list[str] = []
        evidence: list[str] = []
        score = 0.0

        event_types = [e.get("event_type", "") for e in ctx.recent_events]

        # Padrão 1: Alteração de limite → transferência imediata
        if ctx.recent_limit_change:
            score += 0.30
            signals.append("limit_changed_before_transfer")
            evidence.append("Um limite financeiro foi alterado pouco antes da operação.")

        if (
            ctx.funding_source == "credit"
            and "AUMENTO_LIMITE_CREDITO_APROVADO" in event_types
        ):
            score += 0.30
            signals.append("approved_credit_increase_followed_by_credit_pix")
            evidence.append(
                "Aumento de limite aprovado e seguido por Pix no crédito na mesma janela de risco."
            )

        # Padrão 2: Cadastro de beneficiário + transferência na mesma sessão
        if ctx.is_new_recipient and "CADASTRO_BENEFICIARIO" in event_types:
            score += 0.25
            signals.append("new_beneficiary_registered_same_session")
            evidence.append("Beneficiário cadastrado e operação iniciada na mesma sessão.")

        # Padrão 3: Múltiplos logins recentes
        login_count = event_types.count("LOGIN")
        if login_count >= 3:
            score += 0.20
            signals.append("multiple_logins_detected")
            evidence.append(f"{login_count} logins detectados em janela curta antes da operação.")
        elif login_count == 2:
            score += 0.10
            signals.append("double_login_detected")
            evidence.append("Dois logins detectados antes da operação — pode indicar acesso não autorizado.")

        # Padrão 4: Sequência completa de ataque
        has_limit = "ALTERACAO_LIMITE" in event_types
        has_ben   = "CADASTRO_BENEFICIARIO" in event_types
        has_tx    = "INICIO_TRANSFERENCIA" in event_types
        if has_limit and has_ben and has_tx:
            score += 0.20
            signals.append("full_social_engineering_sequence")
            evidence.append(
                "Sequência completa detectada: alteração de limite → "
                "cadastro de beneficiário → transferência."
            )

        # Padrão 5: Finalidade menciona orientação de terceiro
        purpose_lower = ctx.purpose.lower()
        if any(kw in purpose_lower for kw in _THIRD_PARTY_KW):
            score += 0.20
            signals.append("third_party_instruction_declared")
            evidence.append("Finalidade declara orientação ou instrução de terceiro.")

        # Padrão 6: Finalidade ausente em operação de alto valor
        if not ctx.purpose.strip() and ctx.amount > ctx.client_avg_transfer * 3:
            score += 0.10
            signals.append("missing_purpose_high_value")
            evidence.append("Operação de alto valor sem finalidade declarada.")

        score = self._clamp(score)
        status = AgentStatus.SUCCESS

        if mode == AgentMode.AI_MODE:
            try:
                llm_data = await self._llm.complete_json(
                    prompt=f"Dados da transação para análise:\n{ctx.to_analysis_text()}",
                    system_prompt=INCONSISTENCY_AGENT_SYSTEM,
                )
                llm_score = _level_to_score(llm_data.get("risk_level", "LOW"))
                score = self._clamp(score * 0.65 + llm_score * 0.35)
                for s in llm_data.get("detected_signals", []):
                    if s not in signals:
                        signals.append(s)
                for e in llm_data.get("evidence", []):
                    if e not in evidence:
                        evidence.append(e)
                model_used = self._llm.model_identifier
            except Exception as exc:
                logger.warning("InconsistencyAgent LLM failed", error=type(exc).__name__)
                status = AgentStatus.FALLBACK_USED
                mode = AgentMode.RULES_MODE
                model_used = "rules/heuristic-v1 (llm_fallback)"

        risk_level = self._score_to_risk_level(score)
        action = self._risk_to_action(risk_level)
        explanation = _build_explanation("Inconsistência", score, signals, risk_level)

        ms = int((time.monotonic() - t0) * 1000)
        logger.info("InconsistencyAgent completed", score=score, signals=signals, mode=mode.value, ms=ms)

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
            metadata={"event_sequence": event_types},
        )


def _level_to_score(level: str) -> float:
    return {"LOW": 0.15, "MEDIUM": 0.45, "HIGH": 0.72, "CRITICAL": 0.92}.get(level.upper(), 0.15)


def _score_to_confidence(score: float) -> float:
    return 0.80 if score < 0.20 or score > 0.75 else 0.65


def _build_explanation(label: str, score: float, signals: list[str], level: AgentRiskLevel) -> str:
    sig_str = ", ".join(signals) if signals else "nenhuma"
    return (
        f"Análise de {label}: nível {level.value} (score={score:.2f}). "
        f"Inconsistências: {sig_str}. "
        f"{'Padrões sugerem possível manipulação — confirmação recomendada.' if score >= 0.40 else 'Sem inconsistências relevantes detectadas.'}"
    )
