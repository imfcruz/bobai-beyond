"""
API de simulação bancária — dados sintéticos para demonstração.
Não realiza movimentações financeiras reais.
"""

import random
import uuid
from datetime import datetime, timedelta

import structlog

logger = structlog.get_logger(__name__)


# ── Dados sintéticos fixos ────────────────────────────────────────────────────

SYNTHETIC_CLIENTS = {
    "client-001": {
        "name": "Ana Costa",
        "monthly_avg_transactions": 8,
        "avg_transaction_value": 1200.0,
        "known_recipients": ["rec-001", "rec-002", "rec-003"],
        "account_age_days": 1825,
        "last_limit_change_days": 180,
    },
    "client-002": {
        "name": "Carlos Mendes",
        "monthly_avg_transactions": 15,
        "avg_transaction_value": 3500.0,
        "known_recipients": ["rec-004", "rec-005"],
        "account_age_days": 730,
        "last_limit_change_days": 90,
    },
    "client-003": {
        "name": "Beatriz Santos",
        "monthly_avg_transactions": 3,
        "avg_transaction_value": 450.0,
        "known_recipients": ["rec-006"],
        "account_age_days": 2190,
        "last_limit_change_days": 365,
    },
}

SYNTHETIC_RECIPIENTS = {
    "rec-001": {"name": "Fornecedor Alpha Ltda", "risk_score": 0.05},
    "rec-002": {"name": "Escritório Beta", "risk_score": 0.05},
    "rec-003": {"name": "Serviços Gamma", "risk_score": 0.08},
    "rec-004": {"name": "Tech Delta", "risk_score": 0.06},
    "rec-005": {"name": "Logística Epsilon", "risk_score": 0.07},
    "rec-006": {"name": "Consultoria Zeta", "risk_score": 0.04},
}


# ── Cenários predefinidos para demonstração ───────────────────────────────────

DEMO_SCENARIOS = {
    "scenario_a_normal": {
        "description": "Situação A — Operação normal: transferência habitual para fornecedor conhecido",
        "client_id": "client-001",
        "recipient_id": "rec-001",
        "recipient_name": "Fornecedor Alpha Ltda",
        "amount": 1100.0,
        "purpose": "Pagamento de serviços mensais",
        "is_new_recipient": False,
        "recent_limit_change": False,
        "device_recognized": True,
    },
    "scenario_b_unusual": {
        "description": "Situação B — Operação incomum: transferência elevada para destinatário novo",
        "client_id": "client-001",
        "recipient_id": "rec-new-001",
        "recipient_name": "Empresa Desconhecida XPTO",
        "amount": 15000.0,
        "purpose": "Investimento",
        "is_new_recipient": True,
        "recent_limit_change": False,
        "device_recognized": True,
    },
    "scenario_c_social_engineering": {
        "description": "Situação C — Possível engenharia social: limite alterado + novo beneficiário + instrução de terceiro",
        "client_id": "client-001",
        "recipient_id": "rec-new-002",
        "recipient_name": "Conta Segurança BB",
        "amount": 25000.0,
        "purpose": "Uma pessoa disse ser do banco e pediu para transferir para proteger minha conta",
        "is_new_recipient": True,
        "recent_limit_change": True,
        "device_recognized": True,
    },
}


class BankSimulationService:
    """
    Simula operações bancárias com dados sintéticos.
    Todos os dados são fictícios — nenhuma operação real é realizada.
    """

    def get_client_profile(self, client_id: str) -> dict:
        profile = SYNTHETIC_CLIENTS.get(client_id)
        if profile is None:
            return {
                "name": f"Cliente {client_id}",
                "monthly_avg_transactions": 5,
                "avg_transaction_value": 1000.0,
                "known_recipients": [],
                "account_age_days": 365,
                "last_limit_change_days": 60,
            }
        return profile

    def get_recipient_info(self, recipient_id: str) -> dict:
        return SYNTHETIC_RECIPIENTS.get(
            recipient_id,
            {"name": "Destinatário desconhecido", "risk_score": 0.4},
        )

    def get_client_transaction_history(self, client_id: str, days: int = 30) -> list[dict]:
        """Gera histórico sintético de transações para o cliente."""
        profile = self.get_client_profile(client_id)
        history = []
        base_date = datetime.now()
        for i in range(profile["monthly_avg_transactions"]):
            history.append({
                "id": str(uuid.uuid4()),
                "date": (base_date - timedelta(days=random.randint(1, days))).isoformat(),
                "amount": profile["avg_transaction_value"] * random.uniform(0.7, 1.3),
                "recipient_id": random.choice(profile["known_recipients"] or ["rec-001"]),
                "status": "approved",
            })
        return sorted(history, key=lambda x: x["date"], reverse=True)

    def get_demo_scenarios(self) -> dict:
        return DEMO_SCENARIOS

    def get_demo_scenario(self, scenario_key: str) -> dict | None:
        return DEMO_SCENARIOS.get(scenario_key)
