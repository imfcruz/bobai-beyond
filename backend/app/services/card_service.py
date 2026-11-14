"""Gestão simulada de cartão e revisão humana de limite de crédito."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, ValidationError
from app.models.audit_log import AuditLog
from app.models.card import CardStatus, CreditCard, CreditLimitRequest, CreditLimitRequestStatus
from app.models.client import Client
from app.models.contextual_event import ContextualEvent, EventType


class CardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_client_cards(self, client_external_id: str) -> list[CreditCard]:
        client = await self._get_client(client_external_id)
        result = await self.db.execute(
            select(CreditCard).where(CreditCard.client_id == client.id).order_by(CreditCard.id)
        )
        return list(result.scalars().all())

    async def get_card(self, card_external_id: str) -> CreditCard:
        result = await self.db.execute(
            select(CreditCard).where(CreditCard.external_id == card_external_id)
        )
        card = result.scalar_one_or_none()
        if card is None:
            raise NotFoundError("CreditCard", card_external_id)
        return card

    async def submit_limit_request(
        self, card_external_id: str, requested_limit_raw: str, reason: str | None
    ) -> CreditLimitRequest:
        card = await self.get_card(card_external_id)
        if card.status != CardStatus.ACTIVE:
            raise ValidationError("O cartão precisa estar ativo para solicitar novo limite.")
        try:
            requested = Decimal(requested_limit_raw).quantize(Decimal("0.01"))
        except InvalidOperation as exc:
            raise ValidationError("O limite solicitado é inválido.") from exc
        current = Decimal(str(card.credit_limit))
        if requested <= current:
            raise ValidationError("O novo limite deve ser maior que o limite atual.")
        if requested > Decimal("250000.00"):
            raise ValidationError("O limite máximo desta simulação é R$ 250.000,00.")

        pending = await self.db.execute(
            select(CreditLimitRequest).where(
                CreditLimitRequest.card_id == card.id,
                CreditLimitRequest.status == CreditLimitRequestStatus.PENDING_REVIEW,
            )
        )
        if pending.scalar_one_or_none() is not None:
            raise ValidationError("Já existe uma solicitação de limite aguardando análise.")

        assessment = await self._build_agent_assessment(card, requested, reason or "")
        request = CreditLimitRequest(
            external_id=str(uuid.uuid4()), client_id=card.client_id, card=card,
            current_limit=current, requested_limit=requested, reason=reason,
            risk_score=assessment["overall_risk_score"], risk_level=assessment["risk_level"],
            agent_assessment=json.dumps(assessment, ensure_ascii=False),
        )
        self.db.add(request)
        await self.db.flush()

        correlation_id = str(uuid.uuid4())[:12]
        self.db.add(ContextualEvent(
            client_id=card.client_id,
            event_type=EventType.SOLICITACAO_AUMENTO_LIMITE_CREDITO,
            correlation_id=correlation_id,
            metadata_json=json.dumps({
                "request_external_id": request.external_id,
                "card_external_id": card.external_id,
                "current_limit": str(current), "requested_limit": str(requested),
            }),
        ))
        self.db.add(AuditLog(
            transaction_id=None, component="credit_limit_orchestrator",
            agent_name="limit_risk_agents", action="credit_limit_request_analyzed",
            event="CREDIT_LIMIT_REQUESTED", result=CreditLimitRequestStatus.PENDING_REVIEW.value,
            reasoning="Análise automatizada informativa; decisão reservada ao funcionário.",
            risk_score=assessment["overall_risk_score"], flags=json.dumps(assessment["flags"]),
            correlation_id=correlation_id, policy_version="credit-limit-v1",
            agent_contributions=json.dumps(assessment["agents"], ensure_ascii=False),
        ))
        await self.db.flush()
        return request

    async def list_limit_requests(
        self, status: CreditLimitRequestStatus | None = None,
        client_external_id: str | None = None,
    ) -> list[CreditLimitRequest]:
        stmt = select(CreditLimitRequest).options(
            selectinload(CreditLimitRequest.card), selectinload(CreditLimitRequest.client)
        )
        if status is not None:
            stmt = stmt.where(CreditLimitRequest.status == status)
        if client_external_id is not None:
            client = await self._get_client(client_external_id)
            stmt = stmt.where(CreditLimitRequest.client_id == client.id)
        result = await self.db.execute(stmt.order_by(CreditLimitRequest.created_at.desc()))
        return list(result.scalars().all())

    async def review_limit_request(
        self, request_external_id: str, action: str, reviewer_id: str,
        reviewer_notes: str | None,
    ) -> CreditLimitRequest:
        if action not in {"approve", "reject"}:
            raise ValidationError("A ação deve ser 'approve' ou 'reject'.")
        self._validate_human_reviewer(reviewer_id)
        result = await self.db.execute(
            select(CreditLimitRequest)
            .where(CreditLimitRequest.external_id == request_external_id)
            .options(selectinload(CreditLimitRequest.card))
        )
        request = result.scalar_one_or_none()
        if request is None:
            raise NotFoundError("CreditLimitRequest", request_external_id)
        if request.status != CreditLimitRequestStatus.PENDING_REVIEW:
            raise ValidationError("Esta solicitação já foi revisada.")

        approved = action == "approve"
        request.status = CreditLimitRequestStatus.APPROVED if approved else CreditLimitRequestStatus.REJECTED
        request.reviewer_id = reviewer_id.strip()
        request.reviewer_notes = reviewer_notes
        request.reviewed_at = datetime.now(timezone.utc)
        if approved:
            request.card.credit_limit = request.requested_limit
            self.db.add(request.card)

        correlation_id = str(uuid.uuid4())[:12]
        event_type = EventType.AUMENTO_LIMITE_CREDITO_APROVADO if approved else EventType.AUMENTO_LIMITE_CREDITO_REJEITADO
        self.db.add(ContextualEvent(
            client_id=request.client_id, event_type=event_type, correlation_id=correlation_id,
            metadata_json=json.dumps({
                "request_external_id": request.external_id,
                "card_external_id": request.card.external_id,
                "new_limit": str(request.requested_limit) if approved else None,
                "reviewer_id": reviewer_id.strip(),
            }),
        ))
        self.db.add(AuditLog(
            transaction_id=None, component="human_credit_review",
            agent_name=f"human_reviewer:{reviewer_id.strip()}", action=f"credit_limit_{action}",
            event="CREDIT_LIMIT_REVIEWED", result=request.status.value,
            reasoning=reviewer_notes or "Decisão humana registrada.", risk_score=request.risk_score,
            flags=json.dumps(["human_review", f"reviewer:{reviewer_id.strip()}"]),
            correlation_id=correlation_id, policy_version="credit-limit-v1",
        ))
        self.db.add(request)
        await self.db.flush()
        return request

    async def _build_agent_assessment(self, card: CreditCard, requested: Decimal, reason: str) -> dict:
        client = await self.db.get(Client, card.client_id)
        current = max(Decimal("1.00"), Decimal(str(card.credit_limit)))
        ratio = float(requested / current)
        pressure_words = ("urgente", "agora", "funcionário", "funcionario", "ligou", "segurança")
        fraud_score, fraud_flags = 0.08, []
        if ratio >= 4:
            fraud_score += 0.45
            fraud_flags.append("requested_limit_far_above_current")
        elif ratio >= 2:
            fraud_score += 0.22
            fraud_flags.append("requested_limit_above_current")
        if any(word in reason.lower() for word in pressure_words):
            fraud_score += 0.30
            fraud_flags.append("possible_social_engineering_language")

        behavioral_score, behavioral_flags = 0.10, []
        if client and requested > Decimal(str(client.balance)) * Decimal("1.5"):
            behavioral_score += 0.30
            behavioral_flags.append("limit_disproportionate_to_account_balance")
        if client and client.risk_profile.value == "high":
            behavioral_score += 0.25
            behavioral_flags.append("high_risk_profile")
        intention_score = 0.08 if reason.strip() else 0.22
        intention_flags = [] if reason.strip() else ["reason_not_provided"]
        agents = [
            {"agent_name": "fraud_agent", "risk_score": min(1.0, fraud_score), "flags": fraud_flags,
             "explanation": "Avalia proporção do aumento e sinais de engenharia social."},
            {"agent_name": "behavioral_agent", "risk_score": min(1.0, behavioral_score), "flags": behavioral_flags,
             "explanation": "Compara o pedido ao perfil financeiro sintético do cliente."},
            {"agent_name": "intention_agent", "risk_score": intention_score, "flags": intention_flags,
             "explanation": "Analisa a clareza da finalidade declarada sem tratá-la como verdade."},
        ]
        overall = round(sum(agent["risk_score"] for agent in agents) / len(agents), 3)
        risk_level = "high" if overall >= 0.60 else "medium" if overall >= 0.30 else "low"
        flags = [flag for agent in agents for flag in agent["flags"]]
        return {"overall_risk_score": overall, "risk_level": risk_level, "flags": flags,
                "agents": agents, "human_review_required": True,
                "recommendation": "review_carefully" if overall >= 0.30 else "eligible_for_review"}

    async def _get_client(self, external_id: str) -> Client:
        result = await self.db.execute(select(Client).where(Client.external_id == external_id))
        client = result.scalar_one_or_none()
        if client is None:
            raise NotFoundError("Client", external_id)
        return client

    @staticmethod
    def _validate_human_reviewer(reviewer_id: str) -> None:
        if not reviewer_id or not reviewer_id.strip():
            raise ValidationError("O identificador do funcionário é obrigatório.")
        forbidden = ("ai", "llm", "bot", "auto", "system", "agent", "model", "watsonx")
        if any(value in reviewer_id.lower() for value in forbidden):
            raise ValidationError("A IA não pode se identificar como revisor humano.")
