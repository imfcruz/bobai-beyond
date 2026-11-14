"""
Testes dos agentes de análise de risco.

Cobrem:
- FraudAgent heurísticas
- InconsistencyAgent padrões
- BehavioralAgent desvios
- RiskAgent consolidação ponderada
- OrchestratorAgent pipeline completo
- DecisionEngine mapeamento score → ação
- SecurityGateway autorização
"""

import asyncio
from decimal import Decimal

import pytest

from app.agents.base import (
    AgentContext,
    AgentMode,
    AgentRecommendedAction,
    AgentResult,
    AgentRiskLevel,
    AgentStatus,
)
from app.agents.behavioral_agent import BehavioralAgent
from app.agents.fraud_agent import FraudAgent
from app.agents.inconsistency_agent import InconsistencyAgent
from app.agents.orchestrator_agent import OrchestratorAgent, build_context_from_domain
from app.agents.risk_agent import RiskAgent
from app.services.decision_engine import Decision, make_decision
from app.services.security_gateway import SecurityGateway
from app.models.risk_analysis import RecommendedAction
from app.models.transaction import RiskLevel, TransactionStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _low_risk_ctx() -> AgentContext:
    """Contexto de baixo risco — operação normal."""
    return AgentContext(
        transaction_external_id="txn-test-low",
        client_external_id="client-test",
        correlation_id="corr-001",
        analysis_id="analysis-test-low",
        amount=Decimal("500.00"),
        purpose="Pagamento de serviço",
        is_new_recipient=False,
        recent_limit_change=False,
        device_recognized=True,
        is_known_beneficiary=True,
        client_avg_transfer=Decimal("800.00"),
        client_max_transfer=Decimal("3000.00"),
        client_min_transfer=Decimal("100.00"),
        client_avg_monthly_tx=8,
        client_account_age_days=730,
        client_risk_profile="low",
        beneficiary_transfer_count=5,
        beneficiary_total_transferred=Decimal("4000.00"),
        recent_events=[],
        typical_hours='["08:00-12:00", "14:00-18:00"]',
        typical_channels="mobile",
        operation_hour=10,
    )


def _high_risk_ctx() -> AgentContext:
    """Contexto de alto risco — indicadores de engenharia social."""
    return AgentContext(
        transaction_external_id="txn-test-high",
        client_external_id="client-test",
        correlation_id="corr-002",
        analysis_id="analysis-test-high",
        amount=Decimal("45000.00"),
        purpose="Funcionário do banco me orientou a transferir para conta segura",
        is_new_recipient=True,
        recent_limit_change=True,
        device_recognized=False,
        is_known_beneficiary=False,
        client_avg_transfer=Decimal("1000.00"),
        client_max_transfer=Decimal("5000.00"),
        client_min_transfer=Decimal("200.00"),
        client_avg_monthly_tx=5,
        client_account_age_days=365,
        client_risk_profile="low",
        beneficiary_transfer_count=0,
        beneficiary_total_transferred=Decimal("0.00"),
        recent_events=[
            {"event_type": "LOGIN", "metadata": None},
            {"event_type": "LOGIN", "metadata": None},
            {"event_type": "ALTERACAO_LIMITE", "metadata": None},
            {"event_type": "CADASTRO_BENEFICIARIO", "metadata": None},
            {"event_type": "INICIO_TRANSFERENCIA", "metadata": None},
        ],
        typical_hours='["09:00-12:00"]',
        typical_channels="web",
        operation_hour=23,
    )


def _make_agent_result(
    agent_name: str = "test_agent",
    risk_score: float = 0.10,
    risk_level: AgentRiskLevel = AgentRiskLevel.LOW,
    flags: list[str] | None = None,
    reasoning: str = "Teste",
    confidence: float = 0.8,
    metadata: dict | None = None,
    analysis_id: str = "analysis-test",
) -> AgentResult:
    """Helper para construir AgentResult com o novo contrato Pydantic."""
    return AgentResult(
        agent_name=agent_name,
        analysis_id=analysis_id,
        risk_level=risk_level,
        confidence=confidence,
        detected_signals=flags or [],
        evidence=["Análise de teste"],
        explanation=reasoning,
        recommended_action=AgentRecommendedAction.APPROVE,
        model_used="rules/mock-v1",
        execution_time_ms=1,
        status=AgentStatus.SUCCESS,
        mode=AgentMode.RULES_MODE,
        # Campos legados
        risk_score=risk_score,
        flags=flags or [],
        reasoning=reasoning,
        metadata=metadata or {},
    )


# ── FraudAgent ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fraud_agent_low_risk_no_flags():
    agent = FraudAgent()
    result = await agent.analyze(_low_risk_ctx())
    assert result.agent_name == "fraud_agent"
    assert result.risk_score < 0.30
    assert isinstance(result.flags, list)


@pytest.mark.asyncio
async def test_fraud_agent_high_risk_detects_social_engineering():
    agent = FraudAgent()
    result = await agent.analyze(_high_risk_ctx())
    assert result.risk_score > 0.50
    assert "social_engineering_keyword" in result.flags


@pytest.mark.asyncio
async def test_fraud_agent_new_beneficiary_adds_score():
    ctx = _low_risk_ctx()
    ctx.is_new_recipient = True
    agent = FraudAgent()
    result_with = await agent.analyze(ctx)

    ctx2 = _low_risk_ctx()
    result_without = await agent.analyze(ctx2)

    assert result_with.risk_score > result_without.risk_score
    assert "new_beneficiary" in result_with.flags


@pytest.mark.asyncio
async def test_fraud_agent_amount_far_above_avg():
    ctx = _low_risk_ctx()
    ctx.amount = Decimal("20000.00")  # 25x average of 800
    agent = FraudAgent()
    result = await agent.analyze(ctx)
    assert "amount_far_above_avg" in result.flags


@pytest.mark.asyncio
async def test_fraud_agent_score_clamped_to_one():
    agent = FraudAgent()
    result = await agent.analyze(_high_risk_ctx())
    assert 0.0 <= result.risk_score <= 1.0


# ── InconsistencyAgent ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inconsistency_agent_low_risk():
    agent = InconsistencyAgent()
    result = await agent.analyze(_low_risk_ctx())
    assert result.agent_name == "inconsistency_agent"
    assert result.risk_score < 0.20


@pytest.mark.asyncio
async def test_inconsistency_agent_detects_full_sequence():
    agent = InconsistencyAgent()
    result = await agent.analyze(_high_risk_ctx())
    assert result.risk_score > 0.50
    assert "limit_changed_before_transfer" in result.flags
    assert "full_social_engineering_sequence" in result.flags


@pytest.mark.asyncio
async def test_inconsistency_agent_detects_double_login():
    ctx = _low_risk_ctx()
    ctx.recent_events = [
        {"event_type": "LOGIN", "metadata": None},
        {"event_type": "LOGIN", "metadata": None},
    ]
    agent = InconsistencyAgent()
    result = await agent.analyze(ctx)
    assert "double_login_detected" in result.flags


@pytest.mark.asyncio
async def test_inconsistency_agent_new_beneficiary_same_session():
    ctx = _low_risk_ctx()
    ctx.is_new_recipient = True
    ctx.recent_events = [{"event_type": "CADASTRO_BENEFICIARIO", "metadata": None}]
    agent = InconsistencyAgent()
    result = await agent.analyze(ctx)
    assert "new_beneficiary_registered_same_session" in result.flags


# ── BehavioralAgent ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_behavioral_agent_low_risk():
    agent = BehavioralAgent()
    result = await agent.analyze(_low_risk_ctx())
    assert result.agent_name == "behavioral_agent"
    assert result.risk_score < 0.30


@pytest.mark.asyncio
async def test_behavioral_agent_atypical_hour():
    ctx = _low_risk_ctx()
    ctx.operation_hour = 3  # fora das faixas 08-12, 14-18
    agent = BehavioralAgent()
    result = await agent.analyze(ctx)
    assert "atypical_operation_hour" in result.flags


@pytest.mark.asyncio
async def test_behavioral_agent_amount_above_max():
    ctx = _low_risk_ctx()
    ctx.amount = Decimal("10000.00")  # > max de 3000
    agent = BehavioralAgent()
    result = await agent.analyze(ctx)
    assert any("above_max" in f for f in result.flags)


@pytest.mark.asyncio
async def test_behavioral_agent_never_used_beneficiary():
    ctx = _low_risk_ctx()
    ctx.beneficiary_transfer_count = 0
    agent = BehavioralAgent()
    result = await agent.analyze(ctx)
    assert "beneficiary_never_used" in result.flags


# ── RiskAgent ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_agent_without_sub_results():
    agent = RiskAgent()
    result = await agent.analyze(_low_risk_ctx(), sub_results=None)
    assert result.agent_name == "risk_agent"
    assert 0.0 <= result.risk_score <= 1.0


@pytest.mark.asyncio
async def test_risk_agent_consolidates_sub_results():
    agent = RiskAgent()
    sub = [
        _make_agent_result("fraud_agent", risk_score=0.7, flags=["f1"], analysis_id="analysis-test"),
        _make_agent_result("inconsistency_agent", risk_score=0.5, flags=["f2"], analysis_id="analysis-test"),
        _make_agent_result("behavioral_agent", risk_score=0.3, flags=["f3"], analysis_id="analysis-test"),
    ]
    result = await agent.analyze(_low_risk_ctx(), sub_results=sub)
    # Score consolidado ponderado deve ser entre os extremos
    assert 0.3 < result.risk_score < 0.8
    # Todos os flags devem estar presentes
    assert "f1" in result.flags
    assert "f2" in result.flags
    assert "f3" in result.flags


@pytest.mark.asyncio
async def test_risk_agent_hard_block_on_regulatory_limit():
    ctx = _low_risk_ctx()
    ctx.amount = Decimal("60000.00")  # > 50000 limite regulatório
    agent = RiskAgent()
    result = await agent.analyze(ctx)
    assert result.risk_score == 1.0
    assert "regulatory_limit_exceeded" in result.flags
    assert result.metadata["hard_block"] is True


# ── OrchestratorAgent ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_orchestrator_selects_minimum_agents_for_normal_context():
    orchestrator = OrchestratorAgent()
    final, individual = await orchestrator.run_full_pipeline(_low_risk_ctx())

    assert "fraud_agent" in individual
    assert "behavioral_agent" in individual
    assert "risk_agent" in individual
    assert "inconsistency_agent" not in individual
    assert 0.0 <= final.risk_score <= 1.0


@pytest.mark.asyncio
async def test_orchestrator_high_risk_gives_elevated_score():
    orchestrator = OrchestratorAgent()
    final, _ = await orchestrator.run_full_pipeline(_high_risk_ctx())
    assert final.risk_score > 0.50


@pytest.mark.asyncio
async def test_orchestrator_low_risk_gives_low_score():
    orchestrator = OrchestratorAgent()
    final, _ = await orchestrator.run_full_pipeline(_low_risk_ctx())
    assert final.risk_score < 0.40


@pytest.mark.asyncio
async def test_build_context_from_domain():
    ctx = build_context_from_domain(
        transaction_ext_id="txn-x",
        client_ext_id="client-x",
        correlation_id="corr-x",
        analysis_id="analysis-x",
        amount=Decimal("1000.00"),
        purpose="Teste",
        is_new_recipient=False,
        recent_limit_change=False,
        device_recognized=True,
        is_known_beneficiary=True,
        avg_transfer=Decimal("500.00"),
        max_transfer=Decimal("2000.00"),
        min_transfer=Decimal("100.00"),
        avg_monthly_tx=6,
        account_age_days=500,
        risk_profile="low",
        beneficiary_transfer_count=3,
        beneficiary_total=Decimal("1500.00"),
        recent_events=[],
        typical_hours=None,
        typical_channels=None,
    )
    assert ctx.transaction_external_id == "txn-x"
    assert ctx.analysis_id == "analysis-x"
    assert ctx.amount == Decimal("1000.00")
    assert isinstance(ctx.operation_hour, int)


# ── AgentResult serialização ───────────────────────────────────────────────────

def test_agent_result_to_json_roundtrip():
    original = _make_agent_result(
        agent_name="test_agent",
        risk_score=0.42,
        flags=["flag1", "flag2"],
        reasoning="Test reasoning",
        confidence=0.9,
        metadata={"key": "value"},
    )
    json_str = original.to_json()
    restored = AgentResult.from_json(json_str)
    assert restored.agent_name == original.agent_name
    assert restored.risk_score == original.risk_score
    assert restored.flags == original.flags
    assert restored.analysis_id == original.analysis_id


def test_agent_result_new_fields_present():
    """Verifica que todos os campos do novo contrato estão presentes."""
    result = _make_agent_result()
    assert hasattr(result, "risk_level")
    assert hasattr(result, "confidence")
    assert hasattr(result, "detected_signals")
    assert hasattr(result, "evidence")
    assert hasattr(result, "explanation")
    assert hasattr(result, "recommended_action")
    assert hasattr(result, "model_used")
    assert hasattr(result, "execution_time_ms")
    assert hasattr(result, "status")
    assert hasattr(result, "mode")


def test_agent_result_legacy_fields_preserved():
    """Campos legados ainda devem existir para compatibilidade."""
    result = _make_agent_result(risk_score=0.5, flags=["f1"], reasoning="r1")
    assert result.risk_score == 0.5
    assert "f1" in result.flags
    assert result.reasoning == "r1"


def test_agent_result_mode_is_enum_value():
    """Mode deve ser string serializável (use_enum_values=True)."""
    result = _make_agent_result()
    assert result.mode == "RULES_MODE"


# ── DecisionEngine ────────────────────────────────────────────────────────────

def test_decision_engine_low_score_approves():
    result = _make_agent_result(
        agent_name="risk_agent",
        risk_score=0.10,
        flags=[],
        reasoning="Baixo risco",
        metadata={"hard_block": False},
    )
    decision = make_decision(result)
    assert decision.recommended_action == RecommendedAction.APPROVE
    assert decision.transaction_status == TransactionStatus.RELEASED
    assert decision.risk_level == RiskLevel.LOW


def test_decision_engine_medium_score_requests_confirmation():
    result = _make_agent_result(
        agent_name="risk_agent",
        risk_score=0.45,
        flags=["new_beneficiary"],
        reasoning="Risco médio",
        metadata={"hard_block": False},
    )
    decision = make_decision(result)
    assert decision.recommended_action == RecommendedAction.REQUEST_CONFIRMATION
    assert decision.transaction_status == TransactionStatus.AWAITING_CONFIRMATION


def test_decision_engine_high_score_escalates():
    result = _make_agent_result(
        agent_name="risk_agent",
        risk_score=0.90,
        risk_level=AgentRiskLevel.CRITICAL,
        flags=["social_engineering_keyword"],
        reasoning="Risco crítico",
        metadata={"hard_block": False},
    )
    decision = make_decision(result)
    assert decision.recommended_action == RecommendedAction.ESCALATE_TO_HUMAN
    assert decision.transaction_status == TransactionStatus.HUMAN_REVIEW_PENDING


def test_decision_engine_hard_block_rejects():
    result = _make_agent_result(
        agent_name="risk_agent",
        risk_score=0.95,
        risk_level=AgentRiskLevel.CRITICAL,
        flags=["regulatory_limit_exceeded"],
        reasoning="Limite excedido",
        metadata={"hard_block": True},
    )
    decision = make_decision(result)
    assert decision.recommended_action == RecommendedAction.BLOCK
    assert decision.transaction_status == TransactionStatus.REJECTED


# ── SecurityGateway ───────────────────────────────────────────────────────────

def test_gateway_approve_is_authorized():
    decision = Decision(
        risk_level=RiskLevel.LOW,
        recommended_action=RecommendedAction.APPROVE,
        transaction_status=TransactionStatus.RELEASED,
        risk_score=0.10,
        reasoning="OK",
        flags=[],
    )
    gw = SecurityGateway()
    response = gw.evaluate(decision)
    assert response.authorized is True
    assert response.requires_confirmation is False
    assert response.requires_human_review is False
    assert response.final_status == TransactionStatus.RELEASED


def test_gateway_block_is_not_authorized():
    decision = Decision(
        risk_level=RiskLevel.CRITICAL,
        recommended_action=RecommendedAction.BLOCK,
        transaction_status=TransactionStatus.REJECTED,
        risk_score=1.0,
        reasoning="BLOQUEADO",
        flags=["hard_block"],
    )
    gw = SecurityGateway()
    response = gw.evaluate(decision)
    assert response.authorized is False
    assert response.final_status == TransactionStatus.REJECTED


def test_gateway_escalate_requires_human():
    decision = Decision(
        risk_level=RiskLevel.CRITICAL,
        recommended_action=RecommendedAction.ESCALATE_TO_HUMAN,
        transaction_status=TransactionStatus.ESCALATED_TO_HUMAN,
        risk_score=0.90,
        reasoning="Escalar",
        flags=["social_engineering_keyword"],
    )
    gw = SecurityGateway()
    response = gw.evaluate(decision)
    assert response.authorized is True
    assert response.requires_human_review is True


def test_gateway_confirmation_requires_confirmation():
    decision = Decision(
        risk_level=RiskLevel.MEDIUM,
        recommended_action=RecommendedAction.REQUEST_CONFIRMATION,
        transaction_status=TransactionStatus.UNDER_VERIFICATION,
        risk_score=0.45,
        reasoning="Confirmar",
        flags=["new_beneficiary"],
    )
    gw = SecurityGateway()
    response = gw.evaluate(decision)
    assert response.authorized is True
    assert response.requires_confirmation is True


def test_gateway_to_dict():
    decision = Decision(
        risk_level=RiskLevel.LOW,
        recommended_action=RecommendedAction.APPROVE,
        transaction_status=TransactionStatus.RELEASED,
        risk_score=0.05,
        reasoning="OK",
        flags=[],
    )
    gw = SecurityGateway()
    response = gw.evaluate(decision)
    d = response.to_dict()
    assert "authorized" in d
    assert "final_status" in d
    assert "gateway_reasoning" in d
    assert isinstance(d["flags"], list)
