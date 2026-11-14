"""
Repositório de Client — operações CRUD sobre a tabela clients.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import Client


class ClientRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, client_id: int) -> Client | None:
        result = await self.db.execute(
            select(Client).where(Client.id == client_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Client | None:
        result = await self.db.execute(
            select(Client).where(Client.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Client]:
        result = await self.db.execute(
            select(Client)
            .order_by(Client.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, client: Client) -> Client:
        self.db.add(client)
        await self.db.flush()
        await self.db.refresh(client)
        return client

    async def count(self) -> int:
        from sqlalchemy import func
        result = await self.db.execute(select(func.count()).select_from(Client))
        return result.scalar_one()
