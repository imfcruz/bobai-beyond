"""
SeedService — popula dados sintéticos determinísticos para os três cenários de demo.

Todos os dados são fictícios. Nenhuma operação financeira real é realizada.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.behavioral_history import BehavioralHistory
from app.models.beneficiary import Beneficiary
from app.models.client import Client, ClientRiskProfile
from app.models.contextual_event import ContextualEvent, EventType
from app.models.risk_analysis import RiskAnalysis, RiskAnalysisStatus, RecommendedAction
from app.models.statement_entry import StatementEntry, EntryType, EntryStatus
from app.models.transaction import RiskLevel, Transaction, TransactionStatus
from app.models.card import CreditCard, CreditLimitRequest

logger = structlog.get_logger(__name__)

# ── IDs externos estáveis — permitem referenciar nos testes ──────────────────

CLIENT_A_EXT = "client-ana-costa"
CLIENT_B_EXT = "client-carlos-mendes"
CLIENT_C_EXT = "client-beatriz-santos"

BEN_KNOWN_A1 = "ben-fornecedor-alpha"    # Beneficiário conhecido de Ana
BEN_KNOWN_A2 = "ben-escritorio-beta"
BEN_NEW_B1 = "ben-empresa-xpto"          # Novo beneficiário (Cenário B)
BEN_NEW_C1 = "ben-conta-seguranca"       # Novo beneficiário suspeito (Cenário C)

TXN_A = "txn-scenario-a"
TXN_B = "txn-scenario-b"
TXN_C = "txn-scenario-c"

ANALYSIS_A = "analysis-scenario-a"
ANALYSIS_B = "analysis-scenario-b"
ANALYSIS_C = "analysis-scenario-c"


def _utc(minutes_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)


async def seed_database(db: AsyncSession) -> dict:
    """
    Apaga todos os dados existentes e recria os cenários de demonstração.
    Retorna um resumo do que foi criado.
    """
    logger.info("Starting database seed")

    # ── 1. Limpar dados existentes (ordem inversa de FK) ─────────────────────
    for model in [AuditLog, RiskAnalysis, ContextualEvent, CreditLimitRequest,
                  StatementEntry, Transaction, CreditCard, BehavioralHistory,
                  Beneficiary, Client]:
        await db.execute(delete(model))
    await db.flush()
    logger.info("Existing data cleared")

    # ── 2. Criar Clientes ─────────────────────────────────────────────────────
    ana = Client(
        external_id=CLIENT_A_EXT,
        name="Ana Costa",
        document_hint="***.***.***-01",
        agency="0001",
        account_number="45800-1",
        account_type="Conta Corrente",
        balance=Decimal("45000.00"),
        reserved_balance=Decimal("0.00"),
        transfer_limit=Decimal("8000.00"),
        risk_profile=ClientRiskProfile.LOW,
        account_age_days=1825,
        metadata_json=json.dumps({"canal_habitual": "mobile", "cidade": "São Paulo"}),
    )
    carlos = Client(
        external_id=CLIENT_B_EXT,
        name="Carlos Mendes",
        document_hint="***.***.***-02",
        agency="0002",
        account_number="12003-5",
        account_type="Conta Corrente",
        balance=Decimal("120000.00"),
        reserved_balance=Decimal("0.00"),
        transfer_limit=Decimal("30000.00"),
        risk_profile=ClientRiskProfile.MEDIUM,
        account_age_days=730,
        metadata_json=json.dumps({"canal_habitual": "web", "cidade": "Rio de Janeiro"}),
    )
    beatriz = Client(
        external_id=CLIENT_C_EXT,
        name="Beatriz Santos",
        document_hint="***.***.***-03",
        agency="0003",
        account_number="89100-2",
        account_type="Conta Poupança",
        balance=Decimal("28000.00"),
        reserved_balance=Decimal("0.00"),
        transfer_limit=Decimal("25000.00"),
        risk_profile=ClientRiskProfile.LOW,
        account_age_days=2190,
        metadata_json=json.dumps({"canal_habitual": "mobile", "cidade": "Belo Horizonte"}),
    )
    db.add_all([ana, carlos, beatriz])
    await db.flush()

    cards = await ensure_credit_cards(db, [ana, carlos, beatriz])

    # ── 3. Criar Beneficiários ────────────────────────────────────────────────
    ben_alpha = Beneficiary(
        external_id=BEN_KNOWN_A1,
        client_id=ana.id,
        name="Fornecedor Alpha Ltda",
        account_hint="Ag. 0001 / C/C 12345-6 (fictício)",
        bank_name="BBD Parceiros",
        is_known=True,
        transfer_count=24,
        total_transferred=Decimal("28800.00"),
        risk_hint=0.05,
        is_favorite=True,
    )
    ben_beta = Beneficiary(
        external_id=BEN_KNOWN_A2,
        client_id=ana.id,
        name="Escritório Beta",
        account_hint="Ag. 0002 / C/C 54321-0 (fictício)",
        bank_name="Banco Fictício B",
        is_known=True,
        transfer_count=12,
        total_transferred=Decimal("14400.00"),
        risk_hint=0.05,
        is_favorite=True,
    )
    ben_xpto = Beneficiary(
        external_id=BEN_NEW_B1,
        client_id=carlos.id,
        name="Empresa Desconhecida XPTO",
        account_hint="Chave Pix: xpto@email.com (fictício)",
        bank_name="Banco Fictício C",
        is_known=False,
        transfer_count=0,
        total_transferred=Decimal("0.00"),
        risk_hint=0.45,
    )
    ben_seg = Beneficiary(
        external_id=BEN_NEW_C1,
        client_id=beatriz.id,
        name="Conta Segurança BB",
        account_hint="Chave Pix: seguranca@ficticio.com",
        bank_name="Banco Fictício BB",
        is_known=False,
        transfer_count=0,
        total_transferred=Decimal("0.00"),
        risk_hint=0.85,
    )
    db.add_all([ben_alpha, ben_beta, ben_xpto, ben_seg])
    await db.flush()
    contacts = await ensure_demo_contacts(db, [ana, carlos, beatriz])

    # ── 4. Criar Histórico Comportamental ─────────────────────────────────────
    bh_ana = BehavioralHistory(
        client_id=ana.id,
        avg_transfer_value=Decimal("1200.00"),
        max_transfer_value=Decimal("3500.00"),
        min_transfer_value=Decimal("150.00"),
        avg_monthly_transactions=8,
        recurring_beneficiary_ids=json.dumps([BEN_KNOWN_A1, BEN_KNOWN_A2]),
        typical_hours=json.dumps(["09:00-12:00", "14:00-18:00"]),
        typical_channels=json.dumps(["mobile"]),
    )
    bh_carlos = BehavioralHistory(
        client_id=carlos.id,
        avg_transfer_value=Decimal("3500.00"),
        max_transfer_value=Decimal("8000.00"),
        min_transfer_value=Decimal("500.00"),
        avg_monthly_transactions=15,
        recurring_beneficiary_ids=json.dumps([]),
        typical_hours=json.dumps(["10:00-12:00", "15:00-17:00"]),
        typical_channels=json.dumps(["web"]),
    )
    bh_beatriz = BehavioralHistory(
        client_id=beatriz.id,
        avg_transfer_value=Decimal("450.00"),
        max_transfer_value=Decimal("1200.00"),
        min_transfer_value=Decimal("50.00"),
        avg_monthly_transactions=3,
        recurring_beneficiary_ids=json.dumps([]),
        typical_hours=json.dumps(["09:00-11:00"]),
        typical_channels=json.dumps(["mobile"]),
    )
    db.add_all([bh_ana, bh_carlos, bh_beatriz])
    await db.flush()

    # ── 5. Cenário A — Operação Normal ────────────────────────────────────────
    corr_a = str(uuid.uuid4())[:8]
    txn_a = Transaction(
        external_id=TXN_A,
        client_id=ana.id,
        beneficiary_id=ben_alpha.id,
        amount=Decimal("1100.00"),
        currency="BRL",
        purpose="Pagamento mensal de serviços — Fornecedor Alpha",
        is_new_recipient=False,
        recent_limit_change=False,
        device_recognized=True,
        risk_level=RiskLevel.LOW,
        risk_score=0.08,
        status=TransactionStatus.RELEASED,
        decision_reasoning="Operação dentro do padrão histórico. Beneficiário conhecido. Valor habitual.",
        settlement_applied=True,  # Já liquidado no seed
    )
    db.add(txn_a)
    await db.flush()

    # Debitar saldo de Ana (R$ 45.000 − R$ 1.100 = R$ 43.900)
    ana.balance = Decimal("43900.00")
    db.add(ana)
    # Atualizar beneficiário
    ben_alpha.transfer_count += 1
    ben_alpha.total_transferred += Decimal("1100.00")
    db.add(ben_alpha)
    # Lançamento de débito no extrato
    stmt_a = StatementEntry(
        client_id=ana.id,
        transaction_id=txn_a.id,
        entry_type=EntryType.DEBIT,
        amount=Decimal("1100.00"),
        currency="BRL",
        description="Transferência para Fornecedor Alpha Ltda — Pagamento mensal de serviços",
        counterpart_name="Fornecedor Alpha Ltda",
        counterpart_bank="Banco Fictício A",
        status=EntryStatus.POSTED,
        balance_after=Decimal("43900.00"),
        posted_at=_utc(27),
    )
    db.add(stmt_a)

    ev_a1 = ContextualEvent(
        client_id=ana.id, transaction_id=txn_a.id,
        event_type=EventType.LOGIN, correlation_id=corr_a,
        occurred_at=_utc(30),
        metadata_json=json.dumps({"canal": "mobile", "dispositivo_reconhecido": True}),
    )
    ev_a2 = ContextualEvent(
        client_id=ana.id, transaction_id=txn_a.id,
        event_type=EventType.INICIO_TRANSFERENCIA, correlation_id=corr_a,
        occurred_at=_utc(28),
        metadata_json=json.dumps({"beneficiario": BEN_KNOWN_A1, "valor": "1100.00"}),
    )
    db.add_all([ev_a1, ev_a2])

    analysis_a = RiskAnalysis(
        external_id=ANALYSIS_A,
        transaction_id=txn_a.id,
        overall_risk_score=0.08,
        risk_level="low",
        recommended_action=RecommendedAction.APPROVE,
        reasoning="Transação habitual. Beneficiário recorrente. Valor dentro da média histórica de R$ 1.200.",
        flags=json.dumps([]),
        status=RiskAnalysisStatus.COMPLETED,
        started_at=_utc(27),
        completed_at=_utc(27),
    )
    db.add(analysis_a)

    # ── 6. Cenário B — Operação Incomum ───────────────────────────────────────
    corr_b = str(uuid.uuid4())[:8]
    txn_b = Transaction(
        external_id=TXN_B,
        client_id=carlos.id,
        beneficiary_id=ben_xpto.id,
        amount=Decimal("15000.00"),
        currency="BRL",
        purpose="Investimento em parceria comercial",
        is_new_recipient=True,
        recent_limit_change=False,
        device_recognized=True,
        risk_level=RiskLevel.MEDIUM,
        risk_score=0.52,
        status=TransactionStatus.UNDER_VERIFICATION,
        decision_reasoning="Beneficiário novo. Valor 4x acima da média histórica. Solicitada confirmação contextual.",
    )
    db.add(txn_b)
    await db.flush()

    # Reservar saldo de Carlos (em verificação)
    carlos.reserved_balance = Decimal("15000.00")
    db.add(carlos)
    stmt_b_reserve = StatementEntry(
        client_id=carlos.id,
        transaction_id=txn_b.id,
        entry_type=EntryType.RESERVE,
        amount=Decimal("15000.00"),
        currency="BRL",
        description="Reserva de saldo — transferência em análise",
        status=EntryStatus.PENDING,
        balance_after=Decimal("105000.00"),
        posted_at=_utc(45),
    )
    db.add(stmt_b_reserve)

    ev_b1 = ContextualEvent(
        client_id=carlos.id, transaction_id=txn_b.id,
        event_type=EventType.LOGIN, correlation_id=corr_b,
        occurred_at=_utc(60),
        metadata_json=json.dumps({"canal": "web", "dispositivo_reconhecido": True}),
    )
    ev_b2 = ContextualEvent(
        client_id=carlos.id, transaction_id=txn_b.id,
        event_type=EventType.CADASTRO_BENEFICIARIO, correlation_id=corr_b,
        occurred_at=_utc(50),
        metadata_json=json.dumps({"beneficiario": BEN_NEW_B1, "is_new": True}),
    )
    ev_b3 = ContextualEvent(
        client_id=carlos.id, transaction_id=txn_b.id,
        event_type=EventType.INICIO_TRANSFERENCIA, correlation_id=corr_b,
        occurred_at=_utc(45),
        metadata_json=json.dumps({"beneficiario": BEN_NEW_B1, "valor": "15000.00"}),
    )
    db.add_all([ev_b1, ev_b2, ev_b3])

    analysis_b = RiskAnalysis(
        external_id=ANALYSIS_B,
        transaction_id=txn_b.id,
        overall_risk_score=0.52,
        risk_level="medium",
        recommended_action=RecommendedAction.REQUEST_CONFIRMATION,
        reasoning=(
            "Beneficiário cadastrado há menos de 1h. "
            "Valor R$ 15.000 é 4,3x a média histórica de R$ 3.500. "
            "Operação incomum mas sem indício explícito de coerção."
        ),
        flags=json.dumps(["new_beneficiary", "above_avg_value"]),
        status=RiskAnalysisStatus.COMPLETED,
        started_at=_utc(44),
        completed_at=_utc(44),
    )
    db.add(analysis_b)

    # ── 7. Cenário C — Possível Engenharia Social ─────────────────────────────
    corr_c = str(uuid.uuid4())[:8]
    txn_c = Transaction(
        external_id=TXN_C,
        client_id=beatriz.id,
        beneficiary_id=ben_seg.id,
        amount=Decimal("17000.00"),
        currency="BRL",
        purpose="Uma pessoa disse ser do banco e pediu para eu transferir para proteger minha conta",
        is_new_recipient=True,
        recent_limit_change=True,
        device_recognized=True,
        risk_level=RiskLevel.CRITICAL,
        risk_score=0.92,
        status=TransactionStatus.ESCALATED_TO_HUMAN,
        decision_reasoning=(
            "ALERTA CRÍTICO: Indícios fortes de engenharia social. "
            "Sequência: alteração de limite → cadastro de beneficiário novo → "
            "transferência 38x acima da média → declaração de instrução de terceiro. "
            "Encaminhado para análise humana."
        ),
    )
    db.add(txn_c)
    await db.flush()

    # Nota: Para o cenário C (engenharia social), NÃO reservamos saldo no seed.
    # O cenário é demonstrativo — a transação foi escalada e está em análise.
    # A reserva é feita em tempo real apenas para novas transferências.
    # Manter saldo disponível de Beatriz para permitir testes adicionais.

    ev_c1 = ContextualEvent(
        client_id=beatriz.id, transaction_id=txn_c.id,
        event_type=EventType.LOGIN, correlation_id=corr_c,
        occurred_at=_utc(90),
        metadata_json=json.dumps({"canal": "mobile", "dispositivo_reconhecido": True}),
    )
    ev_c2 = ContextualEvent(
        client_id=beatriz.id, transaction_id=txn_c.id,
        event_type=EventType.ALTERACAO_LIMITE, correlation_id=corr_c,
        occurred_at=_utc(80),
        metadata_json=json.dumps({"limite_anterior": "5000.00", "limite_novo": "20000.00"}),
    )
    ev_c3 = ContextualEvent(
        client_id=beatriz.id, transaction_id=txn_c.id,
        event_type=EventType.CADASTRO_BENEFICIARIO, correlation_id=corr_c,
        occurred_at=_utc(70),
        metadata_json=json.dumps({"beneficiario": BEN_NEW_C1, "is_new": True}),
    )
    ev_c4 = ContextualEvent(
        client_id=beatriz.id, transaction_id=txn_c.id,
        event_type=EventType.INICIO_TRANSFERENCIA, correlation_id=corr_c,
        occurred_at=_utc(65),
        metadata_json=json.dumps({"beneficiario": BEN_NEW_C1, "valor": "17000.00"}),
    )
    ev_c5 = ContextualEvent(
        client_id=beatriz.id, transaction_id=txn_c.id,
        event_type=EventType.CONFIRMACAO_CONTEXTUAL, correlation_id=corr_c,
        occurred_at=_utc(63),
        metadata_json=json.dumps({"pergunta": "Qual é a finalidade desta transferência?"}),
    )
    ev_c6 = ContextualEvent(
        client_id=beatriz.id, transaction_id=txn_c.id,
        event_type=EventType.RESPOSTA_CLIENTE, correlation_id=corr_c,
        occurred_at=_utc(60),
        metadata_json=json.dumps({
            "resposta": "Uma pessoa disse ser funcionário do banco e pediu para eu transferir para proteger minha conta."
        }),
    )
    db.add_all([ev_c1, ev_c2, ev_c3, ev_c4, ev_c5, ev_c6])

    analysis_c = RiskAnalysis(
        external_id=ANALYSIS_C,
        transaction_id=txn_c.id,
        overall_risk_score=0.92,
        risk_level="critical",
        recommended_action=RecommendedAction.ESCALATE_TO_HUMAN,
        reasoning=(
            "ENGENHARIA SOCIAL IDENTIFICADA. Sequência suspeita em 30 minutos: "
            "(1) Alteração de limite de R$ 5.000 para R$ 20.000; "
            "(2) Cadastro imediato de beneficiário desconhecido; "
            "(3) Transferência de R$ 17.000 — 38x a média de R$ 450; "
            "(4) Cliente declarou estar agindo por instrução de suposto funcionário do banco. "
            "Nenhum funcionário do banco solicita transferências por telefone."
        ),
        flags=json.dumps([
            "recent_limit_change",
            "new_beneficiary",
            "far_above_avg_value",
            "third_party_instruction",
            "social_engineering_pattern",
        ]),
        status=RiskAnalysisStatus.COMPLETED,
        started_at=_utc(59),
        completed_at=_utc(59),
    )
    db.add(analysis_c)

    await db.flush()

    # ── 8. Audit logs iniciais ────────────────────────────────────────────────
    audit_entries = [
        AuditLog(
            transaction_id=txn_a.id, component="seed_service", agent_name="seed_service",
            action="transaction_created", event="SCENARIO_A_SEEDED", result="released",
            reasoning="Cenário A: operação normal — liberada.", correlation_id=corr_a,
            risk_score=0.08,
        ),
        AuditLog(
            transaction_id=txn_b.id, component="seed_service", agent_name="seed_service",
            action="transaction_created", event="SCENARIO_B_SEEDED", result="under_verification",
            reasoning="Cenário B: operação incomum — em verificação.", correlation_id=corr_b,
            risk_score=0.52,
        ),
        AuditLog(
            transaction_id=txn_c.id, component="seed_service", agent_name="seed_service",
            action="transaction_created", event="SCENARIO_C_SEEDED", result="escalated_to_human",
            reasoning="Cenário C: possível engenharia social — escalado.", correlation_id=corr_c,
            risk_score=0.92,
        ),
    ]
    db.add_all(audit_entries)
    await db.flush()

    summary = {
        "clients": 3,
        "credit_cards": len(cards),
        "beneficiaries": 4 + len(contacts),
        "transactions": 3,
        "statement_entries": 2,
        "contextual_events": 10,
        "behavioral_histories": 3,
        "risk_analyses": 3,
        "audit_logs": 3,
        "scenarios": {
            "A": {"external_id": TXN_A, "status": "released", "risk": "low", "settled": True},
            "B": {"external_id": TXN_B, "status": "under_verification", "risk": "medium", "reserved": "15000.00"},
            "C": {"external_id": TXN_C, "status": "escalated_to_human", "risk": "critical"},
        },
    }
    logger.info("Seed completed", **summary)
    return summary


async def ensure_credit_cards(
    db: AsyncSession, clients: list[Client] | None = None
) -> list[CreditCard]:
    """Cria um cartão sintético para clientes antigos sem apagar dados existentes."""
    if clients is None:
        clients = list((await db.execute(select(Client).order_by(Client.id))).scalars().all())
    defaults = {
        CLIENT_A_EXT: ("card-ana-ourocard", "•••• 4580", "12000.00", "2850.00", "#3333BD", "#465EFF"),
        CLIENT_B_EXT: ("card-carlos-ourocard", "•••• 1200", "28000.00", "9400.00", "#111827", "#465EFF"),
        CLIENT_C_EXT: ("card-beatriz-ourocard", "•••• 8910", "7000.00", "1250.00", "#3333BD", "#7C3AED"),
    }
    created: list[CreditCard] = []
    for index, client in enumerate(clients, start=1):
        existing = await db.execute(select(CreditCard).where(CreditCard.client_id == client.id))
        if existing.scalars().first() is not None:
            continue
        external_id, masked, limit, used, start, end = defaults.get(
            client.external_id,
            (f"card-{client.external_id}", f"•••• {index:04d}", "5000.00", "0.00", "#3333BD", "#465EFF"),
        )
        card = CreditCard(
            external_id=external_id, client_id=client.id, nickname="Ourocard Visa",
            masked_number=masked, brand="Visa", color_start=start, color_end=end,
            credit_limit=Decimal(limit), used_credit=Decimal(used), reserved_credit=Decimal("0.00"),
            due_day=10 + index, closing_day=3 + index,
        )
        db.add(card)
        created.append(card)
    await db.flush()
    return created


async def ensure_demo_contacts(
    db: AsyncSession, clients: list[Client] | None = None, target_per_client: int = 10
) -> list[Beneficiary]:
    """Completa uma agenda sintética sem remover os contatos dos cenários."""
    if clients is None:
        clients = list((await db.execute(select(Client).order_by(Client.id))).scalars().all())

    templates = [
        ("marina-oliveira", "Marina Oliveira", "marina.oliveira@pix.demo", "Banco Horizonte"),
        ("rafael-lima", "Rafael Lima", "+55 11 90000-1201", "Banco Atlântico"),
        ("camila-rocha", "Camila Rocha", "camila.rocha@pix.demo", "Banco Aurora"),
        ("lucas-ferreira", "Lucas Ferreira", "+55 21 90000-2458", "Banco Centralis"),
        ("julia-almeida", "Júlia Almeida", "julia.almeida@pix.demo", "Banco Horizonte"),
        ("gabriel-souza", "Gabriel Souza", "+55 31 90000-7724", "Banco Aurora"),
        ("renata-martins", "Renata Martins", "renata.martins@pix.demo", "Banco Atlântico"),
        ("pedro-nunes", "Pedro Nunes", "+55 41 90000-8190", "Banco Centralis"),
        ("larissa-freitas", "Larissa Freitas", "larissa.freitas@pix.demo", "Banco Horizonte"),
        ("techlab-servicos", "TechLab Serviços", "financeiro@techlab.demo", "Banco Aurora"),
    ]
    created: list[Beneficiary] = []
    for client in clients:
        current = list((await db.execute(
            select(Beneficiary).where(Beneficiary.client_id == client.id).order_by(Beneficiary.id)
        )).scalars().all())
        missing = max(0, target_per_client - len(current))
        existing_ids = {item.external_id for item in current}
        for index, (slug, name, pix, bank) in enumerate(templates):
            if missing <= 0:
                break
            external_id = f"contact-{client.external_id}-{slug}"
            if external_id in existing_ids:
                continue
            contact = Beneficiary(
                external_id=external_id,
                client_id=client.id,
                name=name,
                account_hint=f"Chave Pix: {pix} (fictícia)",
                bank_name=bank,
                is_known=index < 7,
                is_favorite=index < 3,
                transfer_count=max(0, 14 - index * 2),
                total_transferred=Decimal(str(max(0, 8400 - index * 750))),
                risk_hint=0.04 if index < 7 else 0.18,
                first_registered_at=_utc(1440 * (90 - index * 5)),
            )
            db.add(contact)
            created.append(contact)
            existing_ids.add(external_id)
            missing -= 1
    await db.flush()
    return created
