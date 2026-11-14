"""
Testes do cliente LLM.

Cobrem:
- MockLLMClient: complete e complete_json
- LLMClientFactory: criação por provider name
- model_identifier: identificador público do modelo
- reset_llm_client: reset do singleton para testes
- Provedor desconhecido levanta ValueError
"""

import asyncio
import json

import pytest

from app.core.config import settings
from app.services.llm_client import (
    BobShellLLMClient,
    LLMClientFactory,
    MockLLMClient,
    get_llm_client,
    reset_llm_client,
)


@pytest.mark.asyncio
async def test_mock_llm_complete_returns_string():
    client = MockLLMClient()
    result = await client.complete("teste")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_mock_llm_complete_json_returns_dict():
    client = MockLLMClient()
    result = await client.complete_json("teste")
    assert isinstance(result, dict)
    assert "risk_score" in result or "risk_level" in result


@pytest.mark.asyncio
async def test_mock_llm_complete_json_has_explanation():
    client = MockLLMClient()
    result = await client.complete_json("teste")
    assert "explanation" in result
    assert len(result["explanation"]) > 0


def test_llm_factory_creates_mock():
    client = LLMClientFactory.create("mock")
    assert client.provider_name == "mock"


def test_llm_factory_unknown_provider_raises():
    with pytest.raises(ValueError, match="desconhecido"):
        LLMClientFactory.create("unknown_provider")


def test_llm_factory_exposes_only_project_providers():
    assert set(LLMClientFactory._registry) == {"mock", "bob", "watsonx"}


def test_llm_factory_error_lists_supported_providers():
    with pytest.raises(ValueError) as exc_info:
        LLMClientFactory.create("external_provider")
    message = str(exc_info.value)
    assert "mock" in message
    assert "bob" in message
    assert "watsonx" in message


def test_mock_llm_model_identifier():
    """model_identifier deve ser uma string pública sem credenciais."""
    client = MockLLMClient()
    assert isinstance(client.model_identifier, str)
    assert len(client.model_identifier) > 0
    assert "mock" in client.model_identifier.lower() or "rules" in client.model_identifier.lower()


def test_llm_factory_model_identifier_present():
    """Factory deve criar cliente com model_identifier."""
    client = LLMClientFactory.create("mock")
    assert hasattr(client, "model_identifier")
    identifier = client.model_identifier
    assert isinstance(identifier, str)
    assert len(identifier) > 0


def test_reset_llm_client_forces_new_instance():
    """reset_llm_client deve limpar o singleton."""
    reset_llm_client()
    client1 = get_llm_client()
    reset_llm_client()
    client2 = get_llm_client()
    # Após reset, nova instância é criada
    assert client1 is not client2


def test_model_identifier_does_not_contain_credentials():
    """model_identifier nunca deve expor API keys ou tokens."""
    client = LLMClientFactory.create("mock")
    identifier = client.model_identifier
    forbidden = ["sk-", "Bearer ", "apikey", "password", "secret"]
    for token in forbidden:
        assert token not in identifier, f"Credencial '{token}' encontrada no model_identifier"


def test_bob_client_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "BOB_API_KEY", "")
    with pytest.raises(ValueError, match="BOB_API_KEY"):
        BobShellLLMClient()


def test_bob_factory_creates_client_without_model(monkeypatch):
    monkeypatch.setattr(settings, "BOB_API_KEY", "bob-test-key")
    monkeypatch.setattr("app.services.llm_client.shutil.which", lambda _command: "/usr/bin/bob")
    client = LLMClientFactory.create("bob")
    assert client.provider_name == "bob"
    assert client.model_identifier == "ibm-bob/team-inference"


@pytest.mark.asyncio
async def test_bob_client_uses_environment_without_key_in_arguments(monkeypatch):
    secret = "bob-secret-that-must-not-be-an-argument"
    monkeypatch.setattr(settings, "BOB_API_KEY", secret)
    monkeypatch.setattr(settings, "BOB_TEAM_ID", "")
    monkeypatch.setattr("app.services.llm_client.shutil.which", lambda _command: "/usr/bin/bob")

    captured: dict = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            payload = {
                "status": "success",
                "last_message": json.dumps({"risk_level": "LOW"}),
            }
            return json.dumps(payload).encode(), b""

    async def fake_subprocess(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

    client = BobShellLLMClient()
    result = await client.complete_json("analise")

    assert result == {"risk_level": "LOW"}
    assert secret not in captured["args"]
    assert captured["env"]["BOB_API_KEY"] == secret
