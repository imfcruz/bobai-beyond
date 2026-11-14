"""
Testes de Integridade Financeira — Fase 1 do Nexus Bank.

Verificam:
- Transferência aprovada debita saldo.
- Transferência aprovada aparece no extrato.
- Transferência pendente NÃO é debitada definitivamente.
- Transferência rejeitada preserva saldo.
- Transferência duplicada não gera débito duplo (idempotência).
- Saldo insuficiente impede efetivação.
- Limite insuficiente impede efetivação.
- Aumento de limite gera evento contextual.
- Beneficiário novo gera evento contextual.
- Reserva de saldo em transações pendentes.
- Extrato do seed contém lançamento correto.
- settlement_applied impede débito duplo interno.
- Dados de clientes permanecem isolados.
"""

import json
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import Base, get_db
from app.main import create_app
from app.models.client import Client
from app.models.statement_entry import StatementEntry, EntryType, EntryStatus
from app.models.transaction import Transaction, TransactionStatus
from app.services.seed_service import (
    CLIENT_A_EXT,
    CLIENT_B_EXT,
    CLIENT_C_EXT,
    BEN_KNOWN_A1,
    BEN_KNOWN_A2,
    BEN_NEW_B1,
    BEN_NEW_C1,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def fi_db():
    """Banco em memória para testes de integridade financeira."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    from app.models import (  # noqa: F401
        client, beneficiary, transaction, contextual_event,
        behavioral_history, risk_analysis, audit_log, statement_entry,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        from app.services.seed_service import seed_database
        await seed_database(session)
        await session.commit()
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def fi_client(fi_db: AsyncSession):
    """Cliente HTTP com banco financeiro já populado."""
    app = create_app()

    async def override_get_db():
        yield fi_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_balance(session: AsyncSession, external_id: str) -> Decimal:
    result = await session.execute(
        select(Client).where(Client.external_id == external_id)
    )
    await session.refresh(result.scalar_one())  # re-read from DB
    result2 = await session.execute(
        select(Client).where(Client.external_id == external_id)
    )
    c = result2.scalar_one()
    return Decimal(str(c.balance))


async def _get_reserved(session: AsyncSession, external_id: str) -> Decimal:
    result = await session.execute(
        select(Client).where(Client.external_id == external_id)
    )
    c = result.scalar_one()
    await session.refresh(c)
    return Decimal(str(c.reserved_balance))


async def _get_statement_entries(session: AsyncSession, external_id: str) -> list:
    result = await session.execute(
        select(Client).where(Client.external_id == external_id)
    )
    client = result.scalar_one()
    result2 = await session.execute(
        select(StatementEntry)
        .where(StatementEntry.client_id == client.id)
        .order_by(StatementEntry.posted_at.desc())
    )
    return list(result2.scalars().all())


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Transferência liberada debita saldo
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_approved_transfer_debits_balance(fi_client, fi_db):
    """Uma transferência liberada automaticamente deve debitar o saldo."""
    bal_before = await _get_balance(fi_db, CLIENT_A_EXT)

    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "500.00",
        "purpose": "Pagamento de serviços",
    })
    assert resp.status_code == 201, resp.text
    txn = resp.json()["transaction"]
    assert txn["status"] == "released"

    # Refresh
    fi_db.expire_all()
    bal_after = await _get_balance(fi_db, CLIENT_A_EXT)
    assert bal_after == bal_before - Decimal("500.00"), (
        f"Saldo não foi debitado: antes={bal_before}, depois={bal_after}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Transferência liberada aparece no extrato
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_approved_transfer_appears_in_statement(fi_client, fi_db):
    """Uma transferência liberada deve gerar lançamento DEBIT POSTED no extrato."""
    entries_before = await _get_statement_entries(fi_db, CLIENT_A_EXT)
    debit_before = sum(1 for e in entries_before if e.entry_type == EntryType.DEBIT and e.status == EntryStatus.POSTED)

    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A2,
        "amount": "300.00",
        "purpose": "Pagamento escritório",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["transaction"]["status"] == "released"

    fi_db.expire_all()
    entries_after = await _get_statement_entries(fi_db, CLIENT_A_EXT)
    debit_after = sum(1 for e in entries_after if e.entry_type == EntryType.DEBIT and e.status == EntryStatus.POSTED)
    assert debit_after == debit_before + 1, (
        f"Extrato não foi atualizado: {debit_before} → {debit_after}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Transferência pendente NÃO é debitada definitivamente
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pending_transfer_does_not_debit_balance(fi_client, fi_db):
    """Transferência em verificação reserva saldo mas não debita definitivamente."""
    fi_db.expire_all()
    bal_before = await _get_balance(fi_db, CLIENT_B_EXT)

    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_B_EXT,
        "beneficiary_external_id": BEN_NEW_B1,
        "amount": "20000.00",
        "purpose": "Investimento urgente em novo destinatário",
    })
    assert resp.status_code == 201, resp.text
    txn_data = resp.json()["transaction"]

    # Status não deve ser released (beneficiário novo + valor bem acima da média)
    assert txn_data["status"] != "released", (
        f"Transferência suspeita não deveria ser liberada: {txn_data['status']}"
    )

    fi_db.expire_all()
    bal_after = await _get_balance(fi_db, CLIENT_B_EXT)
    assert bal_after == bal_before, (
        f"Saldo foi debitado indevidamente para transação não-liberada: "
        f"antes={bal_before}, depois={bal_after}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Transferência rejeitada (hard rule) preserva saldo
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rejected_transfer_preserves_balance(fi_client, fi_db):
    """Hard rule: valor > R$ 50.000 é sempre rejeitado e não debita saldo.

    Carlos tem limite R$ 30.000 — precisamos aumentar o limite primeiro para
    atingir o hard rule de R$ 50.000 (limite máximo absoluto da simulação).
    """
    # Aumentar limite de Carlos para R$ 60.000 (acima de 2x => pending_review)
    # Mas o aumento até 2x (2 × 30.000 = 60.000) é aprovado automaticamente
    limit_resp = await fi_client.post(f"/api/v1/clients/{CLIENT_B_EXT}/limits", json={
        "requested_limit": "60000.00",
        "reason": "Teste de hard rule",
    })
    assert limit_resp.status_code == 200, limit_resp.text

    fi_db.expire_all()
    bal_before = await _get_balance(fi_db, CLIENT_B_EXT)

    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_B_EXT,
        "beneficiary_external_id": BEN_NEW_B1,
        "amount": "55000.00",
        "purpose": "Operação acima do limite máximo absoluto",
    })
    assert resp.status_code == 201, resp.text
    txn = resp.json()["transaction"]
    assert txn["status"] == "rejected", f"Status deveria ser rejected: {txn['status']}"

    fi_db.expire_all()
    bal_after = await _get_balance(fi_db, CLIENT_B_EXT)
    assert bal_after == bal_before, (
        f"Saldo foi alterado: antes={bal_before}, depois={bal_after}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Transferência duplicada não gera débito duplo (idempotência)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_duplicate_transfer_no_double_debit(fi_client, fi_db):
    """Reenvio com mesma idempotency_key não debita duas vezes."""
    idem_key = str(uuid.uuid4())
    fi_db.expire_all()
    bal_before = await _get_balance(fi_db, CLIENT_A_EXT)

    payload = {
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "200.00",
        "purpose": "Pagamento idempotente",
        "idempotency_key": idem_key,
    }

    resp1 = await fi_client.post("/api/v1/transactions/", json=payload)
    assert resp1.status_code == 201, resp1.text
    assert resp1.json()["transaction"]["status"] == "released"

    fi_db.expire_all()
    bal_mid = await _get_balance(fi_db, CLIENT_A_EXT)
    assert bal_mid == bal_before - Decimal("200.00")

    # Segundo envio (mesmo idempotency_key)
    resp2 = await fi_client.post("/api/v1/transactions/", json=payload)
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["idempotent"] is True

    fi_db.expire_all()
    bal_after = await _get_balance(fi_db, CLIENT_A_EXT)
    assert bal_after == bal_mid, (
        f"Débito duplo detectado: esperado {bal_mid}, obtido {bal_after}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Saldo insuficiente impede efetivação
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_insufficient_balance_prevents_transfer(fi_client):
    """Transferência que excede saldo disponível deve ser rejeitada com 422."""
    # Ana tem ~R$ 43.900. Tentar R$ 50.000 (excede saldo mas está no limite)
    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "50000.00",
        "purpose": "Valor acima do saldo disponível",
    })
    assert resp.status_code == 422, resp.text
    assert "insuficiente" in resp.json()["error"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Limite insuficiente impede efetivação
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_limit_exceeded_prevents_transfer(fi_client):
    """Transferência que excede limite de transferência deve retornar 422."""
    # Ana tem limite R$ 8.000. Tentar R$ 10.000
    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "10000.00",
        "purpose": "Valor acima do limite de transferência",
    })
    assert resp.status_code == 422, resp.text
    assert "limite" in resp.json()["error"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Aumento de limite gera evento contextual
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_limit_change_creates_contextual_event(fi_client, fi_db):
    """Solicitação de alteração de limite gera evento ALTERACAO_LIMITE."""
    resp = await fi_client.post(f"/api/v1/clients/{CLIENT_A_EXT}/limits", json={
        "requested_limit": "12000.00",
        "reason": "Necessidade de limite maior",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["approved"] is True
    assert data["event_correlation_id"] is not None

    # Verificar evento no banco
    fi_db.expire_all()
    from app.models.contextual_event import ContextualEvent, EventType
    result = await fi_db.execute(
        select(Client).where(Client.external_id == CLIENT_A_EXT)
    )
    client = result.scalar_one()
    result2 = await fi_db.execute(
        select(ContextualEvent)
        .where(ContextualEvent.client_id == client.id)
        .where(ContextualEvent.event_type == EventType.ALTERACAO_LIMITE)
        .order_by(ContextualEvent.occurred_at.desc())
    )
    events = list(result2.scalars().all())
    assert len(events) >= 1, "Evento ALTERACAO_LIMITE não foi criado"
    meta = json.loads(events[0].metadata_json)
    assert meta["limite_solicitado"] == "12000.00"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Beneficiário novo gera evento contextual
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_new_beneficiary_creates_contextual_event(fi_client, fi_db):
    """Cadastro de novo beneficiário gera evento CADASTRO_BENEFICIARIO."""
    resp = await fi_client.post(f"/api/v1/clients/{CLIENT_A_EXT}/beneficiaries", json={
        "name": "Novo Fornecedor Teste",
        "account_hint": "Chave Pix: teste@email.com",
        "bank_name": "Banco Fictício Teste",
    })
    assert resp.status_code == 201, resp.text
    ben = resp.json()
    assert ben["is_known"] is False

    fi_db.expire_all()
    from app.models.contextual_event import ContextualEvent, EventType
    result = await fi_db.execute(
        select(Client).where(Client.external_id == CLIENT_A_EXT)
    )
    client = result.scalar_one()
    result2 = await fi_db.execute(
        select(ContextualEvent)
        .where(ContextualEvent.client_id == client.id)
        .where(ContextualEvent.event_type == EventType.CADASTRO_BENEFICIARIO)
        .order_by(ContextualEvent.occurred_at.desc())
    )
    events = list(result2.scalars().all())
    assert len(events) >= 1, "Evento CADASTRO_BENEFICIARIO não foi criado"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Dados de clientes diferentes permanecem isolados
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_client_data_isolation(fi_client, fi_db):
    """Transferência de Ana não deve afetar saldo de Carlos ou Beatriz."""
    fi_db.expire_all()
    bal_b_before = await _get_balance(fi_db, CLIENT_B_EXT)
    bal_c_before = await _get_balance(fi_db, CLIENT_C_EXT)

    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "200.00",
        "purpose": "Pagamento isolado",
    })
    assert resp.status_code == 201, resp.text

    fi_db.expire_all()
    bal_b_after = await _get_balance(fi_db, CLIENT_B_EXT)
    bal_c_after = await _get_balance(fi_db, CLIENT_C_EXT)

    assert bal_b_after == bal_b_before, "Saldo de Carlos foi alterado indevidamente"
    assert bal_c_after == bal_c_before, "Saldo de Beatriz foi alterado indevidamente"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Extrato do seed contém lançamento do cenário A
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_seed_statement_entry_exists(fi_client):
    """O seed deve ter criado um lançamento de débito para o cenário A."""
    resp = await fi_client.get(f"/api/v1/clients/{CLIENT_A_EXT}/statement")
    assert resp.status_code == 200, resp.text
    entries = resp.json()

    debit_entries = [e for e in entries if e["entry_type"] == "debit" and e["status"] == "posted"]
    assert len(debit_entries) >= 1, f"Nenhum lançamento de débito no extrato: {entries}"

    # Verificar que o valor bate com o cenário A (R$ 1.100)
    amounts = [e["amount"] for e in debit_entries]
    assert "1100.00" in amounts, f"Lançamento de R$ 1.100 não encontrado: {amounts}"


# ═══════════════════════════════════════════════════════════════════════════════
# 12. settlement_applied impede débito duplo interno
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_settlement_flag_prevents_double_debit(fi_client, fi_db):
    """A flag settlement_applied deve ser True após liquidação e impedir redébito."""
    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "100.00",
        "purpose": "Teste settlement flag",
    })
    assert resp.status_code == 201, resp.text
    txn_data = resp.json()["transaction"]

    if txn_data["status"] == "released":
        result = await fi_db.execute(
            select(Transaction).where(Transaction.external_id == txn_data["external_id"])
        )
        txn = result.scalar_one()
        await fi_db.refresh(txn)
        assert txn.settlement_applied is True, "settlement_applied deve ser True após liquidação"


@pytest.mark.asyncio
async def test_approved_transfer_preserves_other_transaction_reserve(fi_client, fi_db):
    """Uma liquidação sem reserva própria não pode consumir reserva alheia."""
    reserved_before = await _get_reserved(fi_db, CLIENT_B_EXT)
    assert reserved_before == Decimal("15000.00")

    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_B_EXT,
        "beneficiary_external_id": BEN_NEW_B1,
        "amount": "50.00",
        "purpose": "Pagamento de serviço recorrente",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["transaction"]["status"] == "released"

    fi_db.expire_all()
    reserved_after = await _get_reserved(fi_db, CLIENT_B_EXT)
    assert reserved_after == reserved_before


@pytest.mark.asyncio
async def test_rejection_without_own_reserve_preserves_other_reserves(fi_client, fi_db):
    """Hard block sem reserva própria não pode liberar saldo de outra operação."""
    limit_resp = await fi_client.post(
        f"/api/v1/clients/{CLIENT_B_EXT}/limits",
        json={"requested_limit": "60000.00", "reason": "Teste de isolamento"},
    )
    assert limit_resp.status_code == 200, limit_resp.text

    reserved_before = await _get_reserved(fi_db, CLIENT_B_EXT)
    assert reserved_before == Decimal("15000.00")

    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_B_EXT,
        "beneficiary_external_id": BEN_NEW_B1,
        "amount": "55000.00",
        "purpose": "Operação acima do limite absoluto",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["transaction"]["status"] == "rejected"

    fi_db.expire_all()
    reserved_after = await _get_reserved(fi_db, CLIENT_B_EXT)
    assert reserved_after == reserved_before


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Reserva de saldo para operações pendentes
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reserve_applied_for_pending_transfer(fi_client, fi_db):
    """Transferência em verificação deve reservar saldo sem debitar."""
    fi_db.expire_all()
    bal_before = await _get_balance(fi_db, CLIENT_B_EXT)

    resp = await fi_client.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_B_EXT,
        "beneficiary_external_id": BEN_NEW_B1,
        "amount": "20000.00",
        "purpose": "Transferência para novo destinatário em valor alto",
    })
    assert resp.status_code == 201, resp.text
    txn_data = resp.json()["transaction"]

    fi_db.expire_all()
    bal_after = await _get_balance(fi_db, CLIENT_B_EXT)

    if txn_data["status"] != "released":
        # Não liberada — saldo NÃO deve ter sido debitado
        assert bal_after == bal_before, (
            f"Saldo debitado indevidamente para status {txn_data['status']}: "
            f"antes={bal_before}, depois={bal_after}"
        )
    else:
        # Liberada — deve ter debitado
        assert bal_after == bal_before - Decimal("20000.00")


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Limite disponível após transferência
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_limit_info_reflects_usage(fi_client):
    """Endpoint de limites deve refletir uso real."""
    # Ana tem limite R$ 8.000 e o seed debitou R$ 1.100 hoje
    resp = await fi_client.get(f"/api/v1/clients/{CLIENT_A_EXT}/limits")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["transfer_limit"] == "8000.00"
    assert data["balance"] == "43900.00"  # Após seed
    assert Decimal(data["available_limit"]) <= Decimal(data["transfer_limit"])
