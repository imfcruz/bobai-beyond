"""
Testes de transações — persistência, validação de valores e transições de estado.
"""

import pytest
from decimal import Decimal

from app.models.transaction import TransactionStatus, RiskLevel
from app.core.errors import ValidationError
from app.repositories.transaction_repo import TransactionRepository
from app.services.seed_service import CLIENT_A_EXT, CLIENT_B_EXT, BEN_KNOWN_A1, BEN_NEW_B1, TXN_A
from app.services.bank_service import BankService


# ── Persistência ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initiate_transfer_persists_transaction(seeded_db):
    db, _ = seeded_db
    svc = BankService(db)
    result = await svc.initiate_transfer(
        client_external_id=CLIENT_A_EXT,
        beneficiary_external_id=BEN_KNOWN_A1,
        amount_str="500.00",
        purpose="Pagamento de serviço",
    )
    txn = result["transaction"]
    assert txn.id is not None
    assert txn.external_id is not None
    assert txn.amount == Decimal("500.00")


@pytest.mark.asyncio
async def test_transfer_creates_risk_analysis(seeded_db):
    db, _ = seeded_db
    svc = BankService(db)
    result = await svc.initiate_transfer(
        client_external_id=CLIENT_A_EXT,
        beneficiary_external_id=BEN_KNOWN_A1,
        amount_str="500.00",
        purpose="Teste",
    )
    analysis = result["analysis"]
    assert analysis.id is not None
    assert analysis.transaction_id == result["transaction"].id
    assert analysis.overall_risk_score >= 0.0


# ── Validação de valores ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transfer_rejects_zero_amount(seeded_db):
    db, _ = seeded_db
    svc = BankService(db)
    with pytest.raises(ValidationError, match="positivo"):
        await svc.initiate_transfer(
            client_external_id=CLIENT_A_EXT,
            beneficiary_external_id=BEN_KNOWN_A1,
            amount_str="0.00",
            purpose="Teste",
        )


@pytest.mark.asyncio
async def test_transfer_rejects_negative_amount(seeded_db):
    db, _ = seeded_db
    svc = BankService(db)
    with pytest.raises(ValidationError):
        await svc.initiate_transfer(
            client_external_id=CLIENT_A_EXT,
            beneficiary_external_id=BEN_KNOWN_A1,
            amount_str="-100.00",
            purpose="Teste",
        )


@pytest.mark.asyncio
async def test_transfer_rejects_invalid_amount_string(seeded_db):
    db, _ = seeded_db
    svc = BankService(db)
    with pytest.raises(ValidationError, match="inválido"):
        await svc.initiate_transfer(
            client_external_id=CLIENT_A_EXT,
            beneficiary_external_id=BEN_KNOWN_A1,
            amount_str="abc",
            purpose="Teste",
        )


@pytest.mark.asyncio
async def test_transfer_rejects_amount_above_limit(seeded_db):
    db, _ = seeded_db
    svc = BankService(db)
    # Limite de Ana é R$ 8.000
    with pytest.raises(ValidationError, match="limite"):
        await svc.initiate_transfer(
            client_external_id=CLIENT_A_EXT,
            beneficiary_external_id=BEN_KNOWN_A1,
            amount_str="9000.00",
            purpose="Teste",
        )


@pytest.mark.asyncio
async def test_transfer_rejects_wrong_beneficiary_client(seeded_db):
    db, _ = seeded_db
    svc = BankService(db)
    # BEN_NEW_B1 pertence a Carlos, não a Ana
    with pytest.raises(ValidationError, match="cliente"):
        await svc.initiate_transfer(
            client_external_id=CLIENT_A_EXT,
            beneficiary_external_id=BEN_NEW_B1,
            amount_str="500.00",
            purpose="Teste",
        )


# ── Transições de estado ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_state_transition_pending_to_released(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_A)
    # Cria uma nova transação no estado PENDING para testar transição
    from app.models.transaction import Transaction
    import uuid
    new_txn = Transaction(
        external_id=str(uuid.uuid4()),
        client_id=txn.client_id,
        beneficiary_id=txn.beneficiary_id,
        amount=Decimal("100.00"),
        status=TransactionStatus.PENDING,
        currency="BRL",
    )
    db.add(new_txn)
    await db.flush()

    updated = await repo.transition_status(new_txn, TransactionStatus.RELEASED)
    assert updated.status == TransactionStatus.RELEASED


@pytest.mark.asyncio
async def test_invalid_state_transition_raises_error(seeded_db):
    db, _ = seeded_db
    repo = TransactionRepository(db)
    txn = await repo.get_by_external_id(TXN_A)
    # TXN_A já está em RELEASED — tentar ir para PENDING deve falhar
    with pytest.raises(ValidationError, match="inválida"):
        await repo.transition_status(txn, TransactionStatus.PENDING)


@pytest.mark.asyncio
async def test_terminal_states_have_no_valid_transitions(seeded_db):
    from app.models.transaction import VALID_TRANSITIONS
    terminal_states = [
        TransactionStatus.RELEASED,
        TransactionStatus.APPROVED,
        TransactionStatus.REJECTED,
        TransactionStatus.BLOCKED,
    ]
    for state in terminal_states:
        assert VALID_TRANSITIONS[state] == set(), \
            f"Estado terminal {state} não deveria ter transições"


# ── Endpoint POST /transactions ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_transaction_endpoint(seeded_client):
    ac, _ = seeded_client
    payload = {
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "800.00",
        "purpose": "Pagamento de serviço mensal",
        "device_recognized": True,
    }
    response = await ac.post("/api/v1/transactions/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "transaction" in data
    assert "analysis" in data
    assert "message" in data
    assert data["transaction"]["amount"] == "800.00"


@pytest.mark.asyncio
async def test_post_transaction_returns_422_for_invalid_amount(seeded_client):
    ac, _ = seeded_client
    payload = {
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "invalid",
        "purpose": "Teste",
    }
    response = await ac.post("/api/v1/transactions/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_transaction_endpoint(seeded_client):
    ac, _ = seeded_client
    from app.services.seed_service import TXN_A
    response = await ac.get(f"/api/v1/transactions/{TXN_A}")
    assert response.status_code == 200
    data = response.json()
    assert data["external_id"] == TXN_A
    assert "client_name" in data or "amount" in data
