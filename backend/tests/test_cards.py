"""Fluxos de cartão, limite humano e Pix no crédito."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.card import CreditCard
from app.models.client import Client
from app.services.seed_service import BEN_KNOWN_A1, CLIENT_A_EXT


async def _ana_card(db) -> CreditCard:
    client = (
        await db.execute(select(Client).where(Client.external_id == CLIENT_A_EXT))
    ).scalar_one()
    return (
        await db.execute(select(CreditCard).where(CreditCard.client_id == client.id))
    ).scalar_one()


@pytest.mark.asyncio
async def test_cards_endpoint_returns_available_credit(seeded_client):
    http, _ = seeded_client
    response = await http.get(f"/api/v1/cards/client/{CLIENT_A_EXT}")
    assert response.status_code == 200, response.text
    card = response.json()[0]
    assert card["credit_limit"] == "12000.00"
    assert card["used_credit"] == "2850.00"
    assert card["available_credit"] == "9150.00"


@pytest.mark.asyncio
async def test_credit_pix_consumes_card_not_account_balance(seeded_client, seeded_db):
    http, _ = seeded_client
    db, _ = seeded_db
    card = await _ana_card(db)
    client = (
        await db.execute(select(Client).where(Client.external_id == CLIENT_A_EXT))
    ).scalar_one()
    balance_before = Decimal(str(client.balance))
    used_before = Decimal(str(card.used_credit))

    response = await http.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "200.00",
        "purpose": "Pagamento de almoço",
        "funding_source": "credit",
        "card_external_id": card.external_id,
    })
    assert response.status_code == 201, response.text
    assert response.json()["transaction"]["funding_source"] == "credit"

    await db.refresh(client)
    await db.refresh(card)
    assert Decimal(str(client.balance)) == balance_before
    assert Decimal(str(card.used_credit)) == used_before + Decimal("200.00")


@pytest.mark.asyncio
async def test_limit_request_requires_human_and_updates_card(seeded_client, seeded_db):
    http, _ = seeded_client
    db, _ = seeded_db
    card = await _ana_card(db)

    submitted = await http.post(f"/api/v1/cards/{card.external_id}/limit-requests", json={
        "requested_limit": "18000.00",
        "reason": "Viagem e despesas planejadas",
    })
    assert submitted.status_code == 201, submitted.text
    request = submitted.json()
    assert request["status"] == "pending_review"
    assert request["agent_assessment"]

    reviewed = await http.post(
        f"/api/v1/cards/limit-requests/{request['external_id']}/review/approve",
        json={"reviewer_id": "funcionario-042", "reviewer_notes": "Renda e histórico conferidos."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    await db.refresh(card)
    assert Decimal(str(card.credit_limit)) == Decimal("18000.00")


@pytest.mark.asyncio
async def test_credit_pix_after_limit_approval_is_flagged(seeded_client, seeded_db):
    http, _ = seeded_client
    db, _ = seeded_db
    card = await _ana_card(db)
    submitted = await http.post(f"/api/v1/cards/{card.external_id}/limit-requests", json={
        "requested_limit": "20000.00", "reason": "Compra planejada",
    })
    request_id = submitted.json()["external_id"]
    approved = await http.post(
        f"/api/v1/cards/limit-requests/{request_id}/review/approve",
        json={"reviewer_id": "funcionario-007"},
    )
    assert approved.status_code == 200, approved.text

    response = await http.post("/api/v1/transactions/", json={
        "client_external_id": CLIENT_A_EXT,
        "beneficiary_external_id": BEN_KNOWN_A1,
        "amount": "4000.00",
        "purpose": "Pix usando novo limite",
        "funding_source": "credit",
        "card_external_id": card.external_id,
    })
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["transaction"]["recent_limit_change"] is True
    assert "credit_pix_after_limit_increase" in data["analysis"]["fraud_agent_result"]
