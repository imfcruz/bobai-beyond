"""
Testes de métricas — valida cálculos do MetricsService e do endpoint /metrics/summary.

Cobre:
  - Cálculo correto com dados seed
  - Retorno de "dados insuficientes" com 0 registros
  - Métricas de classificação (TP/FP/TN/FN/Precisão/Recall/F1)
  - Distribuição de risco
  - Distribuição de ações
  - Tempo médio de análise
  - Divergências
  - Quebra por modo (AI_MODE / RULES_MODE)
"""

import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock

from app.services.metrics_service import (
    MetricsService,
    SCENARIO_REFERENCE_LABELS,
    PREDICTED_POSITIVE_STATUSES,
    PREDICTED_NEGATIVE_STATUSES,
    _safe_mean,
)
from app.models.transaction import RiskLevel, Transaction, TransactionStatus
from app.models.risk_analysis import RiskAnalysis


# ── Endpoint smoke tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_endpoint_returns_200(seeded_client):
    """O endpoint deve retornar 200 e as seções obrigatórias."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    required_sections = [
        "volume", "risk_distribution", "rates", "timing",
        "agent_timing", "divergence", "audited_decisions",
        "component_failures", "action_distribution",
        "status_distribution", "classification",
        "mode_breakdown", "risk_score_distribution", "generated_at",
    ]
    for section in required_sections:
        assert section in data, f"Seção ausente: {section}"


@pytest.mark.asyncio
async def test_metrics_volume_with_seeded_data(seeded_client):
    """Com dados seed (3 transações), volume deve refletir os dados reais."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    vol = resp.json()["volume"]
    assert vol["total_transactions"] >= 3
    assert vol["total_analyses"] >= 3
    assert vol["total_audit_logs"] >= 3


@pytest.mark.asyncio
async def test_metrics_risk_distribution(seeded_client):
    """Distribuição de risco deve cobrir todos os níveis."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    rd = resp.json()["risk_distribution"]
    assert "counts" in rd
    assert "percentages" in rd
    assert "total" in rd
    counts = rd["counts"]
    # Dados seed: 1 low (A), 1 medium (B), 1 critical (C)
    assert counts["low"] >= 1
    assert counts["medium"] >= 1
    assert counts["critical"] >= 1
    # Soma dos counts = total
    assert sum(counts.values()) == rd["total"]


@pytest.mark.asyncio
async def test_metrics_action_distribution(seeded_client):
    """Distribuição de ações deve incluir as ações usadas nos cenários seed."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    ad = resp.json()["action_distribution"]
    counts = ad["counts"]
    # Dados seed: approve (A), request_confirmation (B), escalate_to_human (C)
    assert counts["approve"] >= 1
    assert counts["request_confirmation"] >= 1
    assert counts["escalate_to_human"] >= 1
    # Total bate
    assert sum(counts.values()) == ad["total"]


@pytest.mark.asyncio
async def test_metrics_rates(seeded_client):
    """Taxas devem ser frações [0,1] ou None."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    rates = resp.json()["rates"]
    for key in ("confirmation_rate", "human_review_rate"):
        val = rates[key]
        if val is not None:
            assert 0.0 <= val <= 1.0, f"{key} fora do intervalo [0,1]: {val}"


@pytest.mark.asyncio
async def test_metrics_classification_with_scenarios(seeded_client):
    """Classificação deve ser disponível com os 3 cenários seed."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    clf = resp.json()["classification"]
    assert clf["available"] is True
    assert clf["labeled_count"] >= 2
    # TP+FP+TN+FN = total rotulado
    total_labeled = clf["tp"] + clf["fp"] + clf["tn"] + clf["fn"]
    assert total_labeled == clf["labeled_count"]
    # Precision, recall, f1 devem estar no intervalo [0,1]
    for metric_key in ("precision", "recall", "f1_score", "accuracy"):
        val = clf[metric_key]
        if val is not None:
            assert 0.0 <= val <= 1.0, f"{metric_key} fora do intervalo: {val}"


@pytest.mark.asyncio
async def test_metrics_classification_disclaimer_present(seeded_client):
    """A definição da classe positiva e disclaimer devem estar presentes."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    clf = resp.json()["classification"]
    assert "definition" in clf
    defn = clf["definition"]
    assert "positive_class" in defn
    assert "disclaimer" in defn
    assert "Banco do Brasil" in defn["disclaimer"]


@pytest.mark.asyncio
async def test_metrics_risk_score_distribution(seeded_client):
    """Distribuição de scores deve ter 10 buckets de 10%."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    buckets = resp.json()["risk_score_distribution"]
    assert len(buckets) == 10
    labels = [b["range"] for b in buckets]
    assert labels[0] == "0-10%"
    assert labels[9] == "90-100%"
    # Soma das contagens = total de análises
    data = resp.json()
    total_from_buckets = sum(b["count"] for b in buckets)
    assert total_from_buckets == data["volume"]["total_analyses"]


@pytest.mark.asyncio
async def test_metrics_divergence_section(seeded_client):
    """Seção de divergência deve ter campos obrigatórios."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    div = resp.json()["divergence"]
    assert "divergence_count" in div
    assert "completed_analyses" in div
    assert div["divergence_count"] >= 0
    if div["completed_analyses"] > 0:
        assert div["divergence_rate"] is not None


@pytest.mark.asyncio
async def test_metrics_mode_breakdown(seeded_client):
    """Quebra por modo deve somar ao total de análises."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    mb = resp.json()["mode_breakdown"]
    total = mb["AI_MODE"] + mb["RULES_MODE"] + mb["unknown"]
    assert total == mb["total"]
    assert mb["total"] == resp.json()["volume"]["total_analyses"]


@pytest.mark.asyncio
async def test_metrics_agent_timing_structure(seeded_client):
    """Cada agente deve ter estrutura de timing correta."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    timing = resp.json()["agent_timing"]
    expected_agents = [
        "fraud_agent", "inconsistency_agent", "behavioral_agent",
        "risk_agent", "orchestrator_agent", "decision_engine", "security_gateway",
    ]
    for agent in expected_agents:
        assert agent in timing, f"Agente ausente em agent_timing: {agent}"
        entry = timing[agent]
        assert "avg_ms" in entry
        assert "sample_size" in entry
        assert "insufficient_data" in entry


@pytest.mark.asyncio
async def test_metrics_timing_section(seeded_client):
    """Seção de timing deve ter campos obrigatórios."""
    ac, _ = seeded_client
    resp = await ac.get("/api/v1/metrics/summary")
    t = resp.json()["timing"]
    for field in ("avg_ms", "min_ms", "max_ms", "median_ms", "sample_size"):
        assert field in t


# ── Testes unitários — funções puras ──────────────────────────────────────────

def test_safe_mean_empty():
    assert _safe_mean([]) is None


def test_safe_mean_single():
    assert _safe_mean([42.0]) == 42.0


def test_safe_mean_multiple():
    result = _safe_mean([10.0, 20.0, 30.0])
    assert result == 20.0


def test_scenario_reference_labels():
    """Rótulos de referência devem cobrir os 3 cenários."""
    assert "txn-scenario-a" in SCENARIO_REFERENCE_LABELS
    assert "txn-scenario-b" in SCENARIO_REFERENCE_LABELS
    assert "txn-scenario-c" in SCENARIO_REFERENCE_LABELS
    assert SCENARIO_REFERENCE_LABELS["txn-scenario-a"] is False
    assert SCENARIO_REFERENCE_LABELS["txn-scenario-b"] is True
    assert SCENARIO_REFERENCE_LABELS["txn-scenario-c"] is True


def test_predicted_positive_includes_risky_statuses():
    risky = [
        TransactionStatus.ESCALATED_TO_HUMAN,
        TransactionStatus.HUMAN_REVIEW_PENDING,
        TransactionStatus.REJECTED,
        TransactionStatus.UNDER_VERIFICATION,
    ]
    for s in risky:
        assert s in PREDICTED_POSITIVE_STATUSES


def test_predicted_negative_includes_safe_statuses():
    safe = [TransactionStatus.RELEASED, TransactionStatus.APPROVED]
    for s in safe:
        assert s in PREDICTED_NEGATIVE_STATUSES


def test_predicted_positive_negative_disjoint():
    overlap = PREDICTED_POSITIVE_STATUSES & PREDICTED_NEGATIVE_STATUSES
    assert len(overlap) == 0


# ── Testes unitários — MetricsService com mocks ───────────────────────────────

@pytest.mark.asyncio
async def test_classification_formula_tp_precision(db_session):
    """TP=2, FP=0, FN=0, TN=0 → Precision = 1.0, Recall = 1.0"""
    t1 = MagicMock(spec=Transaction)
    t1.external_id = "txn-scenario-b"
    t1.status = TransactionStatus.UNDER_VERIFICATION
    t1.risk_level = RiskLevel.MEDIUM

    t2 = MagicMock(spec=Transaction)
    t2.external_id = "txn-scenario-c"
    t2.status = TransactionStatus.ESCALATED_TO_HUMAN
    t2.risk_level = RiskLevel.CRITICAL

    svc = MetricsService(db_session)
    result = svc._compute_classification([t1, t2])

    assert result["available"] is True
    assert result["tp"] == 2
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1_score"] == 1.0


@pytest.mark.asyncio
async def test_classification_formula_fn(db_session):
    """TN=1, FN=1, TP=1, FP=0 → Precision=1.0, Recall=0.5"""
    t_a = MagicMock(spec=Transaction)
    t_a.external_id = "txn-scenario-a"
    t_a.status = TransactionStatus.RELEASED   # TN
    t_a.risk_level = RiskLevel.LOW

    t_b = MagicMock(spec=Transaction)
    t_b.external_id = "txn-scenario-b"
    t_b.status = TransactionStatus.RELEASED   # FN: real é positivo mas previu negativo
    t_b.risk_level = RiskLevel.MEDIUM

    t_c = MagicMock(spec=Transaction)
    t_c.external_id = "txn-scenario-c"
    t_c.status = TransactionStatus.ESCALATED_TO_HUMAN  # TP
    t_c.risk_level = RiskLevel.CRITICAL

    svc = MetricsService(db_session)
    result = svc._compute_classification([t_a, t_b, t_c])

    assert result["tp"] == 1
    assert result["fp"] == 0
    assert result["tn"] == 1
    assert result["fn"] == 1
    assert result["precision"] == 1.0
    assert result["recall"] == 0.5
    assert result["f1_score"] == pytest.approx(2 / 3, rel=1e-3)


@pytest.mark.asyncio
async def test_classification_insufficient_when_no_scenarios(db_session):
    """Com transações não rotuladas, classificação deve retornar available=False."""
    t = MagicMock(spec=Transaction)
    t.external_id = "txn-some-other-id"
    t.status = TransactionStatus.RELEASED
    t.risk_level = RiskLevel.LOW

    svc = MetricsService(db_session)
    result = svc._compute_classification([t])
    assert result["available"] is False


@pytest.mark.asyncio
async def test_risk_distribution_counts_sum(db_session):
    """Soma das contagens de risco deve igualar o total."""
    txns = []
    for level in [RiskLevel.LOW, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.CRITICAL]:
        t = MagicMock(spec=Transaction)
        t.risk_level = level
        txns.append(t)

    svc = MetricsService(db_session)
    dist = svc._risk_distribution(txns)
    assert sum(dist["counts"].values()) == 4
    assert dist["counts"]["low"] == 2
    assert dist["counts"]["medium"] == 1
    assert dist["counts"]["critical"] == 1


@pytest.mark.asyncio
async def test_risk_score_buckets_count(db_session):
    """Deve retornar exatamente 10 buckets que somam ao total."""
    analyses = []
    for score in [0.05, 0.15, 0.55, 0.92]:
        a = MagicMock(spec=RiskAnalysis)
        a.overall_risk_score = score
        analyses.append(a)

    svc = MetricsService(db_session)
    buckets = svc._risk_score_buckets(analyses)
    assert len(buckets) == 10
    total = sum(b["count"] for b in buckets)
    assert total == 4


@pytest.mark.asyncio
async def test_compute_failures_empty(db_session):
    """Com zero falhas, deve retornar dict vazio."""
    svc = MetricsService(db_session)
    from app.models.audit_log import AuditLog
    log = MagicMock(spec=AuditLog)
    log.result = "released"  # não é falha
    log.component = "decision_engine"
    result = svc._compute_failures([log])
    assert result == {}


@pytest.mark.asyncio
async def test_compute_failures_counts(db_session):
    """Deve contar corretamente falhas por componente."""
    from app.models.audit_log import AuditLog
    svc = MetricsService(db_session)

    logs = []
    for result_val, comp in [("error", "fraud_agent"), ("failed", "fraud_agent"), ("released", "decision_engine")]:
        log = MagicMock(spec=AuditLog)
        log.result = result_val
        log.component = comp
        logs.append(log)

    failures = svc._compute_failures(logs)
    assert failures.get("fraud_agent") == 2
    assert "decision_engine" not in failures
