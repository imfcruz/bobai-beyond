"""
Repositório de RiskAnalysis.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_analysis import RiskAnalysis, RiskAnalysisStatus


class RiskAnalysisRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, analysis_id: int) -> RiskAnalysis | None:
        result = await self.db.execute(
            select(RiskAnalysis).where(RiskAnalysis.id == analysis_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> RiskAnalysis | None:
        result = await self.db.execute(
            select(RiskAnalysis).where(RiskAnalysis.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_by_transaction(self, transaction_id: int) -> RiskAnalysis | None:
        result = await self.db.execute(
            select(RiskAnalysis).where(RiskAnalysis.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[RiskAnalysis]:
        result = await self.db.execute(
            select(RiskAnalysis)
            .order_by(RiskAnalysis.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, analysis: RiskAnalysis) -> RiskAnalysis:
        self.db.add(analysis)
        await self.db.flush()
        await self.db.refresh(analysis)
        return analysis

    async def update_status(
        self, analysis: RiskAnalysis, status: RiskAnalysisStatus
    ) -> RiskAnalysis:
        analysis.status = status
        await self.db.flush()
        return analysis
