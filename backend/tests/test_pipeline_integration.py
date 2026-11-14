"""
Testes de integração do pipeline multiagente via HTTP.

Verificam o fluxo completo end-to-end através dos endpoints FastAPI:
- POST /transactions/ → response com gateway, analysis por agente
- Cenário de baixo risco → released
- Cenário de engenharia social → escalated_to_human
- Cenário com valor acima do limite simulado
- Consistência dos campos da GatewayResponse no response HTTP
"""

import pytest

from app.services.seed_service import (
    CLIENT_A_EXT,
    CLIENT_B_EXT,
    CLIENT_C_EXT,
    BEN_KNOWN_A1,
    BEN_NEW_B1,
    BEN_NEW_C1,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _post_transfer(ac, client_id: str, beneficiary_id: str, amount: str, purpose: str = "", device: bool = True) -> dict:
    response = await ac.post("/api/v1/transactions/", json={
        "client_external_id": client_id,
        "beneficiary_external_id": beneficiary_id,
        "amount": amount,
        "purpose": purpose,
        "device_recognized": device,
    })
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    return response.json()


# ── Estrutura da resposta ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transfer_response_has_all_top_level_fields(seeded_client):
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "500.00", "Serviço mensal")
    assert "transaction" in data
    assert "analysis" in data
    assert "gateway" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_transfer_response_gateway_has_required_fields(seeded_client):
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "500.00", "Serviço")
    gw = data["gateway"]
    assert gw is not None
    assert "authorized" in gw
    assert "final_status" in gw
    assert "final_action" in gw
    assert "risk_level" in gw
    assert "risk_score" in gw
    assert "requires_confirmation" in gw
    assert "requires_human_review" in gw
    assert "gateway_reasoning" in gw
    assert "flags" in gw
    assert isinstance(gw["flags"], list)
    assert isinstance(gw["risk_score"], float)


@pytest.mark.asyncio
async def test_transfer_response_analysis_has_agent_results(seeded_client):
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "500.00", "Serviço")
    analysis = data["analysis"]
    # Após Etapa 3 todos os campos de agente devem ser preenchidos
    assert analysis["fraud_agent_result"] is not None
    assert analysis["inconsistency_agent_result"] is not None
    assert analysis["behavioral_agent_result"] is not None
    assert analysis["risk_agent_result"] is not None
    assert analysis["status"] == "completed"


# ── Cenário de baixo risco (A) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_low_risk_transfer_is_released(seeded_client):
    """Transferência normal para beneficiário conhecido → RELEASED."""
    ac, _ = seeded_client
    data = await _post_transfer(
        ac, CLIENT_A_EXT, BEN_KNOWN_A1,
        amount="500.00",
        purpose="Pagamento regular de serviço",
        device=True,
    )
    txn = data["transaction"]
    gw = data["gateway"]
    assert txn["status"] == "released"
    assert gw["authorized"] is True
    assert gw["requires_confirmation"] is False
    assert gw["requires_human_review"] is False
    assert gw["final_action"] == "approve"
    assert gw["risk_level"] == "low"


@pytest.mark.asyncio
async def test_low_risk_transfer_risk_score_below_threshold(seeded_client):
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "300.00", "Pagamento")
    gw = data["gateway"]
    assert gw["risk_score"] < 0.30, f"Expected score < 0.30, got {gw['risk_score']}"


# ── Cenário de risco médio / alto (B) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_medium_risk_transfer_requires_verification(seeded_client):
    """
    Beneficiário novo + valor 5x acima da média de Carlos (avg=3500) → score ≥ 0.30.
    Carlos tem limite de R$30.000, então R$18.000 é válido.
    """
    ac, _ = seeded_client
    data = await _post_transfer(
        ac, CLIENT_B_EXT, BEN_NEW_B1,
        amount="18000.00",   # 5x acima da média de 3500 → flag amount_above_avg
        purpose="Fornecedor desconhecido",
        device=True,
    )
    txn = data["transaction"]
    gw = data["gateway"]
    # Novo beneficiário + valor acima da média → score deve cruzar 0.30
    assert txn["status"] in ("under_verification", "awaiting_confirmation", "escalated_to_human", "human_review_pending")
    assert gw["risk_score"] >= 0.30
    assert "new_beneficiary" in gw["flags"]


# ── Cenário de engenharia social (C) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_social_engineering_scenario_is_escalated(seeded_client):
    """
    Engenharia social com Beatriz (limite R$5.000).
    Valor R$4.000 (< limite) com frase de engenharia social → score ≥ 0.55.
    """
    ac, _ = seeded_client
    data = await _post_transfer(
        ac, CLIENT_C_EXT, BEN_NEW_C1,
        amount="4000.00",   # dentro do limite de R$5.000 de Beatriz
        purpose="Funcionário do banco me pediu para proteger minha conta",
        device=False,
    )
    txn = data["transaction"]
    gw = data["gateway"]
    # Engenharia social + novo beneficiário + dispositivo não reconhecido
    assert txn["status"] in ("under_verification", "awaiting_confirmation", "escalated_to_human", "human_review_pending", "rejected")
    assert gw["risk_score"] >= 0.55
    # Deve detectar o flag de engenharia social
    assert any(
        "social_engineering" in f or "third_party" in f
        for f in gw["flags"]
    ), f"Expected social_engineering flag, got: {gw['flags']}"


@pytest.mark.asyncio
async def test_social_engineering_flags_detected(seeded_client):
    """Palavra-chave de engenharia social na finalidade → flag detectado."""
    ac, _ = seeded_client
    data = await _post_transfer(
        ac, CLIENT_A_EXT, BEN_KNOWN_A1,
        amount="500.00",
        purpose="Funcionário do banco me orientou a fazer esta transferência",
        device=True,
    )
    gw = data["gateway"]
    all_flags = gw["flags"]
    assert any("social_engineering" in f for f in all_flags), \
        f"Expected social_engineering flag, got: {all_flags}"


# ── Score e nível de risco consistentes ──────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_score_and_level_are_consistent(seeded_client):
    """Score e nível de risco devem ser coerentes entre si."""
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "800.00", "Serviço")
    gw = data["gateway"]
    score = gw["risk_score"]
    level = gw["risk_level"]
    if score < 0.30:
        assert level == "low"
    elif score < 0.60:
        assert level in ("low", "medium")
    elif score < 0.85:
        assert level in ("medium", "high", "critical")
    else:
        assert level in ("high", "critical")


@pytest.mark.asyncio
async def test_transaction_status_matches_gateway_action(seeded_client):
    """Status da transação deve ser coerente com a ação do gateway."""
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "1000.00", "Pagamento")
    txn = data["transaction"]
    gw = data["gateway"]
    action = gw["final_action"]
    status = txn["status"]

    if action == "approve":
        assert status == "released"
    elif action in ("request_confirmation",):
        assert status in ("under_verification", "awaiting_confirmation", "human_review_pending")
    elif action == "escalate_to_human":
        assert status in ("escalated_to_human", "human_review_pending")
    elif action == "block":
        assert status == "rejected"


# ── Persistência pós-pipeline ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_analysis_persisted_after_pipeline(seeded_client):
    """Após a transferência, a análise de risco deve estar persistida e consultável."""
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "600.00", "Serviço")
    txn_id = data["transaction"]["external_id"]

    # Consultar análise via endpoint
    response = await ac.get(f"/api/v1/risk-analyses/transaction/{txn_id}")
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["status"] == "completed"
    assert analysis["overall_risk_score"] >= 0.0
    assert analysis["fraud_agent_result"] is not None


@pytest.mark.asyncio
async def test_audit_log_created_after_pipeline(seeded_client):
    """Pipeline deve criar ao menos um audit log."""
    ac, _ = seeded_client
    # Conta os logs antes
    before = await ac.get("/api/v1/audit/", params={"limit": 200})
    count_before = len(before.json())

    await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "400.00", "Serviço")

    after = await ac.get("/api/v1/audit/", params={"limit": 200})
    count_after = len(after.json())
    assert count_after > count_before, "Esperado ao menos um novo audit log após o pipeline"
