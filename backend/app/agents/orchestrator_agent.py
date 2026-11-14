"""
Agente Orquestrador de Contexto e Intenção.

Responsável por:
1. Receber a solicitação de análise.
2. Construir AgentContext com dados históricos e eventos cronológicos.
3. Interpretar a finalidade declarada.
4. Selecionar e coordenar os agentes necessários em paralelo (asyncio.gather).
5. Invocar o Agente de Risco com os resultados anteriores.
6. Retornar resultado consolidado e resultados individuais.

Não realiza movimentações financeiras.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal

import structlog

from app.agents.base import (
    AgentContext,
    AgentResult,
    BaseAgent,
)
from app.agents.behavioral_agent import BehavioralAgent
from app.agents.fraud_agent import FraudAgent
from app.agents.inconsistency_agent import InconsistencyAgent
from app.agents.intention_agent import IntentionAgent
from app.agents.mode import resolve_agent_mode
from app.agents.risk_agent import RiskAgent
from app.services.llm_client import BaseLLMClient, get_llm_client

logger = structlog.get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Orquestrador multiagente.
    Coordena a execução paralela dos especialistas necessários e passa os
    resultados ao Agente de Risco para consolidação.
    """

    def __init__(self, llm: BaseLLMClient | None = None):
        _llm = llm or get_llm_client()
        self._fraud        = FraudAgent(_llm)
        self._inconsistency = InconsistencyAgent(_llm)
        self._behavioral   = BehavioralAgent(_llm)
        self._intention    = IntentionAgent(_llm)
        self._risk         = RiskAgent(_llm)
        self._llm          = _llm

    @property
    def name(self) -> str:
        return "orchestrator_agent"

    async def analyze(self, ctx: AgentContext) -> AgentResult:
        """Ponto de entrada simples — retorna apenas o resultado final."""
        final, _ = await self.run_full_pipeline(ctx)
        return final

    async def run_full_pipeline(
        self, ctx: AgentContext
    ) -> tuple[AgentResult, dict[str, AgentResult]]:
        """
        Executa o pipeline completo e retorna o resultado final + individuais.
        Usado pelo BankService para persistir cada resultado separadamente.
        """
        t0 = time.monotonic()
        mode = resolve_agent_mode(self._llm.provider_name)

        logger.info(
            "Orchestrator pipeline starting",
            txn=ctx.transaction_external_id,
            amount=str(ctx.amount),
            mode=mode.value,
        )

        specialists = self._select_specialists(ctx)
        selected_names = list(specialists)
        logger.info(
            "Orchestrator specialists selected",
            txn=ctx.transaction_external_id,
            agents=selected_names,
        )

        specialist_results = await asyncio.gather(
            *(agent.analyze(ctx) for agent in specialists.values())
        )
        sub_results = list(specialist_results)

        # ── Agente de Risco consolida (sequencial — depende dos anteriores) ────
        risk_result = await self._risk.analyze(ctx, sub_results=sub_results)
        risk_result.metadata["selected_agents"] = selected_names
        risk_result.metadata["selection_reason"] = self._selection_reason(ctx)

        ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Orchestrator pipeline complete",
            final_score=risk_result.risk_score,
            final_level=risk_result.risk_level,
            ms=ms,
        )

        individual = dict(zip(selected_names, specialist_results, strict=True))
        individual["risk_agent"] = risk_result
        return risk_result, individual

    def _select_specialists(self, ctx: AgentContext) -> dict[str, BaseAgent]:
        """Monta o plano mínimo de análise conforme os sinais disponíveis.

        Fraude permanece stand-alone e sempre participa. Comportamental fornece
        o baseline da operação. Intenção e Inconsistência entram quando o
        contexto pede uma segunda opinião mais profunda.
        """
        selected: dict[str, BaseAgent] = {
            "fraud_agent": self._fraud,
            "behavioral_agent": self._behavioral,
        }
        if self._requires_contextual_depth(ctx):
            selected["intention_agent"] = self._intention
            selected["inconsistency_agent"] = self._inconsistency
        return selected

    @staticmethod
    def _requires_contextual_depth(ctx: AgentContext) -> bool:
        purpose = (ctx.purpose or "").casefold()
        sensitive_terms = (
            "banco", "funcionário", "proteger", "segurança", "terceiro",
            "ligação", "urgente", "orientou", "mandou", "instrução",
        )
        amount_is_unusual = (
            ctx.amount > ctx.client_max_transfer
            or ctx.amount >= ctx.client_avg_transfer * Decimal("2")
        )
        sequence_is_unusual = len(ctx.recent_events) >= 2
        return any((
            ctx.is_new_recipient,
            ctx.recent_limit_change,
            not ctx.device_recognized,
            amount_is_unusual,
            sequence_is_unusual,
            any(term in purpose for term in sensitive_terms),
        ))

    @classmethod
    def _selection_reason(cls, ctx: AgentContext) -> str:
        if cls._requires_contextual_depth(ctx):
            return "Contexto incomum: análise completa e segunda opinião ativadas."
        return "Contexto habitual: fraude e comportamento executados como triagem mínima."


def build_context_from_domain(
    *,
    transaction_ext_id: str,
    client_ext_id: str,
    correlation_id: str,
    analysis_id: str,
    amount: Decimal,
    purpose: str,
    is_new_recipient: bool,
    recent_limit_change: bool,
    device_recognized: bool,
    is_known_beneficiary: bool,
    avg_transfer: Decimal,
    max_transfer: Decimal,
    min_transfer: Decimal,
    avg_monthly_tx: int,
    account_age_days: int,
    risk_profile: str,
    beneficiary_transfer_count: int,
    beneficiary_total: Decimal,
    recent_events: list[dict],
    typical_hours: str | None,
    typical_channels: str | None,
    operation_type: str = "pix",
    funding_source: str = "debit",
) -> AgentContext:
    """
    Monta um AgentContext a partir dos dados de domínio.
    Centraliza o mapeamento domínio → contexto do agente.
    """
    now_hour = datetime.now(UTC).hour
    return AgentContext(
        transaction_external_id=transaction_ext_id,
        client_external_id=client_ext_id,
        correlation_id=correlation_id,
        analysis_id=analysis_id,
        amount=amount,
        purpose=purpose,
        operation_type=operation_type,
        funding_source=funding_source,
        is_new_recipient=is_new_recipient,
        recent_limit_change=recent_limit_change,
        device_recognized=device_recognized,
        is_known_beneficiary=is_known_beneficiary,
        client_avg_transfer=avg_transfer,
        client_max_transfer=max_transfer,
        client_min_transfer=min_transfer,
        client_avg_monthly_tx=avg_monthly_tx,
        client_account_age_days=account_age_days,
        client_risk_profile=risk_profile,
        beneficiary_transfer_count=beneficiary_transfer_count,
        beneficiary_total_transferred=beneficiary_total,
        recent_events=recent_events,
        typical_hours=typical_hours,
        typical_channels=typical_channels,
        operation_hour=now_hour,
    )
