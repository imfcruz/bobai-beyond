"""
Testes do endpoint de health check.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.config import settings


@pytest.mark.asyncio
async def test_health_check_returns_200():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"{settings.API_V1_PREFIX}/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_check_response_schema():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"{settings.API_V1_PREFIX}/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data
    assert "database" in data
    assert "llm_provider" in data


@pytest.mark.asyncio
async def test_health_check_llm_provider_is_mock():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"{settings.API_V1_PREFIX}/health")
    data = response.json()
    assert data["llm_provider"] == "mock"
