"""
Testes de seed/reset — reinicialização dos dados sintéticos.
"""

import pytest

from app.repositories.client_repo import ClientRepository
from app.repositories.transaction_repo import TransactionRepository
from app.services.seed_service import seed_database, TXN_A, TXN_B, TXN_C
from app.services.seed_service import CLIENT_A_EXT


@pytest.mark.asyncio
async def test_seed_creates_expected_summary(seeded_db):
    db, summary = seeded_db
    assert summary["clients"] == 3
    assert summary["beneficiaries"] == 30
    assert summary["transactions"] == 3
    assert summary["contextual_events"] == 10
    assert summary["behavioral_histories"] == 3
    assert summary["risk_analyses"] == 3


@pytest.mark.asyncio
async def test_seed_is_idempotent_when_reset(db_session):
    """Chamar seed duas vezes deve resultar nos mesmos 3 clientes (não duplicar)."""
    await seed_database(db_session)
    await db_session.commit()
    await seed_database(db_session)
    await db_session.commit()

    repo = ClientRepository(db_session)
    clients = await repo.list_all()
    assert len(clients) == 3


@pytest.mark.asyncio
async def test_reset_endpoint_returns_200(seeded_client):
    ac, _ = seeded_client
    response = await ac.post("/api/v1/demo/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["clients"] == 3
    assert "message" in data


@pytest.mark.asyncio
async def test_reset_clears_and_repopulates(seeded_client):
    ac, _ = seeded_client
    # Após reset, os três cenários devem existir
    await ac.post("/api/v1/demo/reset")
    for txn_id in [TXN_A, TXN_B, TXN_C]:
        response = await ac.get(f"/api/v1/transactions/{txn_id}")
        assert response.status_code == 200, f"Transação {txn_id} não encontrada após reset"


@pytest.mark.asyncio
async def test_demo_status_endpoint(seeded_client):
    ac, _ = seeded_client
    response = await ac.get("/api/v1/demo/status")
    assert response.status_code == 200
    data = response.json()
    assert data["seeded"] is True
    assert data["clients"] == 3


@pytest.mark.asyncio
async def test_demo_account_has_ten_contacts_and_favorites(seeded_client):
    ac, _ = seeded_client
    response = await ac.get(f"/api/v1/beneficiaries/client/{CLIENT_A_EXT}")
    assert response.status_code == 200
    contacts = response.json()
    assert len(contacts) == 10
    assert sum(item["is_favorite"] for item in contacts) >= 3


@pytest.mark.asyncio
async def test_contact_favorite_can_be_toggled(seeded_client):
    ac, _ = seeded_client
    contacts = (await ac.get(f"/api/v1/beneficiaries/client/{CLIENT_A_EXT}")).json()
    contact = next(item for item in contacts if not item["is_favorite"])
    response = await ac.patch(
        f"/api/v1/beneficiaries/{contact['external_id']}/favorite",
        json={"is_favorite": True},
    )
    assert response.status_code == 200
    assert response.json()["is_favorite"] is True
