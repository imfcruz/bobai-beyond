"""
conftest.py — fixtures compartilhadas para todos os testes.
Usa banco em memória para isolamento total entre testes.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import create_app
from app.services.llm_client import reset_llm_client


@pytest.fixture(autouse=True)
def force_rules_mode_during_tests(monkeypatch):
    """Impede que a suíte consuma um provedor externo ou credenciais reais."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "AGENT_MODE", "auto")
    reset_llm_client()
    yield
    reset_llm_client()

# ── Engine em memória para testes ─────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Sessão de banco em memória, resetada a cada teste."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    # Registra todos os modelos
    from app.models import (  # noqa: F401
        audit_log,
        behavioral_history,
        beneficiary,
        client,
        contextual_event,
        risk_analysis,
        statement_entry,
        transaction,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def seeded_db(db_session: AsyncSession):
    """Banco em memória já populado com os três cenários."""
    from app.services.seed_service import seed_database
    summary = await seed_database(db_session)
    await db_session.commit()
    return db_session, summary


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Cliente HTTP com override de dependência para banco em memória."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def seeded_client(seeded_db):
    """Cliente HTTP com banco já populado."""
    db_session, summary = seeded_db
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, summary
