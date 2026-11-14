"""
Router principal da API v1 — agrega todos os sub-routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    simulation,
    audit,
    clients,
    beneficiaries,
    transactions,
    events,
    risk_analyses,
    demo,
    metrics,
    cards,
)

api_router = APIRouter()

# ── Etapa 1 (preservados) ────────────────────────────────────────────────────
api_router.include_router(health.router)
api_router.include_router(simulation.router, prefix="/simulation")
api_router.include_router(audit.router, prefix="/audit")

# ── Etapa 2 ──────────────────────────────────────────────────────────────────
api_router.include_router(clients.router, prefix="/clients")
api_router.include_router(beneficiaries.router, prefix="/beneficiaries")
api_router.include_router(transactions.router, prefix="/transactions")
api_router.include_router(cards.router, prefix="/cards")
api_router.include_router(events.router, prefix="/events")
api_router.include_router(risk_analyses.router, prefix="/risk-analyses")
api_router.include_router(demo.router, prefix="/demo")

# ── Etapa 8 — Métricas ───────────────────────────────────────────────────────
api_router.include_router(metrics.router, prefix="/metrics")
