"""
Repositório de Beneficiary.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beneficiary import Beneficiary


class BeneficiaryRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, beneficiary_id: int) -> Beneficiary | None:
        result = await self.db.execute(
            select(Beneficiary).where(Beneficiary.id == beneficiary_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Beneficiary | None:
        result = await self.db.execute(
            select(Beneficiary).where(Beneficiary.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def list_by_client(self, client_id: int, limit: int = 100) -> list[Beneficiary]:
        result = await self.db.execute(
            select(Beneficiary)
            .where(Beneficiary.client_id == client_id)
            .order_by(Beneficiary.is_favorite.desc(), Beneficiary.transfer_count.desc(), Beneficiary.name)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def set_favorite(self, external_id: str, is_favorite: bool) -> Beneficiary | None:
        beneficiary = await self.get_by_external_id(external_id)
        if beneficiary is None:
            return None
        beneficiary.is_favorite = is_favorite
        self.db.add(beneficiary)
        await self.db.flush()
        await self.db.refresh(beneficiary)
        return beneficiary

    async def create(self, beneficiary: Beneficiary) -> Beneficiary:
        self.db.add(beneficiary)
        await self.db.flush()
        await self.db.refresh(beneficiary)
        return beneficiary

    async def update_transfer_stats(
        self, beneficiary_id: int, amount_delta: float
    ) -> None:
        from decimal import Decimal
        from sqlalchemy import update
        await self.db.execute(
            update(Beneficiary)
            .where(Beneficiary.id == beneficiary_id)
            .values(
                transfer_count=Beneficiary.transfer_count + 1,
                total_transferred=Beneficiary.total_transferred + Decimal(str(amount_delta)),
            )
        )
