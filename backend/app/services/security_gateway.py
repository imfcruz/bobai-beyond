"""
Security Gateway — ponto de controle final antes de alterar o status da transação.

Responsável por:
- Validar se a ação solicitada é permitida pela política.
- Impedir transições de estado não autorizadas.
- Bloquear ações não permitidas (ex: aprovar uma transação bloqueada).
- Registrar todas as decisões com rastreabilidade completa.
- Exigir autorização humana quando necessário.
- Garantir que falhas nunca produzam aprovação automática.

O Gateway NÃO é um agente — é uma camada de controle de política.
A LLM não tem acesso direto a este componente.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import structlog

from app.models.risk_analysis import RecommendedAction
from app.models.transaction import RiskLevel, TransactionStatus
from app.services.decision_engine import Decision, POLICY_VERSION

logger = structlog.get_logger(__name__)

# ── Ações autorizadas por nível de risco ─────────────────────────────────────
# Define quais ações o gateway permite para cada nível de risco.
# Estas regras NÃO podem ser contornadas por output de LLM.
_ALLOWED_ACTIONS_BY_LEVEL: dict[RiskLevel, set[RecommendedAction]] = {
    RiskLevel.LOW:      {RecommendedAction.APPROVE},
    RiskLevel.MEDIUM:   {RecommendedAction.REQUEST_CONFIRMATION},
    RiskLevel.HIGH:     {RecommendedAction.REQUEST_CONFIRMATION, RecommendedAction.ESCALATE_TO_HUMAN},
    RiskLevel.CRITICAL: {RecommendedAction.ESCALATE_TO_HUMAN, RecommendedAction.BLOCK},
}

# Ações que sempre exigem revisão humana (não podem ser aprovadas automaticamente)
_REQUIRES_HUMAN_REVIEW_ACTIONS = {
    RecommendedAction.ESCALATE_TO_HUMAN,
}

# Estados de onde aprovação automática é proibida
_NO_AUTO_APPROVE_FROM = {
    TransactionStatus.AWAITING_CONFIRMATION,
    TransactionStatus.HUMAN_REVIEW_PENDING,
    TransactionStatus.ESCALATED_TO_HUMAN,
}


@dataclass
class GatewayResponse:
    """Resposta do Security Gateway."""

    authorized: bool                        # True = pode prosseguir com o status decidido
    final_status: TransactionStatus         # Status final recomendado
    final_action: RecommendedAction         # Ação recomendada
    risk_level: RiskLevel
    risk_score: float
    requires_confirmation: bool             # True = requer confirmação contextual do cliente
    requires_human_review: bool             # True = requer revisão humana
    gateway_reasoning: str
    flags: list[str]

    # Rastreabilidade (Etapa 6)
    policy_version: str = POLICY_VERSION
    divergence_detected: bool = False
    unauthorized_action_attempted: bool = False  # True = ação não permitida foi tentada

    def to_dict(self) -> dict:
        return {
            "authorized": self.authorized,
            "final_status": self.final_status.value,
            "final_action": self.final_action.value,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "requires_confirmation": self.requires_confirmation,
            "requires_human_review": self.requires_human_review,
            "gateway_reasoning": self.gateway_reasoning,
            "flags": self.flags,
            "policy_version": self.policy_version,
            "divergence_detected": self.divergence_detected,
            "unauthorized_action_attempted": self.unauthorized_action_attempted,
        }


class SecurityGateway:
    """
    Ponto de controle de segurança final.

    Valida a decisão do motor e emite autorização definitiva.
    Garante rastreabilidade e impede transições não autorizadas.

    INVARIANTE: Uma transação NUNCA passa de estado de alto risco
    para RELEASED sem revisão humana explícita.
    """

    def evaluate(self, decision: Decision) -> GatewayResponse:
        """
        Avalia a decisão do motor e retorna a resposta do Gateway.

        Verificações de segurança:
        1. BLOCK nunca é autorizado (authorized=False).
        2. ESCALATE sempre exige revisão humana.
        3. REQUEST_CONFIRMATION autorizado mas requer etapa adicional.
        4. APPROVE autorizado apenas para LOW risk.
        5. Ação não permitida para o nível de risco → registrada e recusada.
        """
        action = decision.recommended_action
        level = decision.risk_level
        unauthorized_action_attempted = False

        # Verificar se a ação é permitida para o nível de risco
        allowed = _ALLOWED_ACTIONS_BY_LEVEL.get(level, set())
        if action not in allowed:
            # Ação não permitida — registrar e forçar ação conservadora
            unauthorized_action_attempted = True
            logger.error(
                "SecurityGateway: UNAUTHORIZED ACTION ATTEMPTED",
                action=action,
                level=level,
                allowed=list(a.value for a in allowed),
                policy=POLICY_VERSION,
            )
            # Forçar para ação mais conservadora permitida
            if RecommendedAction.ESCALATE_TO_HUMAN in allowed:
                action = RecommendedAction.ESCALATE_TO_HUMAN
            elif RecommendedAction.REQUEST_CONFIRMATION in allowed:
                action = RecommendedAction.REQUEST_CONFIRMATION
            else:
                action = RecommendedAction.BLOCK

        if action == RecommendedAction.BLOCK:
            response = GatewayResponse(
                authorized=False,
                final_status=TransactionStatus.REJECTED,
                final_action=RecommendedAction.BLOCK,
                risk_level=level,
                risk_score=decision.risk_score,
                requires_confirmation=False,
                requires_human_review=False,
                gateway_reasoning=(
                    f"BLOQUEADO pelo Security Gateway [{POLICY_VERSION}]. "
                    f"{decision.reasoning}"
                ),
                flags=decision.flags,
                policy_version=POLICY_VERSION,
                divergence_detected=decision.divergence_detected,
                unauthorized_action_attempted=unauthorized_action_attempted,
            )

        elif action == RecommendedAction.ESCALATE_TO_HUMAN:
            response = GatewayResponse(
                authorized=True,
                final_status=TransactionStatus.HUMAN_REVIEW_PENDING,
                final_action=RecommendedAction.ESCALATE_TO_HUMAN,
                risk_level=level,
                risk_score=decision.risk_score,
                requires_confirmation=False,
                requires_human_review=True,
                gateway_reasoning=(
                    f"Encaminhado para revisão humana [{POLICY_VERSION}]. "
                    f"{decision.reasoning}"
                ),
                flags=decision.flags,
                policy_version=POLICY_VERSION,
                divergence_detected=decision.divergence_detected,
                unauthorized_action_attempted=unauthorized_action_attempted,
            )

        elif action == RecommendedAction.REQUEST_CONFIRMATION:
            response = GatewayResponse(
                authorized=True,
                final_status=TransactionStatus.AWAITING_CONFIRMATION,
                final_action=RecommendedAction.REQUEST_CONFIRMATION,
                risk_level=level,
                risk_score=decision.risk_score,
                requires_confirmation=True,
                requires_human_review=False,
                gateway_reasoning=(
                    f"Confirmação contextual necessária [{POLICY_VERSION}]. "
                    f"{decision.reasoning}"
                ),
                flags=decision.flags,
                policy_version=POLICY_VERSION,
                divergence_detected=decision.divergence_detected,
                unauthorized_action_attempted=unauthorized_action_attempted,
            )

        else:  # APPROVE
            response = GatewayResponse(
                authorized=True,
                final_status=TransactionStatus.RELEASED,
                final_action=RecommendedAction.APPROVE,
                risk_level=level,
                risk_score=decision.risk_score,
                requires_confirmation=False,
                requires_human_review=False,
                gateway_reasoning=(
                    f"Aprovado pelo Security Gateway [{POLICY_VERSION}]. "
                    f"{decision.reasoning}"
                ),
                flags=decision.flags,
                policy_version=POLICY_VERSION,
                divergence_detected=decision.divergence_detected,
                unauthorized_action_attempted=unauthorized_action_attempted,
            )

        logger.info(
            "SecurityGateway evaluated",
            authorized=response.authorized,
            final_status=response.final_status.value,
            risk_score=response.risk_score,
            policy=POLICY_VERSION,
            divergence=response.divergence_detected,
            unauthorized_attempted=unauthorized_action_attempted,
        )
        return response

    def validate_human_action(
        self,
        current_status: TransactionStatus,
        action: str,
        reviewer_id: str,
    ) -> tuple[bool, str]:
        """
        Valida se uma ação de revisão humana é permitida para o status atual.

        Retorna (allowed, reasoning).
        A IA não pode chamar este método fingindo ser o revisor.
        """
        if current_status not in (
            TransactionStatus.HUMAN_REVIEW_PENDING,
            TransactionStatus.ESCALATED_TO_HUMAN,
        ):
            return False, (
                f"Ação humana não permitida em status '{current_status.value}'. "
                f"Apenas transações em HUMAN_REVIEW_PENDING ou ESCALATED_TO_HUMAN "
                f"podem ser revisadas."
            )

        if action not in ("approve", "reject"):
            return False, f"Ação '{action}' não reconhecida. Use 'approve' ou 'reject'."

        if not reviewer_id or not reviewer_id.strip():
            return False, "reviewer_id é obrigatório para ações de revisão humana."

        # Verifica que o reviewer não é um identificador de sistema/IA
        forbidden_ids = ["ai", "llm", "bot", "auto", "system", "agent", "model", "watsonx"]
        if any(f in reviewer_id.lower() for f in forbidden_ids):
            return False, (
                f"reviewer_id '{reviewer_id}' não é permitido — "
                f"a IA não pode simular revisão humana."
            )

        return True, f"Ação '{action}' autorizada pelo revisor '{reviewer_id}'."
