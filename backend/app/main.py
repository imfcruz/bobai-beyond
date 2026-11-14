"""
Adaptive Security MVP — aplicação FastAPI principal.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.api.v1.router import api_router
from app.db.session import init_db, AsyncSessionLocal, _build_engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa recursos na subida e os libera no encerramento."""
    configure_logging()
    logger.info("Starting Adaptive Security MVP", env=settings.ENVIRONMENT)
    await init_db()
    logger.info("Database initialized")

    # Seed automático apenas se o banco estiver vazio
    if settings.ENVIRONMENT == "development":
        await _auto_seed_if_empty()

    yield
    logger.info("Shutting down Adaptive Security MVP")


async def _auto_seed_if_empty() -> None:
    """Popula o banco com dados sintéticos se estiver vazio (dev only)."""
    import app.db.session as _db
    if _db.AsyncSessionLocal is None:
        _db._build_engine()
    from sqlalchemy import select, func
    from app.models.client import Client

    async with _db.AsyncSessionLocal() as session:
        count = (await session.execute(select(func.count()).select_from(Client))).scalar_one()
        if count == 0:
            from app.services.seed_service import seed_database
            summary = await seed_database(session)
            await session.commit()
            logger.info("Auto-seed completed", **summary)
        else:
            from app.services.seed_service import ensure_credit_cards, ensure_demo_contacts
            cards = await ensure_credit_cards(session)
            contacts = await ensure_demo_contacts(session)
            await session.commit()
            logger.info(
                "Database already seeded; additive demo data verified",
                clients=count,
                cards_created=len(cards),
                contacts_created=len(contacts),
            )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "MVP Acadêmico de Segurança Adaptativa para Operações Financeiras Digitais. "
            "Simulação local com dados sintéticos — sem APIs bancárias reais."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Error handlers ────────────────────────────────────────────────────────
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
