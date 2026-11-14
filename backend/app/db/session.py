"""
Sessão e engine do banco de dados SQLite (async).
"""

import os
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """Base para todos os modelos SQLAlchemy."""
    pass


def _ensure_data_dir() -> None:
    """Garante que o diretório de dados existe."""
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    data_dir = Path(db_path).parent
    data_dir.mkdir(parents=True, exist_ok=True)


engine = None
AsyncSessionLocal = None


def _build_engine():
    global engine, AsyncSessionLocal
    _ensure_data_dir()
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def init_db() -> None:
    """Cria todas as tabelas definidas nos modelos."""
    if engine is None:
        _build_engine()
    # Import all models to register them with Base before create_all
    from app.models import (  # noqa: F401
        client,
        beneficiary,
        transaction,
        contextual_event,
        behavioral_history,
        risk_analysis,
        audit_log,
        statement_entry,
        card,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_sqlite_compatibility_migrations)
    logger.info("All tables created/verified", url=settings.DATABASE_URL)


def _apply_sqlite_compatibility_migrations(sync_conn) -> None:
    """Evolui o SQLite local sem apagar os dados da demonstração.

    O projeto acadêmico ainda não usa Alembic. Estas alterações aditivas mantêm
    bancos criados por versões anteriores compatíveis com Pix no crédito.
    """
    if sync_conn.dialect.name != "sqlite":
        return

    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    if "transactions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("transactions")}
    migrations = {
        "card_id": "ALTER TABLE transactions ADD COLUMN card_id INTEGER",
        "funding_source": (
            "ALTER TABLE transactions ADD COLUMN funding_source VARCHAR(16) "
            "NOT NULL DEFAULT 'DEBIT'"
        ),
        "credit_reservation_applied": (
            "ALTER TABLE transactions ADD COLUMN credit_reservation_applied BOOLEAN "
            "NOT NULL DEFAULT 0"
        ),
    }
    for column, statement in migrations.items():
        if column not in columns:
            sync_conn.execute(text(statement))

    if "beneficiaries" in inspector.get_table_names():
        beneficiary_columns = {
            column["name"] for column in inspector.get_columns("beneficiaries")
        }
        if "is_favorite" not in beneficiary_columns:
            sync_conn.execute(text(
                "ALTER TABLE beneficiaries ADD COLUMN is_favorite BOOLEAN "
                "NOT NULL DEFAULT 0"
            ))


async def get_db():
    """Dependency injection: fornece uma sessão de banco de dados."""
    if AsyncSessionLocal is None:
        _build_engine()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
