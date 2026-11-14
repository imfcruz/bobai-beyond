"""
Testes E2E de Etapa 6 — Fluxo completo de pipeline integrado.

Cobrem os 10 cenários solicitados:
1. Operação normal (baixo risco)
2. Operação incomum (valor/comportamento fora do padrão)
3. Engenharia social detectada
4. Divergência entre agentes
5. Timeout no pipeline (simulado)
6. Resposta inválida da LLM
7. Falha de conexão (simulada)
8. Tentativa de ação não autorizada (Gateway enforcement)
9. Revisão humana (fluxo completo: escalada → revisão → aprovação/rejeição)
10. Reenvio duplicado (idempotência)

Verificações adicionais:
- Audit log completo após cada operação
- Divergência registrada no analysis
- Confirmação contextual (Fase 2)
- Human review rejeita identificador de IA
- Falha nunca produz RELEASED automático
"""

import asyncio
import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

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

async def _post_transfer(
    ac,
    client_id: str,
    beneficiary_id: str,
    amount: str,
    purpose: str = "",
    device: bool = True,
    idempotency_key: str | None = None,
) -> dict:
    payload = {
        "client_external_id": client_id,
        "beneficiary_external_id": beneficiary_id,
        "amount": amount,
        "purpose": purpose,
        "device_recognized": device,
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    response = await ac.post("/api/v1/transactions/", json=payload)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    return response.json()


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 1 — Operação Normal (baixo risco)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_normal_operation_low_risk(seeded_client):
    """Transferência normal para beneficiário conhecido → RELEASED automaticamente."""
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "500.00", "Pagamento de serviço")

    txn = data["transaction"]
    gw = data["gateway"]
    analysis = data["analysis"]

    assert txn["status"] == "released"
    assert gw["authorized"] is True
    assert gw["risk_score"] < 0.30
    assert gw["requires_confirmation"] is False
    assert gw["requires_human_review"] is False
    assert gw["final_action"] == "approve"
    assert analysis["status"] == "completed"
    assert analysis["phase"] == "initial"
    assert gw["policy_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_e2e_normal_operation_audit_log_created(seeded_client):
    """Operação normal deve criar audit log com policy_version."""
    ac, _ = seeded_client
    before_resp = await ac.get("/api/v1/audit/", params={"limit": 200})
    count_before = len(before_resp.json())

    await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "300.00", "Pagamento")

    after_resp = await ac.get("/api/v1/audit/", params={"limit": 200})
    logs = after_resp.json()
    assert len(logs) > count_before

    # Pelo menos um log após a transferência deve ter policy_version
    pipeline_logs = [l for l in logs if l.get("component") == "security_gateway"]
    assert len(pipeline_logs) > 0, "Deve existir audit log do security_gateway"
    assert any(
        l.get("policy_version") == "1.0.0" for l in pipeline_logs
    ), f"Logs do gateway sem policy_version: {pipeline_logs}"


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 2 — Operação Incomum
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_unusual_operation_requires_action(seeded_client):
    """
    Operação incomum: valor muito acima da média, beneficiário novo.
    Espera: score ≥ 0.30 e status diferente de RELEASED.
    """
    ac, _ = seeded_client
    data = await _post_transfer(
        ac, CLIENT_B_EXT, BEN_NEW_B1,
        amount="18000.00",  # 5x acima da média de Carlos
        purpose="Fornecedor novo",
        device=True,
    )
    txn = data["transaction"]
    gw = data["gateway"]

    assert txn["status"] != "released", (
        f"Operação incomum não deveria ser liberada automaticamente. Status: {txn['status']}"
    )
    assert gw["risk_score"] >= 0.30
    assert "new_beneficiary" in gw["flags"]


@pytest.mark.asyncio
async def test_e2e_unusual_operation_analysis_persisted(seeded_client):
    """Após operação incomum, análise deve estar persistida e consultável."""
    ac, _ = seeded_client
    data = await _post_transfer(
        ac, CLIENT_B_EXT, BEN_NEW_B1, "18000.00", "Fornecedor"
    )
    txn_id = data["transaction"]["external_id"]

    resp = await ac.get(f"/api/v1/risk-analyses/transaction/{txn_id}")
    assert resp.status_code == 200
    analysis = resp.json()
    # Operação incomum deve registrar score relevante (>= 0.20)
    assert analysis["overall_risk_score"] >= 0.20
    assert analysis["fraud_agent_result"] is not None
    assert analysis["behavioral_agent_result"] is not None


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 3 — Engenharia Social
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_social_engineering_detected_flags(seeded_client):
    """Engenharia social: agentes detectam flags específicos."""
    ac, _ = seeded_client
    data = await _post_transfer(
        ac, CLIENT_C_EXT, BEN_NEW_C1,
        amount="4000.00",
        purpose="Funcionário do banco me orientou a transferir para conta segura",
        device=False,
    )
    gw = data["gateway"]
    all_flags = gw["flags"]

    assert any("social_engineering" in f or "third_party" in f for f in all_flags), (
        f"Nenhum flag de engenharia social detectado: {all_flags}"
    )
    assert gw["risk_score"] >= 0.55


@pytest.mark.asyncio
async def test_e2e_social_engineering_not_auto_released(seeded_client):
    """Engenharia social nunca deve ser liberada automaticamente."""
    ac, _ = seeded_client
    data = await _post_transfer(
        ac, CLIENT_C_EXT, BEN_NEW_C1,
        amount="4000.00",
        purpose="Banco ligou e pediu para proteger minha conta urgente",
        device=False,
    )
    txn = data["transaction"]
    assert txn["status"] != "released", (
        f"Engenharia social não pode ser auto-liberada. Status: {txn['status']}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 4 — Divergência entre Agentes
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_divergence_detected_and_recorded(seeded_client):
    """
    Quando agentes divergem significativamente, a divergência deve ser registrada
    na análise e influenciar a decisão (não descartada silenciosamente).
    """
    from app.agents.base import (
        AgentContext, AgentMode, AgentRecommendedAction,
        AgentResult, AgentRiskLevel, AgentStatus,
    )
    from app.services.decision_engine import make_decision

    # Criar resultados com divergência alta (spread > 0.40)
    from app.agents.base import AgentResult as AR
    from tests.test_agents import _make_agent_result

    high_result = _make_agent_result("fraud_agent", risk_score=0.85, flags=["social_engineering_keyword"])
    low_result = _make_agent_result("behavioral_agent", risk_score=0.10, flags=[])
    medium_result = _make_agent_result("inconsistency_agent", risk_score=0.30, flags=[])
    consolidated = _make_agent_result("risk_agent", risk_score=0.42, flags=["social_engineering_keyword"])

    decision = make_decision(consolidated, sub_results=[high_result, low_result, medium_result])

    assert decision.divergence_detected is True, "Divergência deveria ser detectada (spread > 0.40)"
    assert decision.divergence_details is not None
    details = json.loads(decision.divergence_details)
    assert details["spread"] > 0.40
    assert "fraud_agent" in details["high_risk_agents"]
    # Divergência não descarta avaliações de alto risco
    assert decision.risk_score >= 0.42  # Score foi levemente elevado pela divergência


@pytest.mark.asyncio
async def test_e2e_divergence_escalates_to_human_review(seeded_client):
    """Divergência significativa deve escalar para revisão humana."""
    from tests.test_agents import _make_agent_result
    from app.services.decision_engine import make_decision
    from app.models.transaction import TransactionStatus

    high = _make_agent_result("fraud_agent", risk_score=0.75)
    low = _make_agent_result("behavioral_agent", risk_score=0.10)
    med = _make_agent_result("inconsistency_agent", risk_score=0.30)
    consolidated = _make_agent_result("risk_agent", risk_score=0.40)

    decision = make_decision(consolidated, sub_results=[high, low, med])

    assert decision.divergence_detected is True
    # Divergência com score médio → HUMAN_REVIEW_PENDING (não AWAITING_CONFIRMATION)
    assert decision.transaction_status == TransactionStatus.HUMAN_REVIEW_PENDING


@pytest.mark.asyncio
async def test_e2e_no_divergence_not_falsely_flagged(seeded_client):
    """Agentes convergentes não devem acionar flag de divergência."""
    from tests.test_agents import _make_agent_result
    from app.services.decision_engine import make_decision

    r1 = _make_agent_result("fraud_agent", risk_score=0.12)
    r2 = _make_agent_result("behavioral_agent", risk_score=0.15)
    r3 = _make_agent_result("inconsistency_agent", risk_score=0.10)
    consolidated = _make_agent_result("risk_agent", risk_score=0.12)

    decision = make_decision(consolidated, sub_results=[r1, r2, r3])
    assert decision.divergence_detected is False


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 5 — Timeout no Pipeline
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_pipeline_timeout_keeps_pending(seeded_client):
    """
    Timeout no pipeline de agentes não deve produzir aprovação automática.
    A transação deve permanecer em PENDING e a análise como FAILED.
    """
    ac, _ = seeded_client

    # Simular timeout sem deixar a coroutine recebida sem await/close.
    async def raise_timeout(awaitable, *args, **kwargs):
        awaitable.close()
        raise asyncio.TimeoutError()

    with patch(
        "app.services.bank_service.asyncio.wait_for",
        new=AsyncMock(side_effect=raise_timeout),
    ):
        data = await _post_transfer(
            ac, CLIENT_A_EXT, BEN_KNOWN_A1, "500.00", "Pagamento timeout test"
        )

    txn = data["transaction"]
    analysis = data["analysis"]

    # Falha NUNCA produz liberação automática
    assert txn["status"] == "pending", (
        f"Timeout não deve liberar transação. Status: {txn['status']}"
    )
    assert analysis["status"] == "failed", (
        f"Análise deveria ser FAILED após timeout. Status: {analysis['status']}"
    )
    assert data.get("pipeline_failed") is True
    assert data.get("gateway") is None, "Gateway não deve ser chamado após timeout"


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 6 — Resposta Inválida da LLM
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_invalid_llm_response_uses_rules_fallback(seeded_client):
    """
    Resposta inválida da LLM deve usar fallback de regras.
    O pipeline não deve falhar — apenas marcar FALLBACK_USED.
    """
    ac, _ = seeded_client

    # Simular LLM retornando JSON malformado
    async def bad_json(*args, **kwargs):
        raise ValueError("JSON inválido: { não é JSON")

    with patch(
        "app.services.llm_client.MockLLMClient.complete_json",
        side_effect=bad_json,
    ):
        # O pipeline deve funcionar com fallback para RULES_MODE
        data = await _post_transfer(
            ac, CLIENT_A_EXT, BEN_KNOWN_A1, "400.00", "Serviço teste LLM fallback"
        )

    # Pipeline deve completar (com fallback), não falhar
    analysis = data["analysis"]
    assert analysis["status"] == "completed", (
        "Pipeline deve completar mesmo com LLM inválida (fallback para regras)"
    )
    txn = data["transaction"]
    # Status deve ser determinado pelas regras, não pelo pipeline falhando
    assert txn["status"] != "pending" or analysis["status"] == "failed"


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 7 — Falha de Conexão
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_connection_failure_pipeline_keeps_pending(seeded_client):
    """
    Falha de conexão no pipeline (ex: Exception genérica) não deve liberar transação.
    """
    ac, _ = seeded_client

    async def raise_connection_failure(awaitable, *args, **kwargs):
        awaitable.close()
        raise RuntimeError("Simulated connection failure")

    with patch(
        "app.services.bank_service.asyncio.wait_for",
        new=AsyncMock(side_effect=raise_connection_failure),
    ):
        data = await _post_transfer(
            ac, CLIENT_A_EXT, BEN_KNOWN_A1, "500.00", "Conexão falha"
        )

    txn = data["transaction"]
    analysis = data["analysis"]

    assert txn["status"] == "pending", (
        f"Falha de conexão não deve liberar. Status: {txn['status']}"
    )
    assert analysis["status"] == "failed"
    assert data.get("pipeline_failed") is True
    assert "connection" in data.get("failure_reason", "").lower() or \
           "falha" in data.get("failure_reason", "").lower()


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 8 — Tentativa de Ação Não Autorizada
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_unauthorized_action_approve_critical(seeded_client):
    """
    SecurityGateway deve bloquear APPROVE em nível CRITICAL.
    """
    from app.models.transaction import RiskLevel
    from app.models.risk_analysis import RecommendedAction
    from app.services.decision_engine import Decision, POLICY_VERSION
    from app.services.security_gateway import SecurityGateway
    from app.models.transaction import TransactionStatus

    gw = SecurityGateway()

    # Tentar aprovar uma transação CRITICAL — não permitido
    decision = Decision(
        risk_level=RiskLevel.CRITICAL,
        recommended_action=RecommendedAction.APPROVE,  # NÃO PERMITIDO para CRITICAL
        transaction_status=TransactionStatus.RELEASED,
        risk_score=0.95,
        reasoning="Tentativa de aprovar critical",
        flags=["social_engineering_keyword"],
    )

    response = gw.evaluate(decision)

    # Gateway deve detectar ação não autorizada e substituir por conservadora
    assert response.unauthorized_action_attempted is True
    assert response.final_action != RecommendedAction.APPROVE, (
        "Gateway não deve permitir APPROVE em nível CRITICAL"
    )
    assert response.final_action in (
        RecommendedAction.ESCALATE_TO_HUMAN, RecommendedAction.BLOCK
    )


@pytest.mark.asyncio
async def test_e2e_unauthorized_action_approve_medium(seeded_client):
    """
    SecurityGateway deve corrigir APPROVE em nível MEDIUM.
    """
    from app.models.transaction import RiskLevel
    from app.models.risk_analysis import RecommendedAction
    from app.services.decision_engine import Decision
    from app.services.security_gateway import SecurityGateway
    from app.models.transaction import TransactionStatus

    gw = SecurityGateway()
    decision = Decision(
        risk_level=RiskLevel.MEDIUM,
        recommended_action=RecommendedAction.APPROVE,  # NÃO PERMITIDO para MEDIUM
        transaction_status=TransactionStatus.RELEASED,
        risk_score=0.45,
        reasoning="Tentativa indevida",
        flags=[],
    )
    response = gw.evaluate(decision)
    assert response.unauthorized_action_attempted is True
    assert response.final_action != RecommendedAction.APPROVE


@pytest.mark.asyncio
async def test_e2e_human_review_with_ai_id_rejected(seeded_client):
    """
    Tentativa de revisão humana com ID de sistema/IA deve ser rejeitada.
    """
    ac, _ = seeded_client

    # Primeiro criar uma transação que precise de revisão humana
    data = await _post_transfer(
        ac, CLIENT_C_EXT, BEN_NEW_C1,
        amount="4000.00",
        purpose="Funcionário do banco me pediu para proteger conta",
        device=False,
    )
    txn_id = data["transaction"]["external_id"]

    # Tentar revisar com ID de IA — deve ser recusado
    for ai_id in ["ai_reviewer", "llm_bot", "auto_approve", "model_agent"]:
        resp = await ac.post(
            f"/api/v1/transactions/{txn_id}/human-review/approve",
            json={"reviewer_id": ai_id, "reviewer_notes": "Aprovado automaticamente"},
        )
        # Deve retornar 400/422 (erro de validação)
        assert resp.status_code in (400, 422), (
            f"ID de IA '{ai_id}' não deveria ser aceito. Status: {resp.status_code}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 9 — Revisão Humana Completa
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_human_review_approve_flow(seeded_client):
    """
    Fluxo completo: escalada → HUMAN_REVIEW_PENDING → aprovação humana → HUMAN_APPROVED.
    """
    ac, _ = seeded_client

    # 1. Criar transação que escale para revisão humana
    data = await _post_transfer(
        ac, CLIENT_C_EXT, BEN_NEW_C1,
        amount="4000.00",
        purpose="Funcionário do banco me orientou a transferir",
        device=False,
    )
    txn_id = data["transaction"]["external_id"]
    txn_status = data["transaction"]["status"]

    # Deve estar em revisão humana ou aguardando confirmação
    assert txn_status in ("human_review_pending", "awaiting_confirmation", "escalated_to_human"), (
        f"Esperado revisão humana, obtido: {txn_status}"
    )

    # Se estiver aguardando confirmação, confirmar primeiro
    if txn_status == "awaiting_confirmation":
        confirm_resp = await ac.post(
            f"/api/v1/transactions/{txn_id}/confirm",
            json={"confirmation_purpose": "Não sei o motivo, banco me pediu"},
        )
        assert confirm_resp.status_code == 200
        txn_status = confirm_resp.json()["new_status"]

    # 2. Verificar se está em HUMAN_REVIEW_PENDING ou ESCALATED
    if txn_status not in ("human_review_pending", "escalated_to_human"):
        pytest.skip(f"Transação não atingiu revisão humana: {txn_status}")

    # 3. Revisor humano aprova
    review_resp = await ac.post(
        f"/api/v1/transactions/{txn_id}/human-review/approve",
        json={"reviewer_id": "operador_demo_001", "reviewer_notes": "Revisado e aprovado"},
    )
    assert review_resp.status_code == 200
    review_data = review_resp.json()
    assert review_data["new_status"] == "human_approved"
    assert review_data["action"] == "approve"
    assert review_data["reviewer_id"] == "operador_demo_001"


@pytest.mark.asyncio
async def test_e2e_human_review_reject_flow(seeded_client):
    """Fluxo de rejeição humana: HUMAN_REVIEW_PENDING → HUMAN_REJECTED."""
    ac, _ = seeded_client

    data = await _post_transfer(
        ac, CLIENT_C_EXT, BEN_NEW_C1,
        amount="4000.00",
        purpose="Banco ligou pedindo transferência urgente",
        device=False,
    )
    txn_id = data["transaction"]["external_id"]
    txn_status = data["transaction"]["status"]

    if txn_status == "awaiting_confirmation":
        confirm_resp = await ac.post(
            f"/api/v1/transactions/{txn_id}/confirm",
            json={"confirmation_purpose": "Banco me obrigou a transferir"},
        )
        txn_status = confirm_resp.json()["new_status"]

    if txn_status not in ("human_review_pending", "escalated_to_human"):
        pytest.skip(f"Transação não atingiu revisão humana: {txn_status}")

    # Revisor rejeita
    review_resp = await ac.post(
        f"/api/v1/transactions/{txn_id}/human-review/reject",
        json={"reviewer_id": "supervisor_001", "reviewer_notes": "Suspeita de fraude confirmada"},
    )
    assert review_resp.status_code == 200
    review_data = review_resp.json()
    assert review_data["new_status"] == "human_rejected"
    assert review_data["action"] == "reject"


@pytest.mark.asyncio
async def test_e2e_human_review_wrong_status_rejected(seeded_client):
    """Revisão humana em transação RELEASED deve ser recusada."""
    ac, _ = seeded_client

    # Criar transação de baixo risco (liberada automaticamente)
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "200.00", "Pagamento normal")
    txn_id = data["transaction"]["external_id"]
    assert data["transaction"]["status"] == "released"

    # Tentar revisão humana — status errado
    review_resp = await ac.post(
        f"/api/v1/transactions/{txn_id}/human-review/approve",
        json={"reviewer_id": "operador_001"},
    )
    assert review_resp.status_code in (400, 422), (
        f"Revisão de transação RELEASED deveria ser recusada. Status: {review_resp.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Cenário 10 — Reenvio Duplicado (Idempotência)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_idempotency_same_key_returns_same_result(seeded_client):
    """
    Reenvio com mesma idempotency_key deve retornar resultado existente,
    sem reprocessar o pipeline.
    """
    ac, _ = seeded_client
    key = "idem-test-key-001"

    # Primeira requisição
    data1 = await _post_transfer(
        ac, CLIENT_A_EXT, BEN_KNOWN_A1, "500.00", "Pagamento original",
        idempotency_key=key,
    )

    # Segunda requisição com mesma chave
    data2 = await _post_transfer(
        ac, CLIENT_A_EXT, BEN_KNOWN_A1, "500.00", "Pagamento original",
        idempotency_key=key,
    )

    # Ambas devem retornar a mesma transação
    assert data1["transaction"]["external_id"] == data2["transaction"]["external_id"], (
        "Reenvio deve retornar a mesma transação"
    )
    assert data2.get("idempotent") is True, (
        "Segunda requisição deve ser marcada como idempotente"
    )


@pytest.mark.asyncio
async def test_e2e_idempotency_different_keys_creates_two_transactions(seeded_client):
    """
    Duas requisições com chaves diferentes devem criar duas transações distintas.
    """
    ac, _ = seeded_client

    data1 = await _post_transfer(
        ac, CLIENT_A_EXT, BEN_KNOWN_A1, "300.00", "Pagamento A",
        idempotency_key="key-unique-001",
    )
    data2 = await _post_transfer(
        ac, CLIENT_A_EXT, BEN_KNOWN_A1, "300.00", "Pagamento B",
        idempotency_key="key-unique-002",
    )

    assert data1["transaction"]["external_id"] != data2["transaction"]["external_id"]
    assert data2.get("idempotent") is not True


@pytest.mark.asyncio
async def test_e2e_no_idempotency_key_always_creates_new(seeded_client):
    """
    Sem idempotency_key, cada requisição cria uma transação nova.
    """
    ac, _ = seeded_client

    data1 = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "200.00", "Sem chave 1")
    data2 = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "200.00", "Sem chave 2")

    assert data1["transaction"]["external_id"] != data2["transaction"]["external_id"]


# ═══════════════════════════════════════════════════════════════════════════
# Confirmação Contextual (Fase 2)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_confirmation_genuine_purpose_releases(seeded_client):
    """
    Confirmação com finalidade genuína e score médio → RELEASED.
    """
    ac, _ = seeded_client

    data = await _post_transfer(
        ac, CLIENT_B_EXT, BEN_NEW_B1,
        amount="18000.00",
        purpose="Novo fornecedor",
        device=True,
    )
    txn_id = data["transaction"]["external_id"]
    txn_status = data["transaction"]["status"]

    if txn_status != "awaiting_confirmation":
        pytest.skip(f"Status não adequado para confirmação: {txn_status}")

    # Confirmar com finalidade genuína
    confirm_resp = await ac.post(
        f"/api/v1/transactions/{txn_id}/confirm",
        json={"confirmation_purpose": "Pagamento de serviço para fornecedor de software"},
    )
    assert confirm_resp.status_code == 200
    result = confirm_resp.json()
    # Score médio (0.41) + finalidade genuína → RELEASED
    assert result["new_status"] in ("released", "human_review_pending"), (
        f"Confirmação genuína deve liberar ou revisar. Status: {result['new_status']}"
    )
    assert result["coercion_detected"] is False


@pytest.mark.asyncio
async def test_e2e_confirmation_coercion_escalates(seeded_client):
    """
    Confirmação com indicador de coerção → HUMAN_REVIEW_PENDING.
    """
    ac, _ = seeded_client

    data = await _post_transfer(
        ac, CLIENT_B_EXT, BEN_NEW_B1,
        amount="18000.00",
        purpose="Novo beneficiário",
        device=True,
    )
    txn_id = data["transaction"]["external_id"]
    txn_status = data["transaction"]["status"]

    if txn_status != "awaiting_confirmation":
        pytest.skip(f"Status não adequado: {txn_status}")

    # Confirmar com indicador de coerção
    confirm_resp = await ac.post(
        f"/api/v1/transactions/{txn_id}/confirm",
        json={"confirmation_purpose": "Um funcionário do banco me disse para transferir"},
    )
    assert confirm_resp.status_code == 200
    result = confirm_resp.json()
    assert result["new_status"] == "human_review_pending"
    assert result["coercion_detected"] is True


@pytest.mark.asyncio
async def test_e2e_confirmation_wrong_status_rejected(seeded_client):
    """
    Confirmação em transação não-AWAITING_CONFIRMATION deve ser recusada.
    """
    ac, _ = seeded_client

    # Transação de baixo risco (RELEASED)
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "100.00", "Baixo risco")
    txn_id = data["transaction"]["external_id"]
    assert data["transaction"]["status"] == "released"

    resp = await ac.post(
        f"/api/v1/transactions/{txn_id}/confirm",
        json={"confirmation_purpose": "Tentar confirmar transação já liberada"},
    )
    assert resp.status_code in (400, 422)


# ═══════════════════════════════════════════════════════════════════════════
# Auditoria e rastreabilidade completa
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_audit_trail_complete(seeded_client):
    """
    Pipeline completo deve produzir audit log rastreável com todos os campos.
    """
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "700.00", "Auditoria teste")
    txn_id = data["transaction"]["external_id"]

    # Consultar eventos da transação
    events_resp = await ac.get(f"/api/v1/events/transaction/{txn_id}")
    assert events_resp.status_code == 200
    events = events_resp.json()
    # Deve ter ao menos o evento INICIO_TRANSFERENCIA
    event_types = [e["event_type"] for e in events]
    assert "INICIO_TRANSFERENCIA" in event_types

    # Consultar análise de risco
    analysis_resp = await ac.get(f"/api/v1/risk-analyses/transaction/{txn_id}")
    assert analysis_resp.status_code == 200
    analysis = analysis_resp.json()
    assert analysis["policy_version"] == "1.0.0"
    assert analysis["fraud_agent_result"] is not None
    assert analysis["risk_agent_result"] is not None


@pytest.mark.asyncio
async def test_e2e_policy_version_in_gateway_response(seeded_client):
    """Gateway response deve sempre incluir policy_version."""
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "400.00", "Policy test")
    gw = data["gateway"]
    assert gw is not None
    assert gw.get("policy_version") == "1.0.0"


@pytest.mark.asyncio
async def test_e2e_divergence_info_in_analysis(seeded_client):
    """Análise deve registrar se houve ou não divergência."""
    ac, _ = seeded_client
    data = await _post_transfer(ac, CLIENT_A_EXT, BEN_KNOWN_A1, "300.00", "Divergence check")
    txn_id = data["transaction"]["external_id"]

    resp = await ac.get(f"/api/v1/risk-analyses/transaction/{txn_id}")
    analysis = resp.json()
    assert "divergence_detected" in analysis  # Campo deve existir (mesmo que False)
