"""
BankService — lógica de negócios do simulador bancário.
Todas as operações são simuladas. Nenhum dinheiro real é movimentado.

Etapa 6: pipeline completo com idempotência, timeouts, confirmação contextual
         e revisão humana explícita.
Fase 1 (Nexus): Liquidação financeira real — saldo debitado, extrato gerado.
"""

import asyncio
import json
import uuid
from datetime import UTC
from decimal import Decimal, InvalidOperation

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator_agent import OrchestratorAgent, build_context_from_domain
from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.models.audit_log import AuditLog
from app.models.beneficiary import Beneficiary
from app.models.card import CardStatus, CreditCard
from app.models.contextual_event import ContextualEvent, EventType
from app.models.risk_analysis import RiskAnalysis, RiskAnalysisStatus
from app.models.transaction import (
    FundingSource,
    Transaction,
    TransactionStatus,
)
from app.repositories.beneficiary_repo import BeneficiaryRepository
from app.repositories.client_repo import ClientRepository
from app.repositories.event_repo import ContextualEventRepository
from app.repositories.risk_analysis_repo import RiskAnalysisRepository
from app.repositories.transaction_repo import TransactionRepository
from app.services.decision_engine import make_decision
from app.services.security_gateway import SecurityGateway
from app.services.settlement_service import (
    REJECTED_STATUSES,
    SETTLED_STATUSES,
    TransactionSettlementService,
)

logger = structlog.get_logger(__name__)

_gateway = SecurityGateway()

class BankService:
    """
    Coordena todas as operações bancárias simuladas.
    Pipeline: Orquestrador → Decision Engine → Security Gateway → persistência.

    Garantias:
    - Idempotência via idempotency_key: reenvio retorna resultado existente sem reprocessar.
    - Timeout por pipeline: falha de agente → status permanece PENDING, nunca aprovado automaticamente.
    - Falha crítica nunca produz RELEASED automático.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.clients = ClientRepository(db)
        self.beneficiaries = BeneficiaryRepository(db)
        self.transactions = TransactionRepository(db)
        self.events = ContextualEventRepository(db)
        self.risk_analyses = RiskAnalysisRepository(db)
        self.settlement = TransactionSettlementService(db)

    # ── Clientes ──────────────────────────────────────────────────────────────

    async def list_clients(self, limit: int = 100, offset: int = 0):
        return await self.clients.list_all(limit, offset)

    async def get_client(self, external_id: str):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.client import Client as ClientModel
        result = await self.db.execute(
            select(ClientModel)
            .where(ClientModel.external_id == external_id)
            .options(selectinload(ClientModel.behavioral_history))
        )
        client = result.scalar_one_or_none()
        if client is None:
            raise NotFoundError("Client", external_id)
        return client

    # ── Beneficiários ─────────────────────────────────────────────────────────

    async def list_beneficiaries(self, client_external_id: str):
        client = await self.get_client(client_external_id)
        return await self.beneficiaries.list_by_client(client.id)

    async def get_beneficiary(self, external_id: str):
        ben = await self.beneficiaries.get_by_external_id(external_id)
        if ben is None:
            raise NotFoundError("Beneficiary", external_id)
        return ben

    async def set_beneficiary_favorite(self, external_id: str, is_favorite: bool):
        beneficiary = await self.beneficiaries.set_favorite(external_id, is_favorite)
        if beneficiary is None:
            raise NotFoundError("Beneficiary", external_id)
        return beneficiary

    # ── Histórico transacional ────────────────────────────────────────────────

    async def get_client_transaction_history(
        self, client_external_id: str, limit: int = 50
    ):
        client = await self.get_client(client_external_id)
        return await self.transactions.list_by_client(client.id, limit=limit)

    # ── Eventos contextuais ───────────────────────────────────────────────────

    async def get_client_events(self, client_external_id: str, limit: int = 100):
        client = await self.get_client(client_external_id)
        return await self.events.list_by_client(client.id, limit=limit)

    async def get_transaction_events(self, transaction_external_id: str):
        txn = await self.transactions.get_by_external_id(transaction_external_id)
        if txn is None:
            raise NotFoundError("Transaction", transaction_external_id)
        return await self.events.list_by_transaction(txn.id)

    # ── Transações ────────────────────────────────────────────────────────────

    async def get_transaction(self, external_id: str):
        txn = await self.transactions.get_by_external_id(external_id)
        if txn is None:
            raise NotFoundError("Transaction", external_id)
        return txn

    # ── Iniciar transferência ─────────────────────────────────────────────────

    async def initiate_transfer(
        self,
        client_external_id: str,
        beneficiary_external_id: str,
        amount_str: str,
        purpose: str | None,
        device_recognized: bool = True,
        idempotency_key: str | None = None,
        funding_source: FundingSource | str = FundingSource.DEBIT,
        card_external_id: str | None = None,
    ) -> dict:
        """
        Inicia uma transferência simulada via pipeline multiagente.

        Idempotência:
          Se idempotency_key já existe, retorna o resultado existente sem reprocessar.
          Impede duplicação por reenvio acidental.

        Fluxo:
        1. Valida cliente, beneficiário e valor.
        2. Verifica idempotência.
        3. Cria a transação em estado PENDING.
        4. Registra evento contextual INICIO_TRANSFERENCIA.
        5. Cria RiskAnalysis placeholder.
        6. Constrói AgentContext e executa pipeline com timeout.
        7. Aplica Decision Engine (com sub_results para divergência).
        8. Valida no Security Gateway.
        9. Persiste resultados, trilha de auditoria.
        10. Retorna transação + análise.
        """
        # Validação do valor
        try:
            amount = Decimal(amount_str)
        except InvalidOperation:
            raise ValidationError(f"Valor inválido: '{amount_str}'")
        if amount <= Decimal("0"):
            raise ValidationError("O valor da transferência deve ser positivo.")
        if amount > Decimal("999999999.99"):
            raise ValidationError("Valor excede o limite máximo permitido na simulação.")

        try:
            source = funding_source if isinstance(funding_source, FundingSource) else FundingSource(funding_source)
        except ValueError as exc:
            raise ValidationError("Forma de pagamento inválida. Use 'debit' ou 'credit'.") from exc

        # Verificar idempotência — reenvio retorna resultado existente
        if idempotency_key:
            existing = await self.transactions.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                logger.info(
                    "Idempotency key already used — returning existing transaction",
                    idempotency_key=idempotency_key,
                    txn_id=existing.external_id,
                )
                analysis = await self.risk_analyses.get_by_transaction(existing.id)
                return {
                    "transaction": existing,
                    "analysis": analysis,
                    "gateway": None,
                    "idempotent": True,
                }

        # Buscar entidades
        client = await self.get_client(client_external_id)
        beneficiary = await self.beneficiaries.get_by_external_id(beneficiary_external_id)
        if beneficiary is None:
            raise NotFoundError("Beneficiary", beneficiary_external_id)
        if beneficiary.client_id != client.id:
            raise ValidationError("Beneficiário não pertence ao cliente informado.")

        card = None
        if source == FundingSource.DEBIT:
            available = Decimal(str(client.balance)) - Decimal(str(client.reserved_balance))
            if amount > available:
                raise ValidationError(
                    f"Saldo insuficiente: disponível R$ {available:.2f}, solicitado R$ {amount:.2f}."
                )
            if amount > Decimal(str(client.transfer_limit)):
                raw_limit = f"{Decimal(str(client.transfer_limit)):,.2f}"
                formatted_limit = raw_limit.replace(",", "X").replace(".", ",").replace("X", ".")
                raise ValidationError(
                    "O valor da transferência ultrapassa seu limite Pix disponível de "
                    f"R$ {formatted_limit}. Ajuste o limite antes de continuar."
                )
        else:
            if not card_external_id:
                raise ValidationError("Selecione um cartão para fazer Pix no crédito.")
            from sqlalchemy import select
            result = await self.db.execute(
                select(CreditCard).where(CreditCard.external_id == card_external_id)
            )
            card = result.scalar_one_or_none()
            if card is None or card.client_id != client.id:
                raise ValidationError("O cartão informado não pertence ao cliente.")
            if card.status != CardStatus.ACTIVE:
                raise ValidationError("O cartão selecionado está bloqueado.")
            if amount > card.available_credit:
                raise ValidationError(
                    f"Limite de crédito insuficiente: disponível R$ {card.available_credit:.2f}."
                )

        # Verificar alteração de limite recente via eventos
        recent_transfer_limit_change = await self.events.count_recent_by_type(
            client.id, EventType.ALTERACAO_LIMITE, minutes=120
        ) > 0
        recent_credit_limit_change = await self.events.count_recent_by_type(
            client.id, EventType.AUMENTO_LIMITE_CREDITO_APROVADO, minutes=120
        ) > 0
        recent_limit_change = recent_transfer_limit_change or recent_credit_limit_change

        # Buscar eventos contextuais somente dentro da janela das últimas 24h,
        # em ordem cronológica, para que a sequência analisada seja real.
        recent_events_objs = await self.events.list_recent_by_client(
            client.id, minutes=24 * 60, limit=20
        )
        recent_events = [
            {
                "event_type": e.event_type.value,
                "metadata": e.metadata_json,
            }
            for e in recent_events_objs
        ]

        correlation_id = str(uuid.uuid4())[:12]

        # Criar transação
        txn = Transaction(
            external_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            client_id=client.id,
            beneficiary_id=beneficiary.id,
            card_id=card.id if card else None,
            amount=amount,
            currency="BRL",
            purpose=purpose or "",
            funding_source=source,
            is_new_recipient=not beneficiary.is_known,
            recent_limit_change=recent_limit_change,
            device_recognized=device_recognized,
            status=TransactionStatus.PENDING,
        )
        txn = await self.transactions.create(txn)

        # Registrar evento de início do Pix
        event = ContextualEvent(
            client_id=client.id,
            transaction_id=txn.id,
            event_type=(
                EventType.INICIO_PIX_CREDITO
                if source == FundingSource.CREDIT
                else EventType.INICIO_TRANSFERENCIA
            ),
            correlation_id=correlation_id,
            metadata_json=json.dumps({
                "beneficiario_ext_id": beneficiary_external_id,
                "valor": str(amount),
                "beneficiario_conhecido": beneficiary.is_known,
                "funding_source": source.value,
                "card_external_id": card.external_id if card else None,
            }),
        )
        await self.events.create(event)

        # Criar placeholder de análise de risco
        analysis = RiskAnalysis(
            external_id=str(uuid.uuid4()),
            transaction_id=txn.id,
            status=RiskAnalysisStatus.IN_PROGRESS,
        )
        analysis = await self.risk_analyses.create(analysis)

        # ── Pipeline multiagente com timeout ──────────────────────────────────
        from datetime import datetime
        analysis.started_at = datetime.now(UTC)

        bh = client.behavioral_history
        ctx = build_context_from_domain(
            transaction_ext_id=txn.external_id,
            client_ext_id=client.external_id,
            correlation_id=correlation_id,
            analysis_id=analysis.external_id,
            amount=amount,
            purpose=purpose or "",
            is_new_recipient=not beneficiary.is_known,
            recent_limit_change=recent_limit_change,
            device_recognized=device_recognized,
            is_known_beneficiary=beneficiary.is_known,
            avg_transfer=bh.avg_transfer_value if bh else Decimal("1000.00"),
            max_transfer=bh.max_transfer_value if bh else Decimal("5000.00"),
            min_transfer=bh.min_transfer_value if bh else Decimal("100.00"),
            avg_monthly_tx=bh.avg_monthly_transactions if bh else 5,
            account_age_days=client.account_age_days,
            risk_profile=client.risk_profile.value,
            beneficiary_transfer_count=beneficiary.transfer_count,
            beneficiary_total=beneficiary.total_transferred,
            recent_events=recent_events,
            typical_hours=bh.typical_hours if bh else None,
            typical_channels=bh.typical_channels if bh else None,
            operation_type="pix",
            funding_source=source.value,
        )

        orchestrator = OrchestratorAgent()
        pipeline_failed = False
        failure_reason = ""
        final_result = None
        individual_results = {}

        try:
            final_result, individual_results = await asyncio.wait_for(
                orchestrator.run_full_pipeline(ctx),
                timeout=settings.AGENT_PIPELINE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            pipeline_failed = True
            failure_reason = (
                f"Pipeline timeout após {settings.AGENT_PIPELINE_TIMEOUT_SECONDS}s. "
                "Transação mantida como PENDING para revisão."
            )
            logger.error(
                "Agent pipeline TIMEOUT",
                txn_id=txn.external_id,
                timeout_s=settings.AGENT_PIPELINE_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            pipeline_failed = True
            failure_reason = f"Falha crítica no pipeline: {type(exc).__name__}. Transação mantida como PENDING."
            logger.error(
                "Agent pipeline FAILED",
                txn_id=txn.external_id,
                error=type(exc).__name__,
            )

        if pipeline_failed:
            # Falha nunca produz aprovação automática — transação fica PENDING
            analysis.status = RiskAnalysisStatus.FAILED
            analysis.reasoning = failure_reason
            analysis.completed_at = datetime.now(UTC)
            self.db.add(AuditLog(
                transaction_id=txn.id,
                component="pipeline",
                agent_name="orchestrator_agent",
                action="pipeline_failed",
                event="PIPELINE_FAILURE",
                result="pending",
                reasoning=failure_reason,
                risk_score=None,
                flags=json.dumps(["pipeline_failure"]),
                correlation_id=correlation_id,
                policy_version="N/A",
            ))
            await self.db.flush()
            await self.db.refresh(txn)
            await self.db.refresh(analysis)
            return {
                "transaction": txn,
                "analysis": analysis,
                "gateway": None,
                "pipeline_failed": True,
                "failure_reason": failure_reason,
            }

        # ── Decision Engine — passa sub_results para detecção de divergência ──
        sub_results_list = list(individual_results.values())
        decision = make_decision(final_result, sub_results=sub_results_list)

        # ── Security Gateway ───────────────────────────────────────────────────
        gateway_response = _gateway.evaluate(decision)

        # ── Persistir resultados individuais por agente ────────────────────────
        analysis.fraud_agent_result = individual_results["fraud_agent"].to_json()
        inconsistency_result = individual_results.get("inconsistency_agent")
        behavioral_result = individual_results.get("behavioral_agent")
        intention_result = individual_results.get("intention_agent")
        analysis.inconsistency_agent_result = (
            inconsistency_result.to_json() if inconsistency_result else None
        )
        analysis.behavioral_agent_result = (
            behavioral_result.to_json() if behavioral_result else None
        )
        analysis.intention_agent_result = (
            intention_result.to_json() if intention_result else None
        )
        analysis.risk_agent_result = individual_results["risk_agent"].to_json()
        analysis.orchestrator_result = final_result.to_json()

        analysis.overall_risk_score = gateway_response.risk_score
        analysis.risk_level = gateway_response.risk_level.value
        analysis.recommended_action = gateway_response.final_action
        analysis.reasoning = gateway_response.gateway_reasoning
        analysis.flags = json.dumps(gateway_response.flags)
        analysis.status = RiskAnalysisStatus.COMPLETED
        analysis.completed_at = datetime.now(UTC)
        analysis.policy_version = gateway_response.policy_version
        analysis.divergence_detected = decision.divergence_detected
        analysis.divergence_details = decision.divergence_details
        analysis.phase = "initial"

        # ── Atualizar transação ────────────────────────────────────────────────
        new_status = gateway_response.final_status
        txn = await self.transactions.transition_status(txn, new_status, gateway_response.gateway_reasoning)
        txn.risk_level = gateway_response.risk_level
        txn.risk_score = gateway_response.risk_score

        # ── Audit log completo ────────────────────────────────────────────────
        agent_contributions_json = json.dumps([
            {
                "agent_name": c.agent_name,
                "risk_score": c.risk_score,
                "flags": c.flags,
            }
            for c in decision.agent_contributions
        ])
        self.db.add(AuditLog(
            transaction_id=txn.id,
            component="security_gateway",
            agent_name="orchestrator_agent",
            action="transfer_initiated",
            event="PIPELINE_COMPLETED",
            result=new_status.value,
            reasoning=gateway_response.gateway_reasoning,
            risk_score=gateway_response.risk_score,
            flags=json.dumps(gateway_response.flags),
            correlation_id=correlation_id,
            policy_version=gateway_response.policy_version,
            execution_time_ms=decision.decision_time_ms,
            agent_contributions=agent_contributions_json,
        ))

        await self.db.flush()
        await self.db.refresh(txn)
        await self.db.refresh(analysis)

        # ── Liquidação financeira ─────────────────────────────────────────────
        # Se a decisão for de aprovação definitiva, debitar saldo e lançar extrato.
        # Se for de rejeição, liberar reserva sem debitar.
        # Se aguardar confirmação, reservar saldo preventivamente.
        settlement_result = None
        if new_status in SETTLED_STATUSES:
            settlement_result = await self.settlement.settle(txn)
            await self.db.refresh(txn)
        elif new_status in REJECTED_STATUSES:
            settlement_result = await self.settlement.settle(txn)
            await self.db.refresh(txn)
        elif new_status in {
            TransactionStatus.AWAITING_CONFIRMATION,
            TransactionStatus.UNDER_VERIFICATION,
            TransactionStatus.HUMAN_REVIEW_PENDING,
            TransactionStatus.ESCALATED_TO_HUMAN,
        }:
            await self.settlement.apply_balance_reserve(txn)
            # A atualização da reserva altera a própria transação no Pix crédito.
            # Recarrega campos com server defaults antes da serialização Pydantic.
            await self.db.refresh(txn)

        logger.info(
            "Transfer initiated via agent pipeline",
            txn_id=txn.external_id,
            amount=str(amount),
            risk_score=gateway_response.risk_score,
            status=new_status.value,
            authorized=gateway_response.authorized,
            divergence=decision.divergence_detected,
            policy=gateway_response.policy_version,
            settlement_applied=settlement_result.get("settled") if settlement_result else False,
        )

        return {
            "transaction": txn,
            "analysis": analysis,
            "gateway": gateway_response.to_dict(),
            "settlement": settlement_result,
        }

    # ── Confirmação Contextual (Fase 2) ───────────────────────────────────────

    async def confirm_transfer(
        self,
        transaction_external_id: str,
        confirmation_purpose: str,
    ) -> dict:
        """
        Fase 2: cliente fornece finalidade da transferência.

        A resposta não é tratada automaticamente como verdadeira ou falsa.
        O sistema registra e reavalia o contexto antes de emitir nova decisão.
        """
        txn = await self.transactions.get_by_external_id(transaction_external_id)
        if txn is None:
            raise NotFoundError("Transaction", transaction_external_id)

        if txn.status != TransactionStatus.AWAITING_CONFIRMATION:
            raise ValidationError(
                f"Transação não está aguardando confirmação. Status atual: {txn.status.value}"
            )

        analysis = await self.risk_analyses.get_by_transaction(txn.id)
        if analysis is None:
            raise NotFoundError("RiskAnalysis for transaction", transaction_external_id)

        # Registrar evento de confirmação contextual
        correlation_id = str(uuid.uuid4())[:12]

        await self.events.create(ContextualEvent(
            client_id=txn.client_id,
            transaction_id=txn.id,
            event_type=EventType.CONFIRMACAO_CONTEXTUAL,
            correlation_id=correlation_id,
            metadata_json=json.dumps({
                "confirmation_purpose": confirmation_purpose[:500],  # Limita tamanho
                "phase": "confirmation",
            }),
        ))

        # Armazena finalidade fornecida
        analysis.confirmation_purpose = confirmation_purpose
        analysis.phase = "confirmation"

        # Reavalia o contexto com a finalidade fornecida
        # A resposta é tratada como dado a analisar — não como verdade automática
        purpose_lower = confirmation_purpose.lower()

        # Detecta indicadores de coerção ou pressão
        coercion_keywords = [
            "me obrigaram", "fui forçado", "banco pediu", "não sei", "não entendo",
            "funcionário disse", "funcionário do banco", "garantido pelo banco",
            "proteger conta", "banco me disse", "banco me pediu", "banco me orientou",
            "me disse para", "me pediu para", "gerente disse",
        ]
        coercion_detected = any(kw in purpose_lower for kw in coercion_keywords)

        # Indicadores de confirmação genuína
        genuine_keywords = [
            "compra", "pagamento", "fornecedor", "serviço", "aluguel", "investimento",
            "amigo", "familiar", "empréstimo pessoal", "salário",
        ]
        genuine_signals = sum(1 for kw in genuine_keywords if kw in purpose_lower)

        # Determinar nova decisão
        if coercion_detected:
            new_status = TransactionStatus.HUMAN_REVIEW_PENDING
            reasoning = (
                "Confirmação contextual indica possível coerção ou engenharia social. "
                "Encaminhado para revisão humana obrigatória."
            )
        elif genuine_signals >= 1 and not coercion_detected:
            # Finalidade genuína — liberar se o score anterior era médio
            if analysis.overall_risk_score < 0.60:
                new_status = TransactionStatus.RELEASED
                reasoning = "Confirmação contextual satisfatória — operação liberada."
            else:
                # Score alto — mesmo com confirmação, manter em revisão
                new_status = TransactionStatus.HUMAN_REVIEW_PENDING
                reasoning = (
                    "Confirmação recebida mas score de risco elevado — "
                    "revisão humana necessária."
                )
        else:
            # Finalidade ambígua — mantém sob verificação
            new_status = TransactionStatus.HUMAN_REVIEW_PENDING
            reasoning = (
                "Finalidade fornecida não foi suficiente para liberação automática. "
                "Encaminhado para revisão humana."
            )
        txn = await self.transactions.transition_status(txn, new_status, reasoning)

        # Audit log
        self.db.add(AuditLog(
            transaction_id=txn.id,
            component="bank_service",
            agent_name="confirmation_handler",
            action="confirmation_provided",
            event="CONFIRMATION_PHASE_2",
            result=new_status.value,
            reasoning=reasoning,
            risk_score=analysis.overall_risk_score,
            flags=json.dumps(["confirmation_phase_2", "coercion_detected"] if coercion_detected else ["confirmation_phase_2"]),
            correlation_id=correlation_id,
            policy_version="1.0.0",
        ))

        await self.db.flush()
        await self.db.refresh(txn)
        await self.db.refresh(analysis)

        # ── Liquidação financeira após confirmação ────────────────────────────
        if new_status in SETTLED_STATUSES:
            await self.settlement.settle(txn)
            await self.db.refresh(txn)
        elif new_status in REJECTED_STATUSES:
            await self.settlement.settle(txn)
            await self.db.refresh(txn)

        logger.info(
            "Transfer confirmation processed",
            txn_id=txn.external_id,
            new_status=new_status.value,
            coercion_detected=coercion_detected,
        )

        return {
            "transaction": txn,
            "analysis": analysis,
            "new_status": new_status.value,
            "reasoning": reasoning,
            "coercion_detected": coercion_detected,
        }

    # ── Revisão Humana ────────────────────────────────────────────────────────

    async def human_review(
        self,
        transaction_external_id: str,
        action: str,       # "approve" | "reject"
        reviewer_id: str,  # ID do operador humano — a IA não pode fingir ser revisor
        reviewer_notes: str | None = None,
    ) -> dict:
        """
        Ação de revisão humana explícita.

        Apenas operadores humanos identificados podem executar esta ação.
        A IA não pode fingir ser o revisor (validado pelo SecurityGateway).
        """
        txn = await self.transactions.get_by_external_id(transaction_external_id)
        if txn is None:
            raise NotFoundError("Transaction", transaction_external_id)

        # Validar ação via SecurityGateway — impede que a IA se passe por revisor
        allowed, gw_reasoning = _gateway.validate_human_action(
            current_status=txn.status,
            action=action,
            reviewer_id=reviewer_id,
        )
        if not allowed:
            raise ValidationError(gw_reasoning)

        # Determinar novo status
        if action == "approve":
            new_status = TransactionStatus.HUMAN_APPROVED
            result_label = "approved_by_human"
        else:
            new_status = TransactionStatus.HUMAN_REJECTED
            result_label = "rejected_by_human"

        reasoning = (
            f"Revisão humana por '{reviewer_id}': {action.upper()}. "
            f"Notas: {reviewer_notes or 'Sem notas adicionais.'}"
        )
        txn = await self.transactions.transition_status(txn, new_status, reasoning)

        analysis = await self.risk_analyses.get_by_transaction(txn.id)
        correlation_id = str(uuid.uuid4())[:12]

        # Registrar evento de revisão
        await self.events.create(ContextualEvent(
            client_id=txn.client_id,
            transaction_id=txn.id,
            event_type=EventType.REVISAO_HUMANA,
            correlation_id=correlation_id,
            metadata_json=json.dumps({
                "action": action,
                "reviewer_id": reviewer_id,
                "reviewer_notes": reviewer_notes or "",
            }),
        ))

        # Audit log completo
        self.db.add(AuditLog(
            transaction_id=txn.id,
            component="security_gateway",
            agent_name=f"human_reviewer:{reviewer_id}",
            action=f"human_review_{action}",
            event="HUMAN_REVIEW_COMPLETED",
            result=result_label,
            reasoning=reasoning,
            risk_score=analysis.overall_risk_score if analysis else None,
            flags=json.dumps(["human_review", f"reviewer:{reviewer_id}"]),
            correlation_id=correlation_id,
            policy_version="1.0.0",
        ))

        await self.db.flush()
        await self.db.refresh(txn)

        # ── Liquidação financeira após revisão humana ─────────────────────────
        if new_status in SETTLED_STATUSES:
            await self.settlement.settle(txn)
            await self.db.refresh(txn)
        elif new_status in REJECTED_STATUSES:
            await self.settlement.settle(txn)
            await self.db.refresh(txn)

        logger.info(
            "Human review completed",
            txn_id=txn.external_id,
            action=action,
            new_status=new_status.value,
            reviewer_id=reviewer_id,
        )

        return {
            "transaction": txn,
            "analysis": analysis,
            "action": action,
            "reviewer_id": reviewer_id,
            "new_status": new_status.value,
            "reasoning": reasoning,
        }

    # ── Análises de risco ─────────────────────────────────────────────────────

    async def get_risk_analysis(self, transaction_external_id: str):
        txn = await self.transactions.get_by_external_id(transaction_external_id)
        if txn is None:
            raise NotFoundError("Transaction", transaction_external_id)
        analysis = await self.risk_analyses.get_by_transaction(txn.id)
        if analysis is None:
            raise NotFoundError("RiskAnalysis for transaction", transaction_external_id)
        return analysis

    async def list_risk_analyses(self, limit: int = 50, offset: int = 0):
        return await self.risk_analyses.list_all(limit, offset)

    # ── Extrato bancário ──────────────────────────────────────────────────────

    async def get_statement(
        self,
        client_external_id: str,
        limit: int = 50,
        offset: int = 0,
        entry_type: str | None = None,
        status: str | None = None,
    ):
        """Retorna os lançamentos do extrato de um cliente."""
        from sqlalchemy import select

        from app.models.statement_entry import StatementEntry

        client = await self.get_client(client_external_id)

        q = (
            select(StatementEntry)
            .where(StatementEntry.client_id == client.id)
            .order_by(StatementEntry.posted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if entry_type:
            q = q.where(StatementEntry.entry_type == entry_type)
        if status:
            q = q.where(StatementEntry.status == status)

        result = await self.db.execute(q)
        return list(result.scalars().all())

    # ── Gestão de limites ─────────────────────────────────────────────────────

    async def get_limit_info(self, client_external_id: str) -> dict:
        """Retorna informações de limite do cliente."""
        client = await self.get_client(client_external_id)
        used_today = await self._compute_used_limit_today(client.id)
        return {
            "client_external_id": client_external_id,
            "transfer_limit": client.transfer_limit,
            "used_today": used_today,
            "available_limit": max(Decimal("0.00"), Decimal(str(client.transfer_limit)) - used_today),
            "balance": client.balance,
            "reserved_balance": client.reserved_balance,
            "available_balance": client.available_balance,
        }

    async def _compute_used_limit_today(self, client_id: int) -> Decimal:
        """Soma os valores de transferências efetivadas hoje."""
        from datetime import date, time
        from datetime import datetime as dt_class

        from sqlalchemy import func, select

        from app.models.statement_entry import EntryStatus, EntryType, StatementEntry

        today_start = dt_class.combine(date.today(), time.min).replace(tzinfo=UTC)
        result = await self.db.execute(
            select(func.coalesce(func.sum(StatementEntry.amount), 0))
            .where(StatementEntry.client_id == client_id)
            .where(StatementEntry.entry_type == EntryType.DEBIT)
            .where(StatementEntry.status == EntryStatus.POSTED)
            .where(StatementEntry.posted_at >= today_start)
        )
        return Decimal(str(result.scalar_one()))

    async def request_limit_change(
        self,
        client_external_id: str,
        requested_limit: str,
        reason: str | None = None,
    ) -> dict:
        """
        Solicita alteração de limite de transferência.

        Política demonstrativa:
        - Aumento até 2× o limite atual: aprovado automaticamente.
        - Aumento maior: requer revisão humana (simulado como pendente).
        - Redução: sempre aprovada automaticamente.

        Gera evento contextual ALTERACAO_LIMITE (visível aos agentes).
        """
        from app.models.contextual_event import ContextualEvent, EventType

        client = await self.get_client(client_external_id)
        current_limit = Decimal(str(client.transfer_limit))

        try:
            new_limit = Decimal(requested_limit)
        except Exception:
            raise ValidationError(f"Limite inválido: '{requested_limit}'")

        if new_limit <= Decimal("0"):
            raise ValidationError("O limite deve ser positivo.")
        if new_limit > Decimal("200000.00"):
            raise ValidationError("Limite máximo da simulação é R$ 200.000,00.")

        correlation_id = str(uuid.uuid4())[:12]
        approved = False
        status = "pending"

        # Política demonstrativa
        if new_limit <= current_limit:
            # Redução — sempre aprovada
            approved = True
            status = "approved"
        elif new_limit <= current_limit * Decimal("2"):
            # Aumento moderado — aprovado automaticamente
            approved = True
            status = "approved"
        else:
            # Aumento grande — simulado como pendente (revisão manual)
            approved = False
            status = "pending_review"

        if approved:
            client.transfer_limit = new_limit
            self.db.add(client)

        # Registrar evento contextual (usado pelos agentes)
        event = ContextualEvent(
            client_id=client.id,
            transaction_id=None,
            event_type=EventType.ALTERACAO_LIMITE,
            correlation_id=correlation_id,
            metadata_json=json.dumps({
                "limite_anterior": str(current_limit),
                "limite_solicitado": str(new_limit),
                "limite_aprovado": str(new_limit) if approved else None,
                "status": status,
                "motivo": reason or "",
            }),
        )
        await self.events.create(event)

        await self.db.flush()
        if approved:
            await self.db.refresh(client)

        return {
            "previous_limit": current_limit,
            "requested_limit": new_limit,
            "approved_limit": new_limit if approved else None,
            "status": status,
            "approved": approved,
            "client_external_id": client_external_id,
            "event_correlation_id": correlation_id,
            "message": (
                f"Limite alterado de R$ {current_limit:.2f} para R$ {new_limit:.2f}."
                if approved else
                f"Solicitação de limite R$ {new_limit:.2f} aguardando revisão (aumento acima de 2×)."
            ),
        }

    async def add_beneficiary(
        self,
        client_external_id: str,
        name: str,
        account_hint: str,
        bank_name: str,
    ) -> "Beneficiary":
        """
        Cadastra um novo beneficiário e registra o evento contextual.
        """
        from app.models.beneficiary import Beneficiary
        from app.models.contextual_event import ContextualEvent, EventType

        client = await self.get_client(client_external_id)
        correlation_id = str(uuid.uuid4())[:12]

        ben = Beneficiary(
            external_id=str(uuid.uuid4()),
            client_id=client.id,
            name=name,
            account_hint=account_hint,
            bank_name=bank_name,
            is_known=False,
            transfer_count=0,
            total_transferred=Decimal("0.00"),
            risk_hint=0.30,
        )
        self.db.add(ben)
        await self.db.flush()
        await self.db.refresh(ben)

        # Registrar evento contextual (visível aos agentes)
        event = ContextualEvent(
            client_id=client.id,
            transaction_id=None,
            event_type=EventType.CADASTRO_BENEFICIARIO,
            correlation_id=correlation_id,
            metadata_json=json.dumps({
                "beneficiario_ext_id": ben.external_id,
                "nome": name,
                "is_new": True,
            }),
        )
        await self.events.create(event)

        return ben
