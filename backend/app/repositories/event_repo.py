"""
Repositório de ContextualEvent.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contextual_event import ContextualEvent, EventType


class ContextualEventRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_client(
        self, client_id: int, limit: int = 100
    ) -> list[ContextualEvent]:
        result = await self.db.execute(
            select(ContextualEvent)
            .where(ContextualEvent.client_id == client_id)
            .order_by(ContextualEvent.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_recent_by_client(
        self,
        client_id: int,
        *,
        minutes: int = 1440,
        limit: int = 100,
    ) -> list[ContextualEvent]:
        """Lista somente eventos dentro da janela contextual, em ordem temporal."""
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = await self.db.execute(
            select(ContextualEvent)
            .where(
                ContextualEvent.client_id == client_id,
                ContextualEvent.occurred_at >= cutoff,
            )
            .order_by(ContextualEvent.occurred_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_transaction(
        self, transaction_id: int
    ) -> list[ContextualEvent]:
        result = await self.db.execute(
            select(ContextualEvent)
            .where(ContextualEvent.transaction_id == transaction_id)
            .order_by(ContextualEvent.occurred_at.asc())
        )
        return list(result.scalars().all())

    async def list_by_correlation(self, correlation_id: str) -> list[ContextualEvent]:
        result = await self.db.execute(
            select(ContextualEvent)
            .where(ContextualEvent.correlation_id == correlation_id)
            .order_by(ContextualEvent.occurred_at.asc())
        )
        return list(result.scalars().all())

    async def create(self, event: ContextualEvent) -> ContextualEvent:
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def count_recent_by_type(
        self, client_id: int, event_type: EventType, minutes: int = 60
    ) -> int:
        from sqlalchemy import func
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = await self.db.execute(
            select(func.count())
            .select_from(ContextualEvent)
            .where(
                ContextualEvent.client_id == client_id,
                ContextualEvent.event_type == event_type,
                ContextualEvent.occurred_at >= cutoff,
            )
        )
        return result.scalar_one()
