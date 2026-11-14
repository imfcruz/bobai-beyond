"""
Testes de clientes — criação, consulta e integridade.
"""

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ClientRiskProfile
from app.repositories.client_repo import ClientRepository
from app.services.seed_service import CLIENT_A_EXT, CLIENT_B_EXT, CLIENT_C_EXT


@pytest.mark.asyncio
async def test_seed_creates_three_clients(seeded_db):
    db, summary = seeded_db
    repo = ClientRepository(db)
    clients = await repo.list_all()
    assert len(clients) == 3
    assert summary["clients"] == 3


@pytest.mark.asyncio
async def test_clients_have_correct_names(seeded_db):
    db, _ = seeded_db
    repo = ClientRepository(db)
    clients = await repo.list_all()
    names = {c.name for c in clients}
    assert names == {"Ana Costa", "Carlos Mendes", "Beatriz Santos"}


@pytest.mark.asyncio
async def test_get_client_by_external_id(seeded_db):
    db, _ = seeded_db
    repo = ClientRepository(db)
    client = await repo.get_by_external_id(CLIENT_A_EXT)
    assert client is not None
    assert client.name == "Ana Costa"
    assert client.risk_profile == ClientRiskProfile.LOW


@pytest.mark.asyncio
async def test_client_balance_is_decimal(seeded_db):
    db, _ = seeded_db
    repo = ClientRepository(db)
    client = await repo.get_by_external_id(CLIENT_A_EXT)
    assert isinstance(client.balance, Decimal)
    assert client.balance > Decimal("0")


@pytest.mark.asyncio
async def test_client_transfer_limit_is_decimal(seeded_db):
    db, _ = seeded_db
    repo = ClientRepository(db)
    client = await repo.get_by_external_id(CLIENT_A_EXT)
    assert isinstance(client.transfer_limit, Decimal)
    assert client.transfer_limit > Decimal("0")


@pytest.mark.asyncio
async def test_client_not_found_returns_none(seeded_db):
    db, _ = seeded_db
    repo = ClientRepository(db)
    result = await repo.get_by_external_id("nao-existe")
    assert result is None


@pytest.mark.asyncio
async def test_list_clients_endpoint(seeded_client):
    ac, _ = seeded_client
    response = await ac.get("/api/v1/clients/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert all("external_id" in c for c in data)


@pytest.mark.asyncio
async def test_get_client_endpoint(seeded_client):
    ac, _ = seeded_client
    response = await ac.get(f"/api/v1/clients/{CLIENT_A_EXT}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ana Costa"
    assert "balance" in data
    assert "transfer_limit" in data


@pytest.mark.asyncio
async def test_get_client_not_found_returns_404(seeded_client):
    ac, _ = seeded_client
    response = await ac.get("/api/v1/clients/cliente-inexistente")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_behavioral_history_endpoint(seeded_client):
    ac, _ = seeded_client
    response = await ac.get(f"/api/v1/clients/{CLIENT_A_EXT}/behavioral-history")
    assert response.status_code == 200
    data = response.json()
    assert "avg_transfer_value" in data
    assert float(data["avg_transfer_value"]) == 1200.0
