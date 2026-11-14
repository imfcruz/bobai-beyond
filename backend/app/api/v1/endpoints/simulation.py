"""
Endpoints da API de simulação bancária.
"""

import structlog
from fastapi import APIRouter

from app.services.bank_simulation import BankSimulationService

logger = structlog.get_logger(__name__)

router = APIRouter()
_service = BankSimulationService()


@router.get(
    "/scenarios",
    summary="Listar cenários de demonstração",
    tags=["Bank Simulation"],
)
async def list_scenarios() -> dict:
    """Retorna os cenários predefinidos para demonstração do MVP."""
    return {
        "scenarios": {
            key: {"description": val["description"]}
            for key, val in _service.get_demo_scenarios().items()
        }
    }


@router.get(
    "/scenarios/{scenario_key}",
    summary="Obter cenário de demonstração",
    tags=["Bank Simulation"],
)
async def get_scenario(scenario_key: str) -> dict:
    """Retorna os dados de um cenário específico."""
    scenario = _service.get_demo_scenario(scenario_key)
    if scenario is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Cenário '{scenario_key}' não encontrado.")
    return scenario


@router.get(
    "/clients/{client_id}/profile",
    summary="Perfil sintético do cliente",
    tags=["Bank Simulation"],
)
async def get_client_profile(client_id: str) -> dict:
    """Retorna o perfil sintético de um cliente para fins de simulação."""
    return _service.get_client_profile(client_id)


@router.get(
    "/clients/{client_id}/history",
    summary="Histórico sintético de transações",
    tags=["Bank Simulation"],
)
async def get_client_history(client_id: str, days: int = 30) -> dict:
    """Retorna histórico simulado de transações do cliente."""
    return {
        "client_id": client_id,
        "days": days,
        "transactions": _service.get_client_transaction_history(client_id, days),
    }
