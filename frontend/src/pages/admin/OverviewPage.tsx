// ─── Nexus Bank — Admin Overview Page ────────────────────────────────────
// KPIs, risk distribution, pending items, quick links to admin modules.

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchTransactions, fetchRiskAnalyses, resetDemo } from '../../services/api'
import type { TransactionResponse, RiskAnalysisResponse } from '../../types'
import {
  t, Card, CardHeader, Btn, Spinner, RiskBadge, StatusBadge,
  fmtBRL, fmtDate, RISK_COLOR, STATUS_COLOR,
  RISK_LABEL, STATUS_LABEL,
} from '../../components/ui'
import NavIcon, { type NavIconName } from '../../components/NavIcon'

function KpiCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <Card style={{ padding: '18px 20px' }}>
      <div style={{ fontSize: 11, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: color ?? t.text, lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: t.textLight, marginTop: 4 }}>{sub}</div>}
    </Card>
  )
}

function RiskDistributionBar({ analyses }: { analyses: RiskAnalysisResponse[] }) {
  if (!analyses.length) return null
  const counts = { low: 0, medium: 0, high: 0, critical: 0 }
  analyses.forEach(a => { counts[a.risk_level as keyof typeof counts] = (counts[a.risk_level as keyof typeof counts] ?? 0) + 1 })
  const total = analyses.length

  return (
    <Card style={{ padding: '18px 20px' }}>
      <div style={{ fontSize: 11, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 }}>
        Distribuição de risco
      </div>
      <div style={{ display: 'flex', gap: 2, height: 16, borderRadius: 8, overflow: 'hidden', marginBottom: 10 }}>
        {Object.entries(counts).map(([level, count]) => {
          if (!count) return null
          return (
            <div
              key={level}
              style={{ flex: count, background: RISK_COLOR[level] ?? '#ccc', transition: 'flex 0.3s' }}
              title={`${level}: ${count}`}
            />
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {Object.entries(counts).map(([level, count]) => (
          <div key={level} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: RISK_COLOR[level] ?? '#ccc', flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: t.textMuted }}>
              {RISK_LABEL[level] ?? 'Não classificado'}: <strong style={{ color: t.text }}>{count}</strong>
              {' '}({total ? ((count / total) * 100).toFixed(0) : 0}%)
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}

function StatusDistributionBar({ transactions }: { transactions: TransactionResponse[] }) {
  if (!transactions.length) return null
  const counts: Record<string, number> = {}
  transactions.forEach(t => { counts[t.status] = (counts[t.status] ?? 0) + 1 })

  return (
    <Card style={{ padding: '18px 20px' }}>
      <div style={{ fontSize: 11, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 }}>
        Status das transações
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {Object.entries(counts).slice(0, 6).map(([status, count]) => (
          <div key={status} className="status-chart-row" style={{ display: 'grid', gridTemplateColumns: 'minmax(150px, 1.1fr) minmax(100px, 3fr) 28px', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 11, color: STATUS_COLOR[status] ?? t.textMuted, fontWeight: 750, whiteSpace: 'normal', lineHeight: 1.2 }}>{STATUS_LABEL[status] ?? 'Registrada'}</span>
            <div style={{
              height: 8, borderRadius: 4, overflow: 'hidden',
              background: t.surface2, border: `1px solid ${t.border}`,
            }}>
              <div style={{
                height: '100%', borderRadius: 4,
                background: STATUS_COLOR[status] ?? '#9ca3af',
                width: `${(count / transactions.length) * 100}%`,
              }} />
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, color: t.text, width: 30, textAlign: 'right' }}>
              {count}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}

export default function AdminOverviewPage() {
  const navigate = useNavigate()
  const [transactions, setTransactions] = useState<TransactionResponse[]>([])
  const [analyses, setAnalyses] = useState<RiskAnalysisResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [txns, anls] = await Promise.all([
        fetchTransactions(200).catch(() => [] as TransactionResponse[]),
        fetchRiskAnalyses(200).catch(() => [] as RiskAnalysisResponse[]),
      ])
      setTransactions(txns)
      setAnalyses(anls)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const pendingReview = transactions.filter(t => ['human_review_pending', 'escalated_to_human'].includes(t.status))
  const awaitingConf = transactions.filter(t => ['awaiting_confirmation', 'under_verification'].includes(t.status))
  const divergences = analyses.filter(a => a.divergence_detected)
  const avgScore = analyses.length ? (analyses.reduce((s, a) => s + a.overall_risk_score, 0) / analyses.length * 100).toFixed(1) : '—'

  async function handleReset() {
    setResetting(true)
    try {
      await resetDemo()
      setResetMsg('Dados reiniciados com sucesso.')
      await load()
    } catch {
      setResetMsg('Erro ao reiniciar dados.')
    } finally {
      setResetting(false)
      setTimeout(() => setResetMsg(null), 4000)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Page title */}
      <div className="admin-page-toolbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: t.text, margin: 0 }}>Visão geral</h1>
          <p style={{ fontSize: 13, color: t.textMuted, margin: '4px 0 0' }}>
            Métricas em tempo real · IBM AI Experiential Learning Lab
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {resetMsg && (
            <span style={{ fontSize: 12, color: resetMsg.includes('Erro') ? t.danger : t.success }}>
              {resetMsg}
            </span>
          )}
          <Btn variant="ghost" small onClick={load} disabled={loading}>
            {loading ? <Spinner size={12} /> : '↻'} Atualizar
          </Btn>
          <Btn variant="secondary" small onClick={handleReset} disabled={resetting}>
            {resetting ? <Spinner size={12} /> : '↺'} Reset demo
          </Btn>
        </div>
      </div>

      {/* KPIs */}
      <div className="admin-kpi-grid">
        <KpiCard label="Total de análises" value={analyses.length} sub="Executadas até agora" />
        <KpiCard label="Revisão humana" value={pendingReview.length} sub="Aguardando ação" color={pendingReview.length > 0 ? t.orange : undefined} />
        <KpiCard label="Aguardando conf." value={awaitingConf.length} sub="Fase 2 pendente" color={awaitingConf.length > 0 ? '#d97706' : undefined} />
        <KpiCard label="Score médio" value={`${avgScore}%`} sub="Risco médio das análises" color={parseFloat(avgScore) > 50 ? t.danger : undefined} />
      </div>

      {/* Charts */}
      <div className="admin-chart-grid">
        <RiskDistributionBar analyses={analyses} />
        <StatusDistributionBar transactions={transactions} />
      </div>

      {/* Divergences */}
      {divergences.length > 0 && (
        <Card>
          <CardHeader
            title={`Divergências detectadas (${divergences.length})`}
            subtitle="Análises onde os agentes apresentaram avaliações significativamente diferentes"
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {divergences.slice(0, 5).map(a => (
              <div key={a.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 12px',
                background: t.orangeBg, border: `1px solid ${t.orangeBorder}`,
                borderRadius: 8,
              }}>
                <div>
                  <code style={{ fontSize: 11 }}>{a.external_id.slice(0, 14)}…</code>
                  <span style={{ marginLeft: 8, fontSize: 12, color: t.textMuted }}>
                    Score: {(a.overall_risk_score * 100).toFixed(0)}%
                  </span>
                </div>
                <RiskBadge level={a.risk_level} />
              </div>
            ))}
          </div>
          {divergences.length > 5 && (
            <div style={{ marginTop: 8, textAlign: 'center' }}>
              <Btn variant="ghost" small onClick={() => navigate('/admin/audit')}>
                Ver todas no painel de auditoria
              </Btn>
            </div>
          )}
        </Card>
      )}

      {/* Recent transactions */}
      <Card>
        <CardHeader
          title="Transações recentes"
          subtitle="Últimas operações processadas"
          action={
            <Btn variant="ghost" small onClick={() => navigate('/admin/audit')}>
              Ver todas →
            </Btn>
          }
        />

        {loading && !transactions.length && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
            <Spinner size={24} />
          </div>
        )}

        {!loading && !transactions.length && (
          <div style={{ textAlign: 'center', padding: '32px 0', color: t.textLight, fontSize: 13 }}>
            Nenhuma transação. Execute um cenário para começar.
          </div>
        )}

        {transactions.slice(0, 8).map((txn, i) => (
          <div key={txn.id} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 4px',
            borderBottom: i < Math.min(7, transactions.length - 1) ? `1px solid ${t.border}` : 'none',
          }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: t.text }}>
                  {txn.client_name ?? `Cliente #${txn.client_id}`}
                </div>
                <div style={{ fontSize: 11, color: t.textMuted }}>
                  → {txn.beneficiary_name ?? `Benef. #${txn.beneficiary_id}`} · {fmtDate(txn.created_at)}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>{fmtBRL(txn.amount)}</span>
              <RiskBadge level={txn.risk_level} />
              <StatusBadge status={txn.status} />
            </div>
          </div>
        ))}
      </Card>

      {/* Quick actions */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
        {[
          { label: 'Painel de auditoria', sub: 'Análises, logs, divergências', to: '/admin/audit', icon: 'audit' as NavIconName },
          { label: 'Clientes', sub: `${pendingReview.length} caso(s) aguardando decisão`, to: '/admin/clients', icon: 'clients' as NavIconName },
          { label: 'Métricas', sub: 'KPIs e indicadores de desempenho', to: '/admin/metrics', icon: 'metrics' as NavIconName },
        ].map(item => (
          <button
            key={item.to}
            onClick={() => navigate(item.to)}
            style={{
              background: t.surface, border: `1px solid ${t.border}`,
              borderRadius: 10, padding: '16px 18px',
              cursor: 'pointer', fontFamily: t.font,
              textAlign: 'left', transition: 'box-shadow 0.15s, border-color 0.15s',
              boxShadow: t.shadowSm,
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = t.accent
              ;(e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 0 2px ${t.accent}22`
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = t.border
              ;(e.currentTarget as HTMLButtonElement).style.boxShadow = t.shadowSm
            }}
          >
            <div style={{ display: 'flex', marginBottom: 8, color: t.accent }}><NavIcon name={item.icon} size={22} /></div>
            <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>{item.label}</div>
            <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>{item.sub}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
