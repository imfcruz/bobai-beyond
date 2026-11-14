// Tela 7 — Painel de Auditoria
// Histórico técnico completo: agentes, evidências, divergências, política, tempo.

import { useState, useEffect, useCallback } from 'react'
import { fetchAuditLogs, fetchRiskAnalyses, fetchTransactions } from '../services/api'
import type { AuditLog, RiskAnalysisResponse, TransactionResponse, AgentResultParsed } from '../types'
import {
  Card, CardHeader, Btn, Badge, StatusBadge, RiskBadge, Spinner,
  clr, fmtBRL, fmtDate, tableStyle, thStyle, tdStyle,
  STATUS_COLOR, parseJSON, riskColor, actionLabel, agentLabel, statusLabel, employeeExplanation,
} from './ui'

type Tab = 'transactions' | 'analyses' | 'audit'

function componentLabel(value: string): string {
  const labels: Record<string, string> = {
    orchestrator: 'Coordenação', decision_engine: 'Motor de decisão', security_gateway: 'Controle de segurança',
    bank_service: 'Serviço bancário', settlement_service: 'Processamento financeiro', card_service: 'Gestão de cartões',
  }
  return labels[value] ?? 'Sistema de análise'
}

function eventLabel(event: string | null, action: string): string {
  const value = event || action
  const labels: Record<string, string> = {
    analysis_started: 'Análise iniciada', analysis_completed: 'Análise concluída', decision_applied: 'Decisão aplicada',
    transaction_created: 'Transferência criada', transaction_released: 'Transferência liberada',
    human_review: 'Revisão humana registrada', confirmation_requested: 'Confirmação solicitada',
    limit_request_created: 'Pedido de limite criado', limit_request_reviewed: 'Pedido de limite revisado',
  }
  return labels[value] ?? actionLabel(value)
}

// ── Agentes expandidos ────────────────────────────────────────────────────────

function AgentDetail({ raw, label }: { raw: string | null; label: string }) {
  const [open, setOpen] = useState(false)
  const result = parseJSON<AgentResultParsed>(raw)
  if (!result) return <span style={{ color: clr.textLight, fontSize: 11 }}>—</span>

  const pct = Math.round(result.risk_score * 100)
  const color = riskColor(result.risk_score)

  return (
    <div style={{ marginBottom: 4 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
          padding: 0, fontFamily: 'inherit',
        }}
      >
        <span style={{ fontWeight: 600, color, fontSize: 12 }}>{pct}%</span>
        <span style={{ fontSize: 11, color: clr.textMuted }}>{label}</span>
        <span style={{ fontSize: 10, color: clr.textLight }}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div style={{
          marginTop: 6, padding: '8px 10px',
          background: clr.surfaceAlt, border: `1px solid ${clr.border}`,
          borderRadius: 6, fontSize: 11,
        }}>
          <div style={{ color: '#374151', lineHeight: 1.5, marginBottom: 4 }}>
            {employeeExplanation(result.explanation || result.reasoning)}
          </div>
          {result.evidence?.slice(0, 2).map((e, i) => (
            <div key={i} style={{ color: clr.textMuted, fontSize: 10, lineHeight: 1.4 }}>• {e}</div>
          ))}
          <div style={{ marginTop: 6, display: 'flex', gap: 10, color: clr.textLight }}>
            {result.execution_time_ms != null && <span>{result.execution_time_ms}ms</span>}
            <span>Confiança: {Math.round(result.confidence * 100)}%</span>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Análise expandida ─────────────────────────────────────────────────────────

function AnalysisRow({ a }: { a: RiskAnalysisResponse }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <tr style={{ cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
        <td style={tdStyle}><code style={{ fontSize: 10 }}>{a.external_id.slice(0, 12)}…</code></td>
        <td style={tdStyle}>
          <strong style={{ color: riskColor(a.overall_risk_score) }}>
            {(a.overall_risk_score * 100).toFixed(1)}%
          </strong>
        </td>
        <td style={tdStyle}><RiskBadge level={a.risk_level} /></td>
        <td style={tdStyle}><span style={{ fontSize: 12 }}>{actionLabel(a.recommended_action)}</span></td>
        <td style={tdStyle}>
          <Badge
            text={statusLabel(a.status)}
            color={a.status === 'completed' ? '#16a34a' : a.status === 'failed' ? '#dc2626' : '#6b7280'}
          />
        </td>
        <td style={tdStyle}>
          {a.divergence_detected
            ? <span style={{ color: '#ea580c', fontWeight: 700, fontSize: 11 }}>Sim</span>
            : <span style={{ color: '#16a34a', fontSize: 11 }}>Não</span>
          }
        </td>
        <td style={tdStyle}><code style={{ fontSize: 10 }}>{a.policy_version ?? '—'}</code></td>
        <td style={tdStyle}>
          {a.started_at && a.completed_at
            ? <span style={{ fontSize: 11 }}>{new Date(a.completed_at).getTime() - new Date(a.started_at).getTime()}ms</span>
            : '—'}
        </td>
        <td style={tdStyle}><span style={{ fontSize: 10, color: clr.textLight }}>{open ? '▲' : '▼'}</span></td>
      </tr>
      {open && (
        <tr>
          <td colSpan={9} style={{ padding: '0 12px 12px', background: clr.surfaceAlt }}>
            <div style={{ padding: '12px', border: `1px solid ${clr.border}`, borderRadius: 8, background: '#fff' }}>
              {/* Agentes */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 12 }}>
                <AgentDetail raw={a.fraud_agent_result} label="Fraude" />
                <AgentDetail raw={a.inconsistency_agent_result} label="Inconsistência" />
                <AgentDetail raw={a.behavioral_agent_result} label="Comportamental" />
                <AgentDetail raw={a.risk_agent_result} label="Risco" />
              </div>

              {/* Divergência */}
              {a.divergence_detected && a.divergence_details && (() => {
                const d = parseJSON<{ spread: number; high_risk_agents: string[]; low_risk_agents: string[]; note: string }>(a.divergence_details)
                if (!d) return null
                return (
                  <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 6, padding: '8px 10px', marginBottom: 10, fontSize: 12, color: '#9a3412' }}>
                    <strong>Divergência detectada</strong> — spread: {(d.spread * 100).toFixed(0)}%
                    {d.high_risk_agents.length > 0 && ` | Maior atenção: ${d.high_risk_agents.map(agentLabel).join(', ')}`}
                    {d.low_risk_agents.length > 0 && ` | Menor atenção: ${d.low_risk_agents.map(agentLabel).join(', ')}`}
                  </div>
                )
              })()}

              {/* Raciocínio */}
              {a.reasoning && (
                <div style={{ fontSize: 12, color: '#374151', lineHeight: 1.6 }}>{employeeExplanation(a.reasoning)}</div>
              )}

              {/* Confirmação */}
              {a.confirmation_purpose && (
                <div style={{ marginTop: 10, fontSize: 12 }}>
                  <span style={{ fontWeight: 700, color: clr.textMuted }}>Finalidade fornecida (Fase 2): </span>
                  <em>"{a.confirmation_purpose}"</em>
                  <span style={{ marginLeft: 8, fontSize: 11, color: clr.textLight }}>fase: {a.phase}</span>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Componentes de tabela ─────────────────────────────────────────────────────

function TransactionsTab({ data }: { data: TransactionResponse[] }) {
  if (!data.length) return <Empty msg="Nenhuma transação." />
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        <thead>
          <tr>{['ID', 'Cliente', 'Beneficiário', 'Valor', 'Risco', 'Score', 'Status', 'Criada em'].map(h => (
            <th key={h} style={thStyle}>{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {data.map(t => (
            <tr key={t.id}>
              <td style={tdStyle}><code style={{ fontSize: 10 }}>{t.external_id.slice(0, 12)}…</code></td>
              <td style={tdStyle}>{t.client_name ?? `#${t.client_id}`}</td>
              <td style={tdStyle}>{t.beneficiary_name ?? `#${t.beneficiary_id}`}</td>
              <td style={tdStyle}><strong>{fmtBRL(t.amount)}</strong></td>
              <td style={tdStyle}><RiskBadge level={t.risk_level} /></td>
              <td style={tdStyle}><span style={{ color: riskColor(t.risk_score), fontWeight: 700, fontSize: 12 }}>{(t.risk_score * 100).toFixed(0)}%</span></td>
              <td style={tdStyle}><StatusBadge status={t.status} /></td>
              <td style={tdStyle}><span style={{ fontSize: 11, color: clr.textMuted }}>{fmtDate(t.created_at)}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AnalysesTab({ data }: { data: RiskAnalysisResponse[] }) {
  if (!data.length) return <Empty msg="Nenhuma análise." />
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        <thead>
          <tr>{['ID', 'Score', 'Nível', 'Ação', 'Status', 'Divergência', 'Política', 'Tempo', ''].map(h => (
            <th key={h} style={thStyle}>{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {data.map(a => <AnalysisRow key={a.id} a={a} />)}
        </tbody>
      </table>
    </div>
  )
}

function AuditTab({ data }: { data: AuditLog[] }) {
  if (!data.length) return <Empty msg="Nenhum log de auditoria." />
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        <thead>
          <tr>{['#', 'Componente', 'Agente', 'Evento', 'Resultado', 'Score', 'Política', 'Tempo', 'Timestamp'].map(h => (
            <th key={h} style={thStyle}>{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {data.map(log => (
            <tr key={log.id}>
              <td style={tdStyle}><span style={{ fontSize: 10, color: clr.textMuted }}>{log.id}</span></td>
              <td style={tdStyle}><span style={{ fontSize: 11 }}>{componentLabel(log.component)}</span></td>
              <td style={tdStyle}><span style={{ fontSize: 11 }}>{agentLabel(log.agent_name)}</span></td>
              <td style={tdStyle}><span style={{ fontSize: 11, color: '#2563eb' }}>{eventLabel(log.event, log.action)}</span></td>
              <td style={tdStyle}>
                {log.result && (
                  <Badge text={statusLabel(log.result)} color={STATUS_COLOR[log.result] ?? '#6b7280'} small />
                )}
              </td>
              <td style={tdStyle}>
                {log.risk_score != null
                  ? <strong style={{ color: riskColor(log.risk_score), fontSize: 12 }}>{(log.risk_score * 100).toFixed(0)}%</strong>
                  : '—'}
              </td>
              <td style={tdStyle}><code style={{ fontSize: 10 }}>{log.policy_version ?? '—'}</code></td>
              <td style={tdStyle}>
                {log.execution_time_ms != null
                  ? <span style={{ fontSize: 11 }}>{log.execution_time_ms}ms</span>
                  : '—'}
              </td>
              <td style={tdStyle}><span style={{ fontSize: 10, color: clr.textMuted }}>{fmtDate(log.created_at)}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Empty({ msg }: { msg: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: clr.textLight, fontSize: 14 }}>
      {msg}
    </div>
  )
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function AuditPage() {
  const [tab, setTab] = useState<Tab>('analyses')
  const [transactions, setTransactions] = useState<TransactionResponse[]>([])
  const [analyses, setAnalyses] = useState<RiskAnalysisResponse[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [txns, anls, logs] = await Promise.all([
        fetchTransactions(100),
        fetchRiskAnalyses(100),
        fetchAuditLogs(200),
      ])
      setTransactions(txns)
      setAnalyses(anls)
      setAuditLogs(logs)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const tabs = [
    { id: 'analyses' as Tab, label: 'Análises', count: analyses.length },
    { id: 'transactions' as Tab, label: 'Transações', count: transactions.length },
    { id: 'audit' as Tab, label: 'Logs', count: auditLogs.length },
  ]

  return (
    <Card>
      <CardHeader title="Painel de Auditoria" subtitle="Rastreabilidade completa de análises, decisões e políticas aplicadas" />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                background: tab === t.id ? '#2563eb' : clr.surfaceAlt,
                color: tab === t.id ? '#fff' : clr.text,
                border: `1px solid ${tab === t.id ? '#2563eb' : clr.border}`,
                borderRadius: 6, padding: '6px 14px',
                fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              {t.label}
              <span style={{
                marginLeft: 6,
                background: tab === t.id ? 'rgba(255,255,255,0.25)' : clr.border,
                borderRadius: 10, padding: '0 6px', fontSize: 11,
              }}>
                {t.count}
              </span>
            </button>
          ))}
        </div>
        <Btn variant="ghost" small onClick={refresh} disabled={loading}>
          {loading ? <Spinner size={12} /> : '↻'} Atualizar
        </Btn>
      </div>

      {loading && analyses.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, display: 'flex', justifyContent: 'center' }}>
          <Spinner size={24} />
        </div>
      )}

      {tab === 'transactions' && <TransactionsTab data={transactions} />}
      {tab === 'analyses' && <AnalysesTab data={analyses} />}
      {tab === 'audit' && <AuditTab data={auditLogs} />}
    </Card>
  )
}
