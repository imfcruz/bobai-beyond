"""
Testes de integridade dos cenários A, B e C.
"""

import pytest
from decimal import Decimal

from app.models.transaction import TransactionStatus, RiskLevel
from app.models.risk_analysis import RecommendedAction, RiskAnalysisStatus
from app.models.contextual_event import EventType
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.event_repo import ContextualEventRepository
from app.repositories.risk_analysis_repo import RiskAnalysisRepository
from app.services.seed_service import TXN_A, TXN_B, TXN_C, ANALYSIS_A, ANALYSIS_B, ANALYSIS_C


# ── Cenário A — Operação Normal ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario_a_transaction_is_released(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_A)
    assert txn is not None
    assert txn.status == TransactionStatus.RELEASED
    assert txn.risk_level == RiskLevel.LOW
    assert txn.risk_score < 0.30


@pytest.mark.asyncio
async def test_scenario_a_beneficiary_is_known(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_A)
    assert txn.is_new_recipient is False
    assert txn.recent_limit_change is False


@pytest.mark.asyncio
async def test_scenario_a_amount_is_decimal(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_A)
    assert isinstance(txn.amount, Decimal)
    assert txn.amount == Decimal("1100.00")


@pytest.mark.asyncio
async def test_scenario_a_analysis_approved(seeded_db):
    db, _ = seeded_db
    repo = RiskAnalysisRepository(db)
    analysis = await repo.get_by_external_id(ANALYSIS_A)
    assert analysis is not None
    assert analysis.recommended_action == RecommendedAction.APPROVE
    assert analysis.status == RiskAnalysisStatus.COMPLETED
    assert analysis.overall_risk_score < 0.30


# ── Cenário B — Operação Incomum ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario_b_transaction_under_verification(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_B)
    assert txn is not None
    assert txn.status == TransactionStatus.UNDER_VERIFICATION
    assert txn.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)


@pytest.mark.asyncio
async def test_scenario_b_new_beneficiary_flag(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_B)
    assert txn.is_new_recipient is True


@pytest.mark.asyncio
async def test_scenario_b_has_three_events(seeded_db):
    db, _ = seeded_db
    txn_repo = TransactionRepository(db)
    ev_repo = ContextualEventRepository(db)
    txn = await txn_repo.get_by_external_id(TXN_B)
    events = await ev_repo.list_by_transaction(txn.id)
    event_types = {e.event_type for e in events}
    assert EventType.LOGIN in event_types
    assert EventType.CADASTRO_BENEFICIARIO in event_types
    assert EventType.INICIO_TRANSFERENCIA in event_types


@pytest.mark.asyncio
async def test_scenario_b_analysis_requests_confirmation(seeded_db):
    db, _ = seeded_db
    repo = RiskAnalysisRepository(db)
    analysis = await repo.get_by_external_id(ANALYSIS_B)
    assert analysis.recommended_action == RecommendedAction.REQUEST_CONFIRMATION
    flags = analysis.flags
    assert "new_beneficiary" in flags


# ── Cenário C — Possível Engenharia Social ────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario_c_escalated_to_human(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_C)
    assert txn is not None
    assert txn.status == TransactionStatus.ESCALATED_TO_HUMAN
    assert txn.risk_level == RiskLevel.CRITICAL
    assert txn.risk_score >= 0.85


@pytest.mark.asyncio
async def test_scenario_c_has_limit_change_flag(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_C)
    assert txn.recent_limit_change is True
    assert txn.is_new_recipient is True


@pytest.mark.asyncio
async def test_scenario_c_has_six_events(seeded_db):
    db, _ = seeded_db
    txn_repo = TransactionRepository(db)
    ev_repo = ContextualEventRepository(db)
    txn = await txn_repo.get_by_external_id(TXN_C)
    events = await ev_repo.list_by_transaction(txn.id)
    assert len(events) == 6
    event_types = {e.event_type for e in events}
    assert EventType.ALTERACAO_LIMITE in event_types
    assert EventType.RESPOSTA_CLIENTE in event_types
    assert EventType.CONFIRMACAO_CONTEXTUAL in event_types


@pytest.mark.asyncio
async def test_scenario_c_analysis_escalates(seeded_db):
    db, _ = seeded_db
    repo = RiskAnalysisRepository(db)
    analysis = await repo.get_by_external_id(ANALYSIS_C)
    assert analysis.recommended_action == RecommendedAction.ESCALATE_TO_HUMAN
    assert analysis.overall_risk_score >= 0.85
    flags = analysis.flags
    assert "social_engineering_pattern" in flags
    assert "third_party_instruction" in flags


@pytest.mark.asyncio
async def test_scenario_c_reasoning_mentions_social_engineering(seeded_db):
    db, _ = seeded_db
    repo = RiskAnalysisRepository(db)
    analysis = await repo.get_by_external_id(ANALYSIS_C)
    assert "engenharia" in analysis.reasoning.lower() or "social" in analysis.reasoning.lower()
