"""
Testes do serviço de simulação bancária.
"""

import pytest

from app.services.bank_simulation import BankSimulationService, DEMO_SCENARIOS


def test_get_known_client_profile():
    service = BankSimulationService()
    profile = service.get_client_profile("client-001")
    assert profile["name"] == "Ana Costa"
    assert profile["avg_transaction_value"] > 0


def test_get_unknown_client_returns_default():
    service = BankSimulationService()
    profile = service.get_client_profile("nonexistent-client")
    assert "name" in profile
    assert "avg_transaction_value" in profile


def test_get_demo_scenarios_returns_all():
    service = BankSimulationService()
    scenarios = service.get_demo_scenarios()
    assert "scenario_a_normal" in scenarios
    assert "scenario_b_unusual" in scenarios
    assert "scenario_c_social_engineering" in scenarios


def test_get_demo_scenario_c_has_social_engineering_markers():
    service = BankSimulationService()
    scenario = service.get_demo_scenario("scenario_c_social_engineering")
    assert scenario is not None
    assert scenario["is_new_recipient"] is True
    assert scenario["recent_limit_change"] is True


def test_get_demo_scenario_none_for_unknown():
    service = BankSimulationService()
    assert service.get_demo_scenario("nonexistent") is None


def test_transaction_history_returns_list():
    service = BankSimulationService()
    history = service.get_client_transaction_history("client-001", days=30)
    assert isinstance(history, list)
    assert len(history) > 0
