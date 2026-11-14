/**
 * Testes de métricas do frontend — valida utilitários de cálculo e tipos.
 *
 * Cobrem:
 * - Cálculo de percentual a partir de contagens
 * - Formatação de scores e taxas
 * - Verificação de estrutura de tipos MetricsSummary
 * - Funções de cor por nível de risco
 * - Cálculo de F1-Score
 * - Determinação de classe (positiva/negativa) por status
 */

import { describe, it, expect } from 'vitest'
import type {
  MetricsSummary,
  ClassificationMetrics,
  ModeBreakdown,
  RiskScoreBucket,
} from '../types/metrics'

// ── Funções utilitárias puras (extraídas da lógica da página) ─────────────────

function calcRate(count: number, total: number): number | null {
  if (total === 0) return null
  return count / total
}

function pct(value: number | null): string {
  if (value == null) return 'Dados insuficientes'
  return `${(value * 100).toFixed(1)}%`
}

function calcF1(precision: number | null, recall: number | null): number | null {
  if (precision == null || recall == null) return null
  if (precision + recall === 0) return 0
  return (2 * precision * recall) / (precision + recall)
}

function isPositivePrediction(status: string): boolean {
  const positive = new Set([
    'under_verification', 'awaiting_confirmation', 'escalated_to_human',
    'human_review_pending', 'rejected', 'human_rejected', 'blocked',
  ])
  return positive.has(status)
}

function isNegativePrediction(status: string): boolean {
  const negative = new Set(['released', 'approved', 'human_approved'])
  return negative.has(status)
}

function riskBucketIndex(score: number): number {
  return Math.min(Math.floor(score * 10), 9)
}

function computeRiskBuckets(scores: number[]): number[] {
  const buckets = new Array<number>(10).fill(0)
  for (const score of scores) {
    buckets[riskBucketIndex(score)]++
  }
  return buckets
}

// ── calcRate ──────────────────────────────────────────────────────────────────

describe('calcRate', () => {
  it('returns null for total = 0', () => {
    expect(calcRate(0, 0)).toBeNull()
    expect(calcRate(5, 0)).toBeNull()
  })

  it('returns 0 when count is 0', () => {
    expect(calcRate(0, 10)).toBe(0)
  })

  it('returns 1.0 when count equals total', () => {
    expect(calcRate(5, 5)).toBe(1.0)
  })

  it('calculates partial rate correctly', () => {
    expect(calcRate(3, 10)).toBeCloseTo(0.3)
  })

  it('returns value in [0, 1]', () => {
    for (let i = 0; i <= 10; i++) {
      const r = calcRate(i, 10)
      if (r != null) {
        expect(r).toBeGreaterThanOrEqual(0)
        expect(r).toBeLessThanOrEqual(1)
      }
    }
  })
})

// ── pct ───────────────────────────────────────────────────────────────────────

describe('pct', () => {
  it('formats null as "Dados insuficientes"', () => {
    expect(pct(null)).toBe('Dados insuficientes')
  })

  it('formats 0 correctly', () => {
    expect(pct(0)).toBe('0.0%')
  })

  it('formats 1.0 correctly', () => {
    expect(pct(1.0)).toBe('100.0%')
  })

  it('formats 0.333 with 1 decimal', () => {
    expect(pct(1 / 3)).toBe('33.3%')
  })

  it('formats 0.5 correctly', () => {
    expect(pct(0.5)).toBe('50.0%')
  })
})

// ── calcF1 ────────────────────────────────────────────────────────────────────

describe('calcF1', () => {
  it('returns null when precision is null', () => {
    expect(calcF1(null, 0.8)).toBeNull()
  })

  it('returns null when recall is null', () => {
    expect(calcF1(0.9, null)).toBeNull()
  })

  it('returns 0 when both are 0', () => {
    expect(calcF1(0, 0)).toBe(0)
  })

  it('returns 1.0 when both are 1.0', () => {
    expect(calcF1(1.0, 1.0)).toBe(1.0)
  })

  it('calculates F1 for P=1, R=0.5', () => {
    const f1 = calcF1(1.0, 0.5)
    expect(f1).toBeCloseTo(2 / 3, 5)
  })

  it('calculates F1 for P=0.8, R=0.6', () => {
    const f1 = calcF1(0.8, 0.6)
    // 2 * 0.8 * 0.6 / (0.8 + 0.6) = 0.96 / 1.4 ≈ 0.6857
    expect(f1).toBeCloseTo(0.6857, 3)
  })

  it('F1 is symmetric — F1(P, R) === F1(R, P)', () => {
    const f1a = calcF1(0.7, 0.9)
    const f1b = calcF1(0.9, 0.7)
    expect(f1a).toBeCloseTo(f1b!, 10)
  })
})

// ── isPositivePrediction / isNegativePrediction ───────────────────────────────

describe('isPositivePrediction', () => {
  const positiveStatuses = [
    'under_verification', 'awaiting_confirmation', 'escalated_to_human',
    'human_review_pending', 'rejected', 'human_rejected', 'blocked',
  ]
  const negativeStatuses = ['released', 'approved', 'human_approved']

  it.each(positiveStatuses)('status %s is predicted positive', (status) => {
    expect(isPositivePrediction(status)).toBe(true)
  })

  it.each(negativeStatuses)('status %s is NOT predicted positive', (status) => {
    expect(isPositivePrediction(status)).toBe(false)
  })
})

describe('isNegativePrediction', () => {
  it('released is negative', () => {
    expect(isNegativePrediction('released')).toBe(true)
  })

  it('approved is negative', () => {
    expect(isNegativePrediction('approved')).toBe(true)
  })

  it('rejected is not negative', () => {
    expect(isNegativePrediction('rejected')).toBe(false)
  })

  it('pending is neither positive nor negative', () => {
    expect(isNegativePrediction('pending')).toBe(false)
    expect(isPositivePrediction('pending')).toBe(false)
  })
})

// ── riskBucketIndex ───────────────────────────────────────────────────────────

describe('riskBucketIndex', () => {
  it('maps 0.0 to bucket 0', () => {
    expect(riskBucketIndex(0.0)).toBe(0)
  })

  it('maps 0.09 to bucket 0', () => {
    expect(riskBucketIndex(0.09)).toBe(0)
  })

  it('maps 0.10 to bucket 1', () => {
    expect(riskBucketIndex(0.10)).toBe(1)
  })

  it('maps 0.5 to bucket 5', () => {
    expect(riskBucketIndex(0.5)).toBe(5)
  })

  it('maps 0.90 to bucket 9', () => {
    expect(riskBucketIndex(0.90)).toBe(9)
  })

  it('maps 1.0 to bucket 9 (clamp)', () => {
    expect(riskBucketIndex(1.0)).toBe(9)
  })
})

// ── computeRiskBuckets ────────────────────────────────────────────────────────

describe('computeRiskBuckets', () => {
  it('returns 10 buckets', () => {
    const b = computeRiskBuckets([])
    expect(b).toHaveLength(10)
  })

  it('all zeros for empty input', () => {
    const b = computeRiskBuckets([])
    expect(b.every(x => x === 0)).toBe(true)
  })

  it('sums to total count', () => {
    const scores = [0.05, 0.15, 0.55, 0.92, 0.33]
    const b = computeRiskBuckets(scores)
    expect(b.reduce((a, x) => a + x, 0)).toBe(5)
  })

  it('places scores in correct buckets', () => {
    const b = computeRiskBuckets([0.05, 0.99, 0.99])
    expect(b[0]).toBe(1)   // bucket 0-10%
    expect(b[9]).toBe(2)   // bucket 90-100%
  })
})

// ── Validação de tipos TypeScript ─────────────────────────────────────────────

describe('MetricsSummary type shape', () => {
  it('accepts a minimal valid MetricsSummary', () => {
    const summary: MetricsSummary = {
      generated_at: new Date().toISOString(),
      volume: { total_transactions: 3, total_analyses: 3, total_audit_logs: 3 },
      risk_distribution: {
        counts: { low: 1, medium: 1, high: 0, critical: 1 },
        percentages: { low: 33.3, medium: 33.3, high: 0.0, critical: 33.3 },
        total: 3,
      },
      rates: {
        confirmation_rate: 0.33,
        confirmation_count: 1,
        human_review_rate: 0.33,
        human_review_count: 1,
        insufficient_data: false,
      },
      timing: {
        avg_ms: 120.5,
        min_ms: 80.0,
        max_ms: 200.0,
        median_ms: 110.0,
        sample_size: 3,
        insufficient_data: false,
      },
      agent_timing: {
        fraud_agent: { avg_ms: 45.0, min_ms: 30.0, max_ms: 60.0, sample_size: 3, insufficient_data: false },
      },
      divergence: { divergence_count: 0, completed_analyses: 3, divergence_rate: 0.0 },
      audited_decisions: 6,
      component_failures: {},
      action_distribution: {
        counts: { approve: 1, request_confirmation: 1, escalate_to_human: 1, block: 0 },
        percentages: { approve: 33.3, request_confirmation: 33.3, escalate_to_human: 33.3, block: 0.0 },
        total: 3,
      },
      status_distribution: {
        counts: { released: 1, under_verification: 1, escalated_to_human: 1 },
        percentages: { released: 33.3, under_verification: 33.3, escalated_to_human: 33.3 },
      },
      classification: {
        available: true,
        labeled_count: 3,
        tp: 2,
        fp: 0,
        tn: 1,
        fn: 0,
        precision: 1.0,
        recall: 1.0,
        f1_score: 1.0,
        accuracy: 1.0,
        details: [],
        definition: {
          positive_class: 'Alto risco',
          disclaimer: 'Dados sintéticos — não representa desempenho no Banco do Brasil.',
        },
      },
      mode_breakdown: { AI_MODE: 0, RULES_MODE: 3, unknown: 0, total: 3 },
      risk_score_distribution: Array.from({ length: 10 }, (_, i) => ({
        range: `${i * 10}-${i * 10 + 10}%`,
        count: i === 0 ? 1 : i === 5 ? 1 : i === 9 ? 1 : 0,
        percentage: i === 0 || i === 5 || i === 9 ? 33.3 : 0,
      })),
    }

    expect(summary.volume.total_transactions).toBe(3)
    expect(summary.classification.available).toBe(true)
    expect(summary.classification.tp).toBe(2)
    expect(summary.mode_breakdown.RULES_MODE).toBe(3)
    expect(summary.risk_score_distribution).toHaveLength(10)
  })
})

describe('ClassificationMetrics type shape', () => {
  it('accepts available=false variant', () => {
    const clf: ClassificationMetrics = {
      available: false,
      reason: 'Sem dados rotulados.',
      labeled_count: 0,
      definition: {
        positive_class: 'Operação suspeita',
        disclaimer: 'Dados sintéticos.',
      },
    }
    expect(clf.available).toBe(false)
    expect(clf.labeled_count).toBe(0)
  })
})

describe('ModeBreakdown invariant', () => {
  it('AI_MODE + RULES_MODE + unknown must equal total', () => {
    const mb: ModeBreakdown = { AI_MODE: 2, RULES_MODE: 5, unknown: 1, total: 8 }
    expect(mb.AI_MODE + mb.RULES_MODE + mb.unknown).toBe(mb.total)
  })
})

describe('RiskScoreBucket', () => {
  it('10 buckets covering 0-100%', () => {
    const buckets: RiskScoreBucket[] = Array.from({ length: 10 }, (_, i) => ({
      range: `${i * 10}-${i * 10 + 10}%`,
      count: i,
      percentage: i * 10,
    }))
    expect(buckets[0].range).toBe('0-10%')
    expect(buckets[9].range).toBe('90-100%')
    expect(buckets.reduce((a, b) => a + b.count, 0)).toBe(45)
  })
})
