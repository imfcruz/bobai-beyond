"""
Endpoint de auditoria — consulta logs de decisão dos agentes.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.schemas.schemas import AuditLogResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=list[AuditLogResponse],
    summary="Listar logs de auditoria",
    tags=["Audit"],
)
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get(
    "/transaction/{transaction_id}",
    response_model=list[AuditLogResponse],
    summary="Logs por transação",
    tags=["Audit"],
)
async def get_audit_logs_by_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.transaction_id == transaction_id)
        .order_by(AuditLog.created_at.asc())
    )
    return list(result.scalars().all())
