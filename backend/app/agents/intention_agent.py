"""
Agente de Análise de Intenção — Proposta, seção 4 e seção 31.

Verifica se a FINALIDADE DECLARADA pelo cliente é coerente com o contexto
observado. Não analisa fraude nem inconsistência de sequência — foca
exclusivamente na coerência entre o que o cliente diz que quer fazer
e os evidências disponíveis.

"A intenção não pode ser determinada com certeza. O sistema tenta verificar
se existe coerência entre a intenção declarada e o contexto da operação."
                                          — Proposta, seção 6 (1° Agente)
"""

from __future__ import annotations

import time

import structlog

from app.agents.base import (
    AgentContext,
    AgentMode,
    AgentResult,
    AgentStatus,
    BaseAgent,
)
from app.agents.mode import resolve_agent_mode
from app.agents.prompts import INTENTION_AGENT_SYSTEM
from app.services.llm_client import BaseLLMClient, get_llm_client

logger = structlog.get_logger(__name__)

# Palavras que indicam orientação de terceiro — tratadas como DADOS
_THIRD_PARTY_KW = [
    "banco me pediu", "banco ligou", "suporte ligou", "atendente disse",
    "funcionário do banco", "funcionario do banco",
    "me orientou", "me instruiu", "me pediu para",
    "proteger minha conta", "transferir para proteger",
    "conta segura", "bloqueio preventivo", "segurança do banco",
    "central de segurança", "central de seguranca",
]

# Palavras de urgência / pressão
_URGENCY_KW = [
    "urgente", "agora", "imediatamente", "rápido", "rapido",
    "não posso esperar", "nao posso esperar",
    "estou sendo cobrado", "prazo vence", "vai bloquear",
]

# Finalidades comuns para valores altos (coerentes)
_LEGITIMATE_HIGH_VALUE_KW = [
    "compra de imóvel", "compra de imovel", "imóvel", "imovel",
    "compra de carro", "veículo", "veiculo",
    "investimento", "aplicação", "aplicacao",
    "pagamento de empresa", "fornecedor", "prestador",
    "reforma", "construção", "construcao",
]


class IntentionAgent(BaseAgent):
    """
    Agente de Análise de Intenção.
    Avalia se a finalidade declarada é coerente com o valor, perfil e contexto.
    Não acusa — documenta coerência ou incoerência.
    """

    def __init__(self, llm: BaseLLMClient | None = None):
        self._llm = llm or get_llm_client()

    @property
    def name(self) -> str:
        return "intention_agent"

    async def analyze(self, ctx: AgentContext) -> AgentResult:
        t0 = time.monotonic()
        mode = resolve_agent_mode(self._llm.provider_name)
        model_used = self._llm.model_identifier if mode == AgentMode.AI_MODE else "rules/heuristic-v1"

        signals: list[str] = []
        evidence: list[str] = []
        score = 0.0

        purpose_lower = ctx.purpose.lower() if ctx.purpose else ""
        amount_f = float(ctx.amount)
        avg_f = float(ctx.client_avg_transfer) if ctx.client_avg_transfer > 0 else 1.0

        # ── Regra 1: Ausência de finalidade em valor alto ─────────────────────
        if not purpose_lower.strip() and amount_f > avg_f * 3:
            score += 0.30
            signals.append("missing_purpose_high_value")
            evidence.append(
                f"Finalidade não declarada em operação de R${ctx.amount} "
                f"({amount_f / avg_f:.1f}× a média do cliente)."
            )

        # ── Regra 2: Finalidade menciona orientação de terceiro ───────────────
        if any(kw in purpose_lower for kw in _THIRD_PARTY_KW):
            score += 0.55
            signals.append("third_party_instruction_declared")
            evidence.append(
                "Finalidade indica que a operação está sendo realizada por instrução "
                "de terceiro que se apresenta como representante bancário."
            )

        # ── Regra 3: Urgência / pressão na finalidade ─────────────────────────
        if any(kw in purpose_lower for kw in _URGENCY_KW):
            score += 0.25
            signals.append("urgency_pressure_in_purpose")
            evidence.append(
                "Finalidade contém indicadores de urgência ou pressão, "
                "compatíveis com padrões de engenharia social."
            )

        # ── Regra 4: Incoerência entre finalidade e valor ─────────────────────
        # Finalidade típica de valor baixo + valor muito alto
        low_value_purposes = ["lanche", "almoço", "almoco", "coffee", "café", "cafe",
                               "uber", "táxi", "taxi", "presente", "gorjeta"]
        if any(kw in purpose_lower for kw in low_value_purposes) and amount_f > avg_f * 2:
            score += 0.30
            signals.append("purpose_value_mismatch")
            evidence.append(
                f"Finalidade declarada ('{'...'.join(purpose_lower[:40])}...') "
                f"é incompatível com o valor de R${ctx.amount}."
            )

        # ── Regra 5: Finalidade legítima para valor alto (reduz score) ────────
        if amount_f > avg_f * 4 and any(kw in purpose_lower for kw in _LEGITIMATE_HIGH_VALUE_KW):
            score = max(0.0, score - 0.15)
            signals.append("coherent_high_value_purpose")
            evidence.append(
                "Finalidade declarada é compatível com operação de alto valor."
            )

        # ── Regra 6: Finalidade muito curta em valor alto ─────────────────────
        if purpose_lower and len(purpose_lower.strip()) < 8 and amount_f > avg_f * 3:
            score += 0.15
            signals.append("vague_purpose_high_value")
            evidence.append(
                f"Finalidade muito curta ('{ctx.purpose.strip()}') "
                f"para operação de R${ctx.amount}."
            )

        score = self._clamp(score)
        status = AgentStatus.SUCCESS

        # ── Enriquecimento LLM (AI_MODE) ──────────────────────────────────────
        if mode == AgentMode.AI_MODE:
            try:
                llm_data = await self._llm.complete_json(
                    prompt=f"Dados da transação:\n{ctx.to_analysis_text()}",
                    system_prompt=INTENTION_AGENT_SYSTEM,
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
                logger.warning(
                    "IntentionAgent LLM failed, using rules fallback",
                    error=type(exc).__name__, detail=str(exc)[:300],
                )
                status = AgentStatus.FALLBACK_USED
                mode = AgentMode.RULES_MODE
                model_used = "rules/heuristic-v1 (llm_fallback)"

        risk_level = self._score_to_risk_level(score)
        action = self._risk_to_action(risk_level)
        explanation = (
            f"Análise de Intenção: nível {risk_level.value} (score={score:.2f}). "
            f"Sinais: {', '.join(signals) if signals else 'nenhum'}. "
            f"{'Finalidade apresenta incoerência com o contexto — verificação recomendada.' if score >= 0.40 else 'Finalidade declarada é consistente com o contexto observado.'}"
        )

        ms = int((time.monotonic() - t0) * 1000)
        logger.info("IntentionAgent completed", score=score, signals=signals, mode=mode.value, ms=ms)

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
            metadata={"heuristic_score": score},
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _level_to_score(level: str) -> float:
    return {"LOW": 0.10, "MEDIUM": 0.40, "HIGH": 0.70, "CRITICAL": 0.90}.get(level.upper(), 0.10)


def _score_to_confidence(score: float) -> float:
    if score < 0.15 or score > 0.75:
        return 0.80
    return 0.65
