"""
MetricsService — calcula métricas de desempenho do pipeline multiagente.

Todas as métricas são derivadas de dados reais armazenados no banco.
Nenhum valor é inventado ou estático.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEFINIÇÃO DE CLASSE POSITIVA (para métricas de classificação)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Positivo  = operação de ALTO RISCO (risco ≥ medium ou ação ≠ approve)
              Rótulo de referência: campo `reference_label` atribuído
              EXTERNAMENTE nos cenários sintéticos.

  Negativo  = operação LEGÍTIMA (risco low E ação = approve)

DENOMINADORES:
  Precisão = TP / (TP + FP)         → entre as alertadas, fração correta
  Recall   = TP / (TP + FN)         → entre as reais, fração capturada
  F1       = 2 * P * R / (P + R)    → média harmônica

LIMITAÇÕES:
  - Rótulos de referência são definidos manualmente nos cenários sintéticos.
  - O simulador não possui ground truth de fraudes reais.
  - Resultados NÃO representam desempenho real em produção.
  - Métricas de classificação são válidas apenas para transações com
    `reference_label` atribuído (campo `purpose` codificado ou external_id
    prefixado com 'txn-scenario-').
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FÓRMULAS:
  avg_analysis_time_ms = mean(completed_at - started_at) para análises completas
  agent_avg_time_ms    = mean(execution_time_ms) por componente em audit_logs
  divergence_rate      = divergence_count / total_completed_analyses
  confirmation_rate    = confirmations / total
  human_review_rate    = human_reviews / total
  component_errors     = count(audit_logs WHERE result IN ('error','failed','timeout'))
"""

import json
import statistics
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.risk_analysis import RiskAnalysis, RiskAnalysisStatus
from app.models.transaction import RiskLevel, Transaction, TransactionStatus

logger = structlog.get_logger(__name__)

# ── Rótulos de referência para cenários sintéticos ────────────────────────────
# Definidos externamente, independentes das previsões dos agentes.
# Positivo = operação de alto risco real (engenharia social / fraude)
# Negativo = operação legítima

SCENARIO_REFERENCE_LABELS: dict[str, bool] = {
    "txn-scenario-a": False,   # Cenário A: operação legítima  → negativo
    "txn-scenario-b": True,    # Cenário B: risco real médio/alto → positivo
    "txn-scenario-c": True,    # Cenário C: engenharia social → positivo
}

# Statuses que indicam que o sistema sinalizou como suspeito (predição positiva)
PREDICTED_POSITIVE_STATUSES = {
    TransactionStatus.UNDER_VERIFICATION,
    TransactionStatus.AWAITING_CONFIRMATION,
    TransactionStatus.ESCALATED_TO_HUMAN,
    TransactionStatus.HUMAN_REVIEW_PENDING,
    TransactionStatus.REJECTED,
    TransactionStatus.HUMAN_REJECTED,
    TransactionStatus.BLOCKED,
}

# Statuses que indicam liberação (predição negativa)
PREDICTED_NEGATIVE_STATUSES = {
    TransactionStatus.RELEASED,
    TransactionStatus.APPROVED,
    TransactionStatus.HUMAN_APPROVED,
}

# Componentes dos agentes para análise de tempo
AGENT_COMPONENTS = [
    "fraud_agent",
    "inconsistency_agent",
    "behavioral_agent",
    "risk_agent",
    "orchestrator_agent",
    "decision_engine",
    "security_gateway",
]

# Resultados que indicam falha de componente
ERROR_RESULTS = {"error", "failed", "timeout", "failure", "exception"}


def _safe_mean(values: list[float]) -> float | None:
    """Média aritmética — retorna None se lista vazia."""
    if not values:
        return None
    return statistics.mean(values)


def _parse_agent_result(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


class MetricsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def compute_summary(self) -> dict[str, Any]:
        """
        Calcula o resumo completo de métricas.
        Retorna dict com todas as seções documentadas.
        """
        transactions = await self._fetch_all_transactions()
        analyses = await self._fetch_all_analyses()
        audit_logs = await self._fetch_all_audit_logs()

        total_txn = len(transactions)
        total_analyses = len(analyses)

        # ── 1. Volume total ────────────────────────────────────────────────────
        volume = {
            "total_transactions": total_txn,
            "total_analyses": total_analyses,
            "total_audit_logs": len(audit_logs),
        }

        # ── 2. Distribuição por nível de risco ────────────────────────────────
        risk_distribution = self._risk_distribution(transactions)

        # ── 3. Percentual de confirmação adicional ─────────────────────────────
        confirmation_count = sum(
            1 for t in transactions
            if t.status in (
                TransactionStatus.AWAITING_CONFIRMATION,
                TransactionStatus.UNDER_VERIFICATION,
                # também conta se passou pela fase 2 (analysis com confirmation_purpose)
            )
        )
        # Inclui análises que tiveram phase = confirmation
        confirmation_from_phase2 = sum(
            1 for a in analyses
            if a.confirmation_purpose is not None
        )
        confirmation_total = max(confirmation_count, confirmation_from_phase2)

        # ── 4. Percentual encaminhado para revisão humana ─────────────────────
        human_review_statuses = {
            TransactionStatus.HUMAN_REVIEW_PENDING,
            TransactionStatus.ESCALATED_TO_HUMAN,
            TransactionStatus.HUMAN_APPROVED,
            TransactionStatus.HUMAN_REJECTED,
        }
        human_review_count = sum(
            1 for t in transactions if t.status in human_review_statuses
        )

        rates = {
            "confirmation_rate": round(confirmation_total / total_txn, 4) if total_txn else None,
            "confirmation_count": confirmation_total,
            "human_review_rate": round(human_review_count / total_txn, 4) if total_txn else None,
            "human_review_count": human_review_count,
            "insufficient_data": total_txn < 3,
        }

        # ── 5. Tempo médio de análise ──────────────────────────────────────────
        timing = self._compute_timing(analyses, audit_logs)

        # ── 6. Tempo de execução por agente ───────────────────────────────────
        agent_timing = self._compute_agent_timing(audit_logs, analyses)

        # ── 7. Frequência de divergências ─────────────────────────────────────
        completed_analyses = [a for a in analyses if a.status == RiskAnalysisStatus.COMPLETED]
        divergence_count = sum(1 for a in completed_analyses if a.divergence_detected)
        divergence_metrics = {
            "divergence_count": divergence_count,
            "completed_analyses": len(completed_analyses),
            "divergence_rate": round(divergence_count / len(completed_analyses), 4)
            if completed_analyses else None,
        }

        # ── 8. Decisões auditadas ──────────────────────────────────────────────
        # Conta logs que representam decisões (não apenas eventos de sistema)
        decision_components = {"decision_engine", "security_gateway"}
        audited_decisions = sum(
            1 for log in audit_logs if log.component in decision_components
        )

        # ── 9. Falhas por componente ───────────────────────────────────────────
        component_failures = self._compute_failures(audit_logs)

        # ── 10. Distribuição de ações finais ──────────────────────────────────
        action_distribution = self._action_distribution(analyses)

        # ── Distribuição de status de transações ──────────────────────────────
        status_distribution = self._status_distribution(transactions)

        # ── Métricas de classificação (apenas para cenários com rótulo) ───────
        classification = self._compute_classification(transactions)

        # ── Breakdown por modo (AI_MODE vs RULES_MODE) ────────────────────────
        mode_breakdown = self._compute_mode_breakdown(analyses)

        # ── Score de risco: distribuição percentual ───────────────────────────
        risk_score_distribution = self._risk_score_buckets(analyses)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "volume": volume,
            "risk_distribution": risk_distribution,
            "rates": rates,
            "timing": timing,
            "agent_timing": agent_timing,
            "divergence": divergence_metrics,
            "audited_decisions": audited_decisions,
            "component_failures": component_failures,
            "action_distribution": action_distribution,
            "status_distribution": status_distribution,
            "classification": classification,
            "mode_breakdown": mode_breakdown,
            "risk_score_distribution": risk_score_distribution,
        }

    # ── helpers ────────────────────────────────────────────────────────────────

    async def _fetch_all_transactions(self) -> list[Transaction]:
        result = await self.db.execute(
            select(Transaction).order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def _fetch_all_analyses(self) -> list[RiskAnalysis]:
        result = await self.db.execute(
            select(RiskAnalysis).order_by(RiskAnalysis.created_at.desc())
        )
        return list(result.scalars().all())

    async def _fetch_all_audit_logs(self) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc())
        )
        return list(result.scalars().all())

    def _risk_distribution(self, transactions: list[Transaction]) -> dict:
        counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        total = len(transactions)
        for t in transactions:
            level = t.risk_level.value if hasattr(t.risk_level, "value") else str(t.risk_level)
            if level in counts:
                counts[level] += 1
        return {
            "counts": counts,
            "percentages": {
                k: round(v / total * 100, 1) if total else None
                for k, v in counts.items()
            },
            "total": total,
        }

    def _status_distribution(self, transactions: list[Transaction]) -> dict:
        counts: dict[str, int] = {}
        for t in transactions:
            s = t.status.value if hasattr(t.status, "value") else str(t.status)
            counts[s] = counts.get(s, 0) + 1
        total = len(transactions)
        return {
            "counts": counts,
            "percentages": {
                k: round(v / total * 100, 1) if total else None
                for k, v in counts.items()
            },
        }

    def _action_distribution(self, analyses: list[RiskAnalysis]) -> dict:
        counts: dict[str, int] = {
            "approve": 0, "request_confirmation": 0,
            "escalate_to_human": 0, "block": 0,
        }
        for a in analyses:
            action = a.recommended_action.value if hasattr(a.recommended_action, "value") else str(a.recommended_action)
            counts[action] = counts.get(action, 0) + 1
        total = len(analyses)
        return {
            "counts": counts,
            "percentages": {
                k: round(v / total * 100, 1) if total else None
                for k, v in counts.items()
            },
            "total": total,
        }

    def _compute_timing(
        self, analyses: list[RiskAnalysis], audit_logs: list[AuditLog]
    ) -> dict:
        durations_ms: list[float] = []
        for a in analyses:
            if a.started_at and a.completed_at:
                delta = (a.completed_at - a.started_at).total_seconds() * 1000
                if delta >= 0:
                    durations_ms.append(delta)

        # Também extrai de audit_logs com execution_time_ms
        audit_durations = [
            float(log.execution_time_ms)
            for log in audit_logs
            if log.execution_time_ms is not None and log.component == "bank_service"
        ]
        if audit_durations:
            durations_ms.extend(audit_durations)

        if not durations_ms:
            return {
                "avg_ms": None,
                "min_ms": None,
                "max_ms": None,
                "median_ms": None,
                "sample_size": 0,
                "insufficient_data": True,
            }

        return {
            "avg_ms": round(_safe_mean(durations_ms) or 0, 1),
            "min_ms": round(min(durations_ms), 1),
            "max_ms": round(max(durations_ms), 1),
            "median_ms": round(statistics.median(durations_ms), 1),
            "sample_size": len(durations_ms),
            "insufficient_data": len(durations_ms) < 2,
        }

    def _compute_agent_timing(
        self, audit_logs: list[AuditLog], analyses: list[RiskAnalysis]
    ) -> dict[str, dict]:
        """
        Para cada agente, calcula o tempo médio de execução.
        Fontes:
          1. audit_logs.execution_time_ms por component
          2. AgentResult.execution_time_ms embutido nos campos JSON das analyses
        """
        timing: dict[str, list[float]] = {c: [] for c in AGENT_COMPONENTS}

        # Fonte 1: audit_logs
        for log in audit_logs:
            comp = log.component
            if comp in timing and log.execution_time_ms is not None:
                timing[comp].append(float(log.execution_time_ms))

        # Fonte 2: agent result JSON nos campos da análise
        agent_field_map = {
            "fraud_agent": "fraud_agent_result",
            "inconsistency_agent": "inconsistency_agent_result",
            "behavioral_agent": "behavioral_agent_result",
            "risk_agent": "risk_agent_result",
            "orchestrator_agent": "orchestrator_result",
        }
        for a in analyses:
            for agent_key, field in agent_field_map.items():
                raw = getattr(a, field, None)
                parsed = _parse_agent_result(raw)
                if parsed and isinstance(parsed.get("execution_time_ms"), (int, float)):
                    timing[agent_key].append(float(parsed["execution_time_ms"]))

        result = {}
        for comp, values in timing.items():
            if values:
                result[comp] = {
                    "avg_ms": round(_safe_mean(values) or 0, 1),
                    "min_ms": round(min(values), 1),
                    "max_ms": round(max(values), 1),
                    "sample_size": len(values),
                    "insufficient_data": len(values) < 2,
                }
            else:
                result[comp] = {
                    "avg_ms": None, "min_ms": None, "max_ms": None,
                    "sample_size": 0, "insufficient_data": True,
                }
        return result

    def _compute_failures(self, audit_logs: list[AuditLog]) -> dict[str, int]:
        """Conta falhas por componente (result ∈ ERROR_RESULTS)."""
        failures: dict[str, int] = {}
        for log in audit_logs:
            result_val = (log.result or "").lower()
            if any(e in result_val for e in ERROR_RESULTS):
                failures[log.component] = failures.get(log.component, 0) + 1
        return failures

    def _compute_classification(self, transactions: list[Transaction]) -> dict:
        """
        Métricas de classificação apenas para transações com rótulo de referência.
        Positivo = operação de alto risco.
        """
        labeled = [
            t for t in transactions
            if t.external_id in SCENARIO_REFERENCE_LABELS
        ]
        if len(labeled) < 2:
            return {
                "available": False,
                "reason": "Menos de 2 transações com rótulo de referência disponíveis.",
                "labeled_count": len(labeled),
                "definition": {
                    "positive_class": "Operação de alto risco (risco ≥ medium ou ação ≠ approve)",
                    "negative_class": "Operação legítima (risco low, ação approve)",
                    "reference_labels": SCENARIO_REFERENCE_LABELS,
                    "prediction_rule": "Status em {under_verification, awaiting_confirmation, escalated_to_human, human_review_pending, rejected, ...} → POSITIVO",
                },
            }

        tp = fp = tn = fn = 0
        details = []
        for t in labeled:
            ref_positive = SCENARIO_REFERENCE_LABELS[t.external_id]
            status = t.status if isinstance(t.status, TransactionStatus) else TransactionStatus(t.status)
            pred_positive = status in PREDICTED_POSITIVE_STATUSES

            if ref_positive and pred_positive:
                tp += 1
                classification_result = "TP"
            elif not ref_positive and pred_positive:
                fp += 1
                classification_result = "FP"
            elif ref_positive and not pred_positive:
                fn += 1
                classification_result = "FN"
            else:
                tn += 1
                classification_result = "TN"

            details.append({
                "external_id": t.external_id,
                "reference_label": "positive" if ref_positive else "negative",
                "predicted": "positive" if pred_positive else "negative",
                "status": status.value,
                "risk_level": t.risk_level.value if hasattr(t.risk_level, "value") else str(t.risk_level),
                "classification": classification_result,
            })

        # Métricas
        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None
        f1 = (2 * precision * recall / (precision + recall)) if (precision and recall) else None
        accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else None

        return {
            "available": True,
            "labeled_count": len(labeled),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1_score": round(f1, 4) if f1 is not None else None,
            "accuracy": round(accuracy, 4) if accuracy is not None else None,
            "details": details,
            "definition": {
                "positive_class": "Operação de alto risco (risco ≥ medium ou ação ≠ approve)",
                "negative_class": "Operação legítima (risco low, ação approve)",
                "precision_formula": "TP / (TP + FP)",
                "recall_formula": "TP / (TP + FN)",
                "f1_formula": "2 × Precisão × Recall / (Precisão + Recall)",
                "disclaimer": (
                    "Métricas calculadas sobre cenários sintéticos com rótulos definidos manualmente. "
                    "NÃO representam evidência de redução real de fraudes no Banco do Brasil."
                ),
            },
        }

    def _compute_mode_breakdown(self, analyses: list[RiskAnalysis]) -> dict:
        """Quebra por modo de execução lido dos campos JSON dos agentes."""
        ai_mode_count = 0
        rules_mode_count = 0
        unknown_count = 0

        for a in analyses:
            # Verifica o modo do agente de risco (último a executar, mais representativo)
            parsed = _parse_agent_result(a.risk_agent_result) or _parse_agent_result(a.fraud_agent_result)
            if parsed:
                mode = parsed.get("mode", "")
                if mode == "AI_MODE":
                    ai_mode_count += 1
                elif mode == "RULES_MODE":
                    rules_mode_count += 1
                else:
                    unknown_count += 1
            else:
                unknown_count += 1

        return {
            "AI_MODE": ai_mode_count,
            "RULES_MODE": rules_mode_count,
            "unknown": unknown_count,
            "total": len(analyses),
        }

    def _risk_score_buckets(self, analyses: list[RiskAnalysis]) -> list[dict]:
        """Agrupa scores de risco em buckets de 10%."""
        buckets = [0] * 10  # [0-10), [10-20), ..., [90-100]
        for a in analyses:
            score = a.overall_risk_score
            idx = min(int(score * 10), 9)
            buckets[idx] += 1
        total = len(analyses)
        return [
            {
                "range": f"{i*10}-{i*10+10}%",
                "count": buckets[i],
                "percentage": round(buckets[i] / total * 100, 1) if total else 0,
            }
            for i in range(10)
        ]
