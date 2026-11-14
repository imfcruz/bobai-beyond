"""
Utilitário para determinar o AgentMode em vigor.

mock/rules → RULES_MODE (nunca apresentado como IA real)
bob/watsonx → AI_MODE
AGENT_MODE=auto → determinado pelo provider
AGENT_MODE=AI_MODE/RULES_MODE → força o modo explicitamente
"""
from app.agents.base import AgentMode
from app.core.config import settings


def resolve_agent_mode(provider_name: str) -> AgentMode:
    """Determina o AgentMode efetivo com base nas configurações."""
    setting = settings.AGENT_MODE
    if setting == "AI_MODE":
        return AgentMode.AI_MODE
    if setting == "RULES_MODE":
        return AgentMode.RULES_MODE
    # auto: mock → RULES_MODE, qualquer outro → AI_MODE
    return AgentMode.RULES_MODE if provider_name in ("mock",) else AgentMode.AI_MODE
