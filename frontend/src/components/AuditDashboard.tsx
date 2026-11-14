// Painel de auditoria — exibe logs e análises de risco em tempo real

import { useState, useEffect, useCallback } from 'react'
import { fetchAuditLogs, fetchRiskAnalyses, fetchTransactions } from '../services/api'
import type { AuditLog, RiskAnalysisResponse, TransactionResponse } from '../types'

const RISK_COLOR: Record<string, string> = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
}

const STATUS_COLOR: Record<string, string> = {
  released: '#22c55e',
  approved: '#22c55e',
  under_verification: '#f59e0b',
  requires_verification: '#f59e0b',
  escalated_to_human: '#f97316',
  rejected: '#ef4444',
  blocked: '#ef4444',
  pending: '#6b7280',
}

type Tab = 'transactions' | 'analyses' | 'audit'

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      background: color + '22',
      color,
      border: `1px solid ${color}44`,
      borderRadius: 4,
      padding: '1px 7px',
      fontSize: 11,
      fontWeight: 700,
      textTransform: 'uppercase',
    }}>
      {text}
    </span>
  )
}

function TransactionsTable({ data }: { data: TransactionResponse[] }) {
  if (!data.length) return <EmptyState message="Nenhuma transação encontrada." />
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        <thead>
          <tr style={{ background: '#f7f8fa' }}>
            {['ID externo', 'Cliente', 'Beneficiário', 'Valor', 'Risco', 'Status', 'Criada em'].map(h => (
              <th key={h} style={thStyle}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map(t => (
            <tr key={t.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={tdStyle}><code style={{ fontSize: 11 }}>{t.external_id.slice(0, 14)}…</code></td>
              <td style={tdStyle}>{t.client_name ?? t.client_id}</td>
              <td style={tdStyle}>{t.beneficiary_name ?? t.beneficiary_id}</td>
              <td style={tdStyle}><strong>R$ {Number(t.amount).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</strong></td>
              <td style={tdStyle}>
                <Badge text={t.risk_level} color={RISK_COLOR[t.risk_level] ?? '#6b7280'} />
                <span style={{ marginLeft: 4, fontSize: 11, color: '#57606a' }}>
                  {(t.risk_score * 100).toFixed(0)}%
                </span>
              </td>
              <td style={tdStyle}>
                <Badge text={t.status.replace(/_/g, ' ')} color={STATUS_COLOR[t.status] ?? '#6b7280'} />
              </td>
              <td style={tdStyle}><span style={{ fontSize: 11, color: '#57606a' }}>{new Date(t.created_at).toLocaleString('pt-BR')}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AnalysesTable({ data }: { data: RiskAnalysisResponse[] }) {
  if (!data.length) return <EmptyState message="Nenhuma análise encontrada." />
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        <thead>
          <tr style={{ background: '#f7f8fa' }}>
            {['Análise', 'Score', 'Nível', 'Ação', 'Status', 'Flags', 'Criada em'].map(h => (
              <th key={h} style={thStyle}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map(a => {
            let flags: string[] = []
            try { flags = JSON.parse(a.flags ?? '[]') } catch { /* ok */ }
            return (
              <tr key={a.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={tdStyle}><code style={{ fontSize: 11 }}>{a.external_id.slice(0, 14)}…</code></td>
                <td style={tdStyle}>
                  <strong style={{ color: RISK_COLOR[a.risk_level] ?? '#374151' }}>
                    {(a.overall_risk_score * 100).toFixed(1)}%
                  </strong>
                </td>
                <td style={tdStyle}>
                  <Badge text={a.risk_level} color={RISK_COLOR[a.risk_level] ?? '#6b7280'} />
                </td>
                <td style={tdStyle}>
                  <span style={{ fontSize: 12 }}>{a.recommended_action.replace(/_/g, ' ')}</span>
                </td>
                <td style={tdStyle}>
                  <Badge text={a.status} color={a.status === 'completed' ? '#22c55e' : '#6b7280'} />
                </td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                    {flags.slice(0, 3).map(f => (
                      <span key={f} style={{
                        background: '#fee2e2', color: '#b91c1c',
                        borderRadius: 3, padding: '0 5px', fontSize: 10,
                      }}>{f}</span>
                    ))}
                    {flags.length > 3 && <span style={{ fontSize: 10, color: '#57606a' }}>+{flags.length - 3}</span>}
                  </div>
                </td>
                <td style={tdStyle}><span style={{ fontSize: 11, color: '#57606a' }}>{new Date(a.created_at).toLocaleString('pt-BR')}</span></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function AuditTable({ data }: { data: AuditLog[] }) {
  if (!data.length) return <EmptyState message="Nenhum log de auditoria encontrado." />
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        <thead>
          <tr style={{ background: '#f7f8fa' }}>
            {['#', 'Componente', 'Agente', 'Evento', 'Resultado', 'Score', 'Timestamp'].map(h => (
              <th key={h} style={thStyle}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map(log => (
            <tr key={log.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={tdStyle}><span style={{ fontSize: 11, color: '#57606a' }}>{log.id}</span></td>
              <td style={tdStyle}><code style={{ fontSize: 11 }}>{log.component}</code></td>
              <td style={tdStyle}><span style={{ fontSize: 12 }}>{log.agent_name}</span></td>
              <td style={tdStyle}><code style={{ fontSize: 11, color: '#3b82d4' }}>{log.event ?? log.action}</code></td>
              <td style={tdStyle}>
                {log.result && (
                  <Badge
                    text={log.result.replace(/_/g, ' ')}
                    color={STATUS_COLOR[log.result] ?? '#6b7280'}
                  />
                )}
              </td>
              <td style={tdStyle}>
                {log.risk_score != null && (
                  <strong style={{ color: RISK_COLOR[log.risk_score < 0.3 ? 'low' : log.risk_score < 0.6 ? 'medium' : log.risk_score < 0.85 ? 'high' : 'critical'] }}>
                    {(log.risk_score * 100).toFixed(1)}%
                  </strong>
                )}
              </td>
              <td style={tdStyle}><span style={{ fontSize: 11, color: '#57606a' }}>{new Date(log.created_at).toLocaleString('pt-BR')}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: '#9ca3af', fontSize: 14 }}>
      {message}
    </div>
  )
}

export function AuditDashboard({ refreshKey }: { refreshKey: number }) {
  const [tab, setTab] = useState<Tab>('transactions')
  const [transactions, setTransactions] = useState<TransactionResponse[]>([])
  const [analyses, setAnalyses] = useState<RiskAnalysisResponse[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [txns, anls, logs] = await Promise.all([
        fetchTransactions(),
        fetchRiskAnalyses(),
        fetchAuditLogs(),
      ])
      setTransactions(txns)
      setAnalyses(anls)
      setAuditLogs(logs)
    } catch {
      // silencioso — erro tratado no console
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh, refreshKey])

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: 'transactions', label: '💳 Transações', count: transactions.length },
    { id: 'analyses', label: '🤖 Análises', count: analyses.length },
    { id: 'audit', label: '📋 Auditoria', count: auditLogs.length },
  ]

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                background: tab === t.id ? '#3b82d4' : '#f7f8fa',
                color: tab === t.id ? '#fff' : '#374151',
                border: '1px solid',
                borderColor: tab === t.id ? '#3b82d4' : '#e5e7eb',
                borderRadius: 6,
                padding: '6px 14px',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {t.label}
              <span style={{
                marginLeft: 6,
                background: tab === t.id ? 'rgba(255,255,255,0.3)' : '#e5e7eb',
                borderRadius: 10,
                padding: '0 6px',
                fontSize: 11,
              }}>
                {t.count}
              </span>
            </button>
          ))}
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          style={{
            background: 'transparent',
            border: '1px solid #e5e7eb',
            borderRadius: 6,
            padding: '6px 12px',
            fontSize: 12,
            cursor: 'pointer',
            color: '#57606a',
          }}
        >
          {loading ? '⏳' : '🔄'} Atualizar
        </button>
      </div>

      {tab === 'transactions' && <TransactionsTable data={transactions} />}
      {tab === 'analyses' && <AnalysesTable data={analyses} />}
      {tab === 'audit' && <AuditTable data={auditLogs} />}
    </div>
  )
}

// ── Estilos de tabela ─────────────────────────────────────────────────────────

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 13,
}

const thStyle: React.CSSProperties = {
  padding: '8px 12px',
  textAlign: 'left',
  fontSize: 11,
  fontWeight: 700,
  color: '#57606a',
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  borderBottom: '2px solid #e5e7eb',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '8px 12px',
  verticalAlign: 'middle',
}
