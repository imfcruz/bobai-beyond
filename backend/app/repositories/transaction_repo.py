"""
Repositório de Transaction com suporte a transições de estado validadas.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transaction import Transaction, TransactionStatus, is_valid_transition
from app.core.errors import ValidationError


class TransactionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, transaction_id: int) -> Transaction | None:
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .options(
                selectinload(Transaction.client),
                selectinload(Transaction.beneficiary),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Transaction | None:
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.external_id == external_id)
            .options(
                selectinload(Transaction.client),
                selectinload(Transaction.beneficiary),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_client(
        self, client_id: int, limit: int = 50, offset: int = 0
    ) -> list[Transaction]:
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.client_id == client_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(
                selectinload(Transaction.client),
                selectinload(Transaction.beneficiary),
            )
        )
        return list(result.scalars().all())

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[Transaction]:
        result = await self.db.execute(
            select(Transaction)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(
                selectinload(Transaction.client),
                selectinload(Transaction.beneficiary),
            )
        )
        return list(result.scalars().all())

    async def create(self, transaction: Transaction) -> Transaction:
        self.db.add(transaction)
        await self.db.flush()
        await self.db.refresh(transaction)
        return transaction

    async def get_by_idempotency_key(self, key: str) -> Transaction | None:
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.idempotency_key == key)
            .options(
                selectinload(Transaction.client),
                selectinload(Transaction.beneficiary),
            )
        )
        return result.scalar_one_or_none()

    async def transition_status(
        self,
        transaction: Transaction,
        new_status: TransactionStatus,
        reasoning: str | None = None,
    ) -> Transaction:
        """Aplica uma transição de estado validada. Levanta ValidationError se inválida."""
        if not is_valid_transition(transaction.status, new_status):
            raise ValidationError(
                f"Transição inválida: {transaction.status} → {new_status}"
            )
        transaction.status = new_status
        if reasoning:
            transaction.decision_reasoning = reasoning
        await self.db.flush()
        return transaction
