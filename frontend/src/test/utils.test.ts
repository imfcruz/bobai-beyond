/**
 * Testes das funções utilitárias de tipos e lógica do frontend.
 *
 * Cobrem:
 * - Verificação dos tipos TypeScript em runtime
 * - Parsing de AgentResult (JSON → objeto)
 * - Parsing de flags (JSON string → string[])
 * - Lógica de cores por nível de risco
 * - Mapeamentos de status e ação para labels
 */

import { describe, it, expect } from 'vitest'
import type {
  RiskLevel,
  TransactionStatus,
  RecommendedAction,
  GatewayResponse,
  TransferInitiatedResponse,
  AgentResultParsed,
} from '../types'

// ── Helpers extraídos de TransferSimulator.tsx ────────────────────────────────

function parseAgentResult(raw: string | null): AgentResultParsed | null {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function parseFlags(raw: string | null): string[] {
  if (!raw) return []
  try {
    return JSON.parse(raw)
  } catch {
    return []
  }
}

const RISK_COLOR: Record<string, string> = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
}

const STATUS_LABEL: Record<string, string> = {
  released: '✅ Liberada',
  under_verification: '⚠️ Em verificação',
  escalated_to_human: '🔴 Escalada para humano',
  rejected: '❌ Rejeitada',
  pending: '⏳ Pendente',
}

const ACTION_LABEL: Record<string, string> = {
  approve: 'Aprovar',
  request_confirmation: 'Solicitar confirmação',
  escalate_to_human: 'Escalar para humano',
  block: 'Bloquear',
}

// ── parseAgentResult ──────────────────────────────────────────────────────────

describe('parseAgentResult', () => {
  it('returns null for null input', () => {
    expect(parseAgentResult(null)).toBeNull()
  })

  it('returns null for empty string', () => {
    expect(parseAgentResult('')).toBeNull()
  })

  it('returns null for invalid JSON', () => {
    expect(parseAgentResult('not-json')).toBeNull()
  })

  it('parses a valid AgentResult JSON', () => {
    const raw = JSON.stringify({
      agent_name: 'fraud_agent',
      risk_score: 0.75,
      flags: ['new_beneficiary', 'social_engineering_keyword'],
      reasoning: 'Risco alto detectado.',
      confidence: 0.85,
    })
    const result = parseAgentResult(raw)
    expect(result).not.toBeNull()
    expect(result!.agent_name).toBe('fraud_agent')
    expect(result!.risk_score).toBe(0.75)
    expect(result!.flags).toHaveLength(2)
    expect(result!.flags).toContain('social_engineering_keyword')
    expect(result!.reasoning).toBe('Risco alto detectado.')
    expect(result!.confidence).toBe(0.85)
  })

  it('parses low-risk AgentResult', () => {
    const raw = JSON.stringify({
      agent_name: 'behavioral_agent',
      risk_score: 0.05,
      flags: [],
      reasoning: 'Dentro do padrão histórico.',
      confidence: 0.9,
    })
    const result = parseAgentResult(raw)
    expect(result!.risk_score).toBe(0.05)
    expect(result!.flags).toHaveLength(0)
  })
})

// ── parseFlags ────────────────────────────────────────────────────────────────

describe('parseFlags', () => {
  it('returns empty array for null', () => {
    expect(parseFlags(null)).toEqual([])
  })

  it('returns empty array for empty string', () => {
    expect(parseFlags('')).toEqual([])
  })

  it('returns empty array for invalid JSON', () => {
    expect(parseFlags('not-json')).toEqual([])
  })

  it('parses a valid flags JSON array', () => {
    const raw = JSON.stringify(['new_beneficiary', 'limit_changed_before_transfer'])
    const flags = parseFlags(raw)
    expect(flags).toHaveLength(2)
    expect(flags).toContain('new_beneficiary')
    expect(flags).toContain('limit_changed_before_transfer')
  })

  it('returns empty array for empty JSON array', () => {
    expect(parseFlags('[]')).toEqual([])
  })
})

// ── RISK_COLOR mapping ────────────────────────────────────────────────────────

describe('RISK_COLOR', () => {
  it('maps low to green', () => {
    expect(RISK_COLOR['low']).toBe('#22c55e')
  })

  it('maps medium to yellow/amber', () => {
    expect(RISK_COLOR['medium']).toBe('#f59e0b')
  })

  it('maps high to orange', () => {
    expect(RISK_COLOR['high']).toBe('#f97316')
  })

  it('maps critical to red', () => {
    expect(RISK_COLOR['critical']).toBe('#ef4444')
  })

  it('has exactly 4 risk levels', () => {
    expect(Object.keys(RISK_COLOR)).toHaveLength(4)
  })
})

// ── STATUS_LABEL mapping ──────────────────────────────────────────────────────

describe('STATUS_LABEL', () => {
  it('maps released to approved label', () => {
    expect(STATUS_LABEL['released']).toContain('Liberada')
  })

  it('maps under_verification to verification label', () => {
    expect(STATUS_LABEL['under_verification']).toContain('verificação')
  })

  it('maps escalated_to_human to human label', () => {
    expect(STATUS_LABEL['escalated_to_human']).toContain('humano')
  })

  it('maps rejected to rejected label', () => {
    expect(STATUS_LABEL['rejected']).toContain('Rejeitada')
  })
})

// ── ACTION_LABEL mapping ──────────────────────────────────────────────────────

describe('ACTION_LABEL', () => {
  it('maps approve action', () => {
    expect(ACTION_LABEL['approve']).toBe('Aprovar')
  })

  it('maps request_confirmation action', () => {
    expect(ACTION_LABEL['request_confirmation']).toContain('confirmação')
  })

  it('maps escalate_to_human action', () => {
    expect(ACTION_LABEL['escalate_to_human']).toContain('humano')
  })

  it('maps block action', () => {
    expect(ACTION_LABEL['block']).toBe('Bloquear')
  })
})

// ── Type shape validation ─────────────────────────────────────────────────────

describe('GatewayResponse type shape', () => {
  it('accepts a valid GatewayResponse object', () => {
    const gw: GatewayResponse = {
      authorized: true,
      final_status: 'released' as TransactionStatus,
      final_action: 'approve' as RecommendedAction,
      risk_level: 'low' as RiskLevel,
      risk_score: 0.08,
      requires_confirmation: false,
      requires_human_review: false,
      gateway_reasoning: 'Aprovado pelo Security Gateway.',
      flags: [],
      policy_version: 'v1.0.0',
      divergence_detected: false,
      unauthorized_action_attempted: false,
    }
    expect(gw.authorized).toBe(true)
    expect(gw.risk_level).toBe('low')
    expect(gw.risk_score).toBeLessThan(0.3)
  })

  it('accepts a high-risk blocked GatewayResponse', () => {
    const gw: GatewayResponse = {
      authorized: false,
      final_status: 'rejected' as TransactionStatus,
      final_action: 'block' as RecommendedAction,
      risk_level: 'critical' as RiskLevel,
      risk_score: 0.97,
      requires_confirmation: false,
      requires_human_review: false,
      gateway_reasoning: 'BLOQUEADO — engenharia social detectada.',
      flags: ['social_engineering_keyword', 'full_social_engineering_sequence'],
      policy_version: 'v1.0.0',
      divergence_detected: false,
      unauthorized_action_attempted: false,
    }
    expect(gw.authorized).toBe(false)
    expect(gw.flags).toHaveLength(2)
  })
})

// ── TransferInitiatedResponse shape ──────────────────────────────────────────

describe('TransferInitiatedResponse shape', () => {
  it('accepts a minimal response with null gateway', () => {
    const response: TransferInitiatedResponse = {
      transaction: {
        id: 1,
        external_id: 'txn-test-001',
        client_id: 1,
        beneficiary_id: 1,
        amount: '1500.00',
        currency: 'BRL',
        purpose: 'Pagamento',
        is_new_recipient: false,
        recent_limit_change: false,
        device_recognized: true,
        risk_level: 'low',
        risk_score: 0.05,
        status: 'released',
        decision_reasoning: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      analysis: {
        id: 1,
        external_id: 'analysis-001',
        transaction_id: 1,
        overall_risk_score: 0.05,
        risk_level: 'low',
        recommended_action: 'approve',
        reasoning: 'Baixo risco.',
        flags: '[]',
        status: 'completed',
        orchestrator_result: null,
        fraud_agent_result: null,
        inconsistency_agent_result: null,
        behavioral_agent_result: null,
        risk_agent_result: null,
        divergence_detected: false,
        divergence_details: null,
        policy_version: null,
        confirmation_purpose: null,
        phase: 'phase_1',
        started_at: null,
        completed_at: null,
        created_at: new Date().toISOString(),
      },
      gateway: null,
      message: '✅ Transferência liberada automaticamente.',
      idempotent: false,
      pipeline_failed: false,
      failure_reason: null,
    }
    expect(response.message).toContain('liberada')
    expect(response.gateway).toBeNull()
    expect(response.transaction.risk_score).toBe(0.05)
  })
})

// ── Risk score bar color logic ────────────────────────────────────────────────

describe('risk score to color mapping', () => {
  function scoreToColor(score: number): string {
    return score < 0.3
      ? '#22c55e'
      : score < 0.6
        ? '#f59e0b'
        : score < 0.85
          ? '#f97316'
          : '#ef4444'
  }

  it('returns green for score 0.05', () => {
    expect(scoreToColor(0.05)).toBe('#22c55e')
  })

  it('returns green for score 0.29', () => {
    expect(scoreToColor(0.29)).toBe('#22c55e')
  })

  it('returns amber for score 0.30', () => {
    expect(scoreToColor(0.30)).toBe('#f59e0b')
  })

  it('returns amber for score 0.59', () => {
    expect(scoreToColor(0.59)).toBe('#f59e0b')
  })

  it('returns orange for score 0.60', () => {
    expect(scoreToColor(0.60)).toBe('#f97316')
  })

  it('returns orange for score 0.84', () => {
    expect(scoreToColor(0.84)).toBe('#f97316')
  })

  it('returns red for score 0.85', () => {
    expect(scoreToColor(0.85)).toBe('#ef4444')
  })

  it('returns red for score 1.0', () => {
    expect(scoreToColor(1.0)).toBe('#ef4444')
  })
})
