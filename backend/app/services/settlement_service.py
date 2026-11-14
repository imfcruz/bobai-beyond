"""
TransactionSettlementService — liquidação financeira simulada.

Responsável por efetivar movimentações financeiras após aprovação:
- Debitar saldo do cliente de origem.
- Creditar saldo do cliente de destino (se existir no simulador).
- Lançar lançamentos no extrato (StatementEntry).
- Atualizar saldos de forma atômica.
- Garantir idempotência (settlement_applied flag).
- Usar Decimal em todos os cálculos monetários.

NUNCA movimenta dinheiro real. Dados 100% sintéticos.
"""

import json
import uuid
from decimal import Decimal
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.transaction import Transaction, TransactionStatus
from app.models.transaction import FundingSource
from app.models.card import CardStatus, CreditCard
from app.models.statement_entry import StatementEntry, EntryType, EntryStatus
from app.models.beneficiary import Beneficiary
from app.core.errors import ValidationError

logger = structlog.get_logger(__name__)

# Statuses que representam aprovação definitiva (trigger settlement)
SETTLED_STATUSES = {
    TransactionStatus.RELEASED,
    TransactionStatus.HUMAN_APPROVED,
    TransactionStatus.APPROVED,
}

# Statuses que representam rejeição definitiva (liberar reserva, não debitar)
REJECTED_STATUSES = {
    TransactionStatus.REJECTED,
    TransactionStatus.HUMAN_REJECTED,
    TransactionStatus.BLOCKED,
}


class TransactionSettlementService:
    """
    Liquida uma transferência aprovada de forma atômica.

    Garantias:
    - Idempotência via `transaction.settlement_applied` flag — nunca debita duas vezes.
    - Usa Decimal em TODOS os cálculos — nunca float.
    - Opera dentro de uma transação de banco de dados existente.
    - Não aprova nem rejeita a transação — apenas efetiva o resultado já decidido.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def settle(self, transaction: Transaction) -> dict:
        """
        Efetiva uma transferência aprovada.

        Retorna um dict com:
        - settled: bool
        - reason: str
        - debit_entry: StatementEntry ou None
        - credit_entry: StatementEntry ou None
        - new_balance: Decimal do cliente de origem
        """
        # Idempotência — impede débito duplo
        if transaction.settlement_applied:
            logger.info(
                "Settlement already applied — skipping",
                txn_id=transaction.external_id,
            )
            return {"settled": False, "reason": "already_settled"}

        status = transaction.status
        amount = Decimal(str(transaction.amount))  # garantir Decimal

        if transaction.funding_source == FundingSource.CREDIT:
            return await self._settle_credit(transaction, amount, status)

        # Nenhuma ação para statuses não-terminais ou rejeição
        if status in REJECTED_STATUSES:
            # Liberar qualquer reserva existente sem debitar
            await self._release_reserve(transaction, amount)
            transaction.settlement_applied = True
            self.db.add(transaction)
            await self.db.flush()
            return {"settled": False, "reason": "rejected_no_debit"}

        if status not in SETTLED_STATUSES:
            return {"settled": False, "reason": f"not_a_settlement_status:{status}"}

        # Buscar cliente de origem. Em produção, este trecho deve usar uma
        # transação/lock compatível com o banco adotado; SQLite serializa as
        # escritas, mas não oferece SELECT ... FOR UPDATE real.
        client = await self.db.get(Client, transaction.client_id)
        if client is None:
            raise ValidationError(f"Cliente ID {transaction.client_id} não encontrado para liquidação.")

        balance = Decimal(str(client.balance))
        reserved = Decimal(str(client.reserved_balance))
        pending_reserve = await self._get_pending_reserve(transaction.id)
        own_reserved = (
            Decimal(str(pending_reserve.amount))
            if pending_reserve is not None
            else Decimal("0.00")
        )
        available = balance - reserved

        # Uma transação que já possui reserva pode consumir a própria reserva.
        # Transações sem reserva só podem consumir o saldo realmente disponível.
        has_sufficient_funds = (
            balance >= amount and own_reserved >= amount
            if pending_reserve is not None
            else available >= amount
        )
        if not has_sufficient_funds:
            logger.warning(
                "Insufficient balance at settlement",
                txn_id=transaction.external_id,
                available=str(available),
                amount=str(amount),
            )
            raise ValidationError(
                f"Saldo insuficiente para liquidação: disponível R$ {available}, necessário R$ {amount}."
            )

        # ── Debitar saldo de origem ────────────────────────────────────────────
        new_balance = balance - amount
        # Libera somente a reserva pertencente a ESTA transação. O código antigo
        # subtraía o valor de qualquer reserva agregada do cliente, corrompendo
        # operações pendentes não relacionadas.
        released_reserve = min(reserved, own_reserved)
        new_reserved = max(Decimal("0.00"), reserved - released_reserve)
        client.balance = new_balance
        client.reserved_balance = new_reserved
        self.db.add(client)

        if pending_reserve is not None:
            pending_reserve.status = EntryStatus.REVERSED
            self.db.add(pending_reserve)

        # ── Criar lançamento de débito no extrato ──────────────────────────────
        ben = await self.db.get(Beneficiary, transaction.beneficiary_id)
        ben_name = ben.name if ben else "Destinatário"
        ben_bank = ben.bank_name if ben else ""

        debit_entry = StatementEntry(
            client_id=client.id,
            transaction_id=transaction.id,
            entry_type=EntryType.DEBIT,
            amount=amount,
            currency=transaction.currency or "BRL",
            description=f"Transferência para {ben_name}" + (f" — {transaction.purpose}" if transaction.purpose else ""),
            counterpart_name=ben_name,
            counterpart_bank=ben_bank,
            status=EntryStatus.POSTED,
            balance_after=new_balance,
            posted_at=datetime.now(timezone.utc),
            metadata_json=json.dumps({
                "transaction_external_id": transaction.external_id,
                "settlement_status": status.value,
            }),
        )
        self.db.add(debit_entry)

        credit_entry = None

        # ── Creditar conta de destino se existir no simulador ─────────────────
        dest_client = await self._find_client_for_beneficiary(ben)
        if dest_client is not None:
            dest_balance = Decimal(str(dest_client.balance))
            new_dest_balance = dest_balance + amount
            dest_client.balance = new_dest_balance
            self.db.add(dest_client)

            credit_entry = StatementEntry(
                client_id=dest_client.id,
                transaction_id=transaction.id,
                entry_type=EntryType.CREDIT,
                amount=amount,
                currency=transaction.currency or "BRL",
                description=f"Transferência recebida de {client.name}",
                counterpart_name=client.name,
                counterpart_bank="Banco Brasil Digital",
                status=EntryStatus.POSTED,
                balance_after=new_dest_balance,
                posted_at=datetime.now(timezone.utc),
                metadata_json=json.dumps({
                    "transaction_external_id": transaction.external_id,
                    "settlement_status": status.value,
                }),
            )
            self.db.add(credit_entry)

        # ── Atualizar estatísticas do beneficiário ─────────────────────────────
        if ben is not None:
            ben.transfer_count = (ben.transfer_count or 0) + 1
            ben.total_transferred = Decimal(str(ben.total_transferred or "0.00")) + amount
            self.db.add(ben)

        # ── Marcar liquidação como aplicada (idempotência) ─────────────────────
        transaction.settlement_applied = True
        self.db.add(transaction)

        await self.db.flush()

        logger.info(
            "Settlement applied",
            txn_id=transaction.external_id,
            amount=str(amount),
            old_balance=str(balance),
            new_balance=str(new_balance),
            credited_client=dest_client.external_id if dest_client else None,
        )

        return {
            "settled": True,
            "reason": "ok",
            "debit_entry": debit_entry,
            "credit_entry": credit_entry,
            "new_balance": new_balance,
            "old_balance": balance,
        }

    async def apply_balance_reserve(self, transaction: Transaction) -> None:
        """
        Reserva saldo preventivamente quando uma transferência fica aguardando confirmação.
        Impede que o cliente use o mesmo saldo em outra operação concorrente.
        Não debita definitivamente.
        """
        if transaction.settlement_applied:
            return

        if transaction.funding_source == FundingSource.CREDIT:
            await self._apply_credit_reserve(transaction)
            return

        # Idempotência por transação: repetir o fluxo não pode reservar duas vezes.
        if await self._get_pending_reserve(transaction.id) is not None:
            return

        client = await self.db.get(Client, transaction.client_id)
        if client is None:
            return

        amount = Decimal(str(transaction.amount))
        balance = Decimal(str(client.balance))
        reserved = Decimal(str(client.reserved_balance))

        # Verificar disponibilidade
        if (balance - reserved) < amount:
            return  # Sem saldo suficiente para reservar — não bloqueia o fluxo

        # Criar lançamento de reserva (pending)
        reserve_entry = StatementEntry(
            client_id=client.id,
            transaction_id=transaction.id,
            entry_type=EntryType.RESERVE,
            amount=amount,
            currency=transaction.currency or "BRL",
            description=f"Reserva de saldo — transferência em análise",
            status=EntryStatus.PENDING,
            balance_after=balance - reserved - amount,
            posted_at=datetime.now(timezone.utc),
            metadata_json=json.dumps({
                "transaction_external_id": transaction.external_id,
            }),
        )
        client.reserved_balance = reserved + amount
        self.db.add(client)
        self.db.add(reserve_entry)
        await self.db.flush()

    async def _settle_credit(
        self,
        transaction: Transaction,
        amount: Decimal,
        status: TransactionStatus,
    ) -> dict:
        """Consome ou libera limite do cartão sem alterar o saldo da conta."""
        card = await self.db.get(CreditCard, transaction.card_id) if transaction.card_id else None
        if card is None:
            raise ValidationError("Cartão não encontrado para liquidação do Pix no crédito.")

        reserved = Decimal(str(card.reserved_credit))
        used = Decimal(str(card.used_credit))
        if status in REJECTED_STATUSES:
            if transaction.credit_reservation_applied:
                card.reserved_credit = max(Decimal("0.00"), reserved - amount)
                transaction.credit_reservation_applied = False
            transaction.settlement_applied = True
            self.db.add_all([card, transaction])
            await self.db.flush()
            return {"settled": False, "reason": "rejected_credit_released"}

        if status not in SETTLED_STATUSES:
            return {"settled": False, "reason": f"not_a_settlement_status:{status}"}
        if card.status != CardStatus.ACTIVE:
            raise ValidationError("O cartão está bloqueado.")

        available_without_own_reserve = Decimal(str(card.credit_limit)) - used - reserved
        if transaction.credit_reservation_applied:
            if reserved < amount:
                raise ValidationError("Reserva de crédito inconsistente para esta transação.")
            card.reserved_credit = reserved - amount
            transaction.credit_reservation_applied = False
        elif available_without_own_reserve < amount:
            raise ValidationError(
                f"Limite de crédito insuficiente: disponível R$ {available_without_own_reserve:.2f}."
            )

        card.used_credit = used + amount
        transaction.settlement_applied = True
        self.db.add_all([card, transaction])

        beneficiary = await self.db.get(Beneficiary, transaction.beneficiary_id)
        if beneficiary is not None:
            beneficiary.transfer_count = (beneficiary.transfer_count or 0) + 1
            beneficiary.total_transferred = Decimal(str(beneficiary.total_transferred or "0.00")) + amount
            self.db.add(beneficiary)
        await self.db.flush()
        return {
            "settled": True,
            "reason": "credit_consumed",
            "card_external_id": card.external_id,
            "available_credit": card.available_credit,
        }

    async def _apply_credit_reserve(self, transaction: Transaction) -> None:
        if transaction.credit_reservation_applied:
            return
        card = await self.db.get(CreditCard, transaction.card_id) if transaction.card_id else None
        if card is None or card.status != CardStatus.ACTIVE:
            return
        amount = Decimal(str(transaction.amount))
        if card.available_credit < amount:
            return
        card.reserved_credit = Decimal(str(card.reserved_credit)) + amount
        transaction.credit_reservation_applied = True
        self.db.add_all([card, transaction])
        await self.db.flush()

    async def _release_reserve(self, transaction: Transaction, amount: Decimal) -> None:
        """Libera qualquer reserva associada à transação rejeitada."""
        client = await self.db.get(Client, transaction.client_id)
        if client is None:
            return

        reserve_entry = await self._get_pending_reserve(transaction.id)
        if reserve_entry is None:
            # Uma rejeição imediata pode ocorrer antes de qualquer reserva.
            # Não toque nas reservas de outras transações.
            return

        reserved = Decimal(str(client.reserved_balance))
        reserved_for_transaction = Decimal(str(reserve_entry.amount))
        amount_to_release = min(reserved, reserved_for_transaction, amount)
        client.reserved_balance = max(
            Decimal("0.00"), reserved - amount_to_release
        )
        self.db.add(client)
        reserve_entry.status = EntryStatus.REVERSED
        self.db.add(reserve_entry)

        # Criar lançamento de estorno de reserva
        release_entry = StatementEntry(
            client_id=client.id,
            transaction_id=transaction.id,
            entry_type=EntryType.RELEASE,
            amount=amount_to_release,
            currency=transaction.currency or "BRL",
            description="Liberação de reserva — operação não efetivada",
            status=EntryStatus.REVERSED,
            balance_after=Decimal(str(client.balance)),
            posted_at=datetime.now(timezone.utc),
            metadata_json=json.dumps({
                "transaction_external_id": transaction.external_id,
            }),
        )
        self.db.add(release_entry)
        await self.db.flush()

    async def _get_pending_reserve(
        self, transaction_id: int
    ) -> StatementEntry | None:
        """Retorna a reserva pendente vinculada exclusivamente à transação."""
        result = await self.db.execute(
            select(StatementEntry)
            .where(StatementEntry.transaction_id == transaction_id)
            .where(StatementEntry.entry_type == EntryType.RESERVE)
            .where(StatementEntry.status == EntryStatus.PENDING)
            .order_by(StatementEntry.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_client_for_beneficiary(self, ben: Beneficiary | None) -> Client | None:
        """
        Tenta encontrar um cliente no simulador que seja o dono deste beneficiário.
        Usado para creditar a conta de destino quando ela também existe no simulador.
        Esta lógica é puramente demonstrativa.
        """
        if ben is None:
            return None
        # Nos dados de seed, beneficiários são de outros clientes.
        # Para crédito simulado, procuramos por external_id hints.
        # Na demo, apenas beneficiários internos recebem crédito.
        # Retorna None para beneficiários externos (maioria dos casos de demo).
        return None
