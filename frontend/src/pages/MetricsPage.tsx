// Tela 9 — Painel de Métricas
// Indicadores calculados em tempo real a partir do banco do simulador.
// Todos os valores são derivados de dados reais — nenhum é estático ou inventado.
// Quando não há dados suficientes, exibe "Dados insuficientes".

import { useState, useEffect, useCallback } from 'react'
import { fetchMetrics } from '../services/api'
import type { MetricsSummary, ClassificationDetail, RiskScoreBucket } from '../types/metrics'
import { Card, CardHeader, Btn, Spinner, Badge, clr, fmtDate, agentLabel, statusLabel } from './ui'

// ── Constantes de cor ─────────────────────────────────────────────────────────

const RISK_COLORS: Record<string, string> = {
  low: '#16a34a',
  medium: '#d97706',
  high: '#ea580c',
  critical: '#dc2626',
}

const ACTION_COLORS: Record<string, string> = {
  approve: '#16a34a',
  request_confirmation: '#d97706',
  escalate_to_human: '#ea580c',
  block: '#dc2626',
}

const ACTION_LABELS: Record<string, string> = {
  approve: 'Aprovar',
  request_confirmation: 'Confirmar',
  escalate_to_human: 'Escalar',
  block: 'Bloquear',
}

const CLF_COLORS: Record<string, string> = {
  TP: '#16a34a', FP: '#ef4444', TN: '#2563eb', FN: '#d97706',
}

// ── Componentes de micro-gráficos SVG ────────────────────────────────────────

function BarChart({
  items,
  colorMap,
  labelMap,
  height = 130,
}: {
  items: { key: string; value: number }[]
  colorMap: Record<string, string>
  labelMap: Record<string, string>
  height?: number
}) {
  const maxVal = Math.max(...items.map(i => i.value), 1)
  const barWidth = 44
  const gap = 12
  const width = items.length * (barWidth + gap) + gap
  const chartH = height - 36  // espaço para labels

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height }}>
      {items.map((item, idx) => {
        const x = gap + idx * (barWidth + gap)
        const barH = Math.max((item.value / maxVal) * chartH, item.value > 0 ? 3 : 0)
        const y = chartH - barH
        const color = colorMap[item.key] ?? '#9ca3af'
        const label = labelMap[item.key] ?? item.key
        return (
          <g key={item.key}>
            <rect x={x} y={y} width={barWidth} height={barH} fill={color} rx={3} />
            <text x={x + barWidth / 2} y={chartH + 14} textAnchor="middle" fontSize={10} fill={clr.textMuted}>
              {label}
            </text>
            {item.value > 0 && (
              <text x={x + barWidth / 2} y={y - 4} textAnchor="middle" fontSize={10} fill={color} fontWeight="700">
                {item.value}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

function DonutChart({
  slices,
  colorMap,
  labelMap,
  size = 120,
}: {
  slices: { key: string; value: number }[]
  colorMap: Record<string, string>
  labelMap: Record<string, string>
  size?: number
}) {
  const total = slices.reduce((s, x) => s + x.value, 0)
  if (total === 0) return <div style={{ textAlign: 'center', color: clr.textLight, fontSize: 12, padding: '20px 0' }}>Sem dados</div>

  const r = 42
  const cx = size / 2
  const cy = size / 2
  const activeSlices = slices.filter(s => s.value > 0)
  const paths = activeSlices.map((s, index) => {
    const fraction = s.value / total
    const previousFraction = activeSlices.slice(0, index).reduce((sum, item) => sum + item.value / total, 0)
    const startAngle = -Math.PI / 2 + previousFraction * 2 * Math.PI
    const endAngle = startAngle + fraction * 2 * Math.PI

    const x1 = cx + r * Math.cos(startAngle)
    const y1 = cy + r * Math.sin(startAngle)
    const x2 = cx + r * Math.cos(endAngle)
    const y2 = cy + r * Math.sin(endAngle)
    const large = fraction > 0.5 ? 1 : 0

    return {
      key: s.key,
      value: s.value,
      d: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`,
      color: colorMap[s.key] ?? '#9ca3af',
      label: labelMap[s.key] ?? s.key,
    }
  })

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
        {paths.map(p => (
          <path key={p.key} d={p.d} fill={p.color} stroke="#fff" strokeWidth={1.5} />
        ))}
        <circle cx={cx} cy={cy} r={22} fill="#fff" />
        <text x={cx} y={cy + 4} textAnchor="middle" fontSize={11} fontWeight="700" fill={clr.text}>
          {total}
        </text>
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {paths.map(p => (
          <div key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
            <span style={{ width: 10, height: 10, background: p.color, borderRadius: 2, flexShrink: 0 }} />
            <span style={{ color: clr.textMuted }}>{p.label}</span>
            <span style={{ fontWeight: 700, color: clr.text }}>{p.value}</span>
            <span style={{ color: clr.textLight }}>({((p.value / total) * 100).toFixed(0)}%)</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ScoreHistogram({ buckets, height = 90 }: { buckets: RiskScoreBucket[]; height?: number }) {
  const maxCount = Math.max(...buckets.map(b => b.count), 1)
  const chartH = height - 20
  const barW = 22
  const gap = 3
  const width = buckets.length * (barW + gap)

  function bucketColor(i: number) {
    if (i < 3) return RISK_COLORS.low
    if (i < 6) return RISK_COLORS.medium
    if (i < 8) return RISK_COLORS.high
    return RISK_COLORS.critical
  }

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height }}>
        {buckets.map((b, i) => {
          const barH = Math.max((b.count / maxCount) * chartH, b.count > 0 ? 2 : 0)
          const x = i * (barW + gap)
          const y = chartH - barH
          return (
            <g key={b.range}>
              <rect x={x} y={y} width={barW} height={barH} fill={bucketColor(i)} rx={2} />
              {b.count > 0 && (
                <text x={x + barW / 2} y={y - 2} textAnchor="middle" fontSize={8} fill={bucketColor(i)}>
                  {b.count}
                </text>
              )}
              <text x={x + barW / 2} y={height - 2} textAnchor="middle" fontSize={7} fill={clr.textLight}>
                {i * 10}%
              </text>
            </g>
          )
        })}
      </svg>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 4 }}>
        {[['0–30% Baixo', RISK_COLORS.low], ['30–60% Médio', RISK_COLORS.medium], ['60–85% Alto', RISK_COLORS.high], ['85–100% Crítico', RISK_COLORS.critical]].map(([label, color]) => (
          <span key={label as string} style={{ fontSize: 9, color: clr.textLight, display: 'flex', alignItems: 'center', gap: 3 }}>
            <span style={{ width: 8, height: 8, background: color as string, borderRadius: 1, display: 'inline-block' }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Componentes de seção ──────────────────────────────────────────────────────

function KpiCard({ label, value, sub, color, note }: {
  label: string; value: string | number; sub?: string; color?: string; note?: string
}) {
  return (
    <div style={{
      background: clr.surfaceAlt, border: `1px solid ${clr.border}`,
      borderRadius: 8, padding: '14px 16px',
      borderLeft: color ? `3px solid ${color}` : undefined,
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 800, color: color ?? clr.text, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: clr.textMuted, marginTop: 4 }}>{sub}</div>}
      {note && <div style={{ fontSize: 10, color: clr.textLight, marginTop: 3, fontStyle: 'italic' }}>{note}</div>}
    </div>
  )
}

function Insuf({ msg }: { msg?: string }) {
  return (
    <div style={{
      background: '#f9fafb', border: '1px dashed #d1d5db',
      borderRadius: 6, padding: '16px', textAlign: 'center',
      color: clr.textLight, fontSize: 13,
    }}>
      Dados insuficientes{msg ? ` — ${msg}` : '.'}
    </div>
  )
}

function MetricRow({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '6px 0', borderBottom: `1px solid ${clr.border}` }}>
      <span style={{ fontSize: 12, color: clr.textMuted }}>{label}</span>
      <div style={{ textAlign: 'right' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: clr.text }}>{value}</span>
        {note && <div style={{ fontSize: 10, color: clr.textLight }}>{note}</div>}
      </div>
    </div>
  )
}

function ClassificationBadge({ type }: { type: string }) {
  const color = CLF_COLORS[type] ?? '#6b7280'
  const labels: Record<string, string> = {
    TP: 'Verdadeiro Positivo',
    FP: 'Falso Positivo',
    TN: 'Verdadeiro Negativo',
    FN: 'Falso Negativo',
  }
  return (
    <Badge text={`${type} — ${labels[type] ?? type}`} color={color} />
  )
}

// ── Filtros ───────────────────────────────────────────────────────────────────

type ModeFilter = 'all' | 'AI_MODE' | 'RULES_MODE'

// ── Página principal ──────────────────────────────────────────────────────────

export default function MetricsPage() {
  const [data, setData] = useState<MetricsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modeFilter, setModeFilter] = useState<ModeFilter>('all')
  const [expandedSection, setExpandedSection] = useState<string | null>('overview')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchMetrics()
      setData(result)
    } catch {
      setError('Não foi possível carregar as métricas. Verifique se o backend está em execução.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const toggle = (key: string) =>
    setExpandedSection(s => s === key ? null : key)

  if (loading) return (
    <div style={{ textAlign: 'center', padding: 60, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
      <Spinner size={32} />
      <span style={{ color: clr.textMuted, fontSize: 14 }}>Calculando métricas…</span>
    </div>
  )

  if (error || !data) return (
    <Card>
      <div style={{ textAlign: 'center', padding: 40, color: '#991b1b' }}>
        {error ?? 'Erro desconhecido.'}
        <div style={{ marginTop: 16 }}>
          <Btn variant="secondary" onClick={refresh}>Tentar novamente</Btn>
        </div>
      </div>
    </Card>
  )

  const { volume, risk_distribution, rates, timing, agent_timing,
    divergence, audited_decisions, component_failures,
    action_distribution, status_distribution, classification,
    mode_breakdown, risk_score_distribution } = data

  // Filtra por modo quando possível
  const modeNote = modeFilter !== 'all'
    ? `Filtro: ${modeFilter === 'AI_MODE' ? 'IA generativa' : 'motor de regras'} — os indicadores gerais continuam consolidados.`
    : undefined

  const modeTotal = mode_breakdown.AI_MODE + mode_breakdown.RULES_MODE + mode_breakdown.unknown

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Header de controles ── */}
      <div style={{
        background: '#fff', border: `1px solid ${clr.border}`,
        borderRadius: 10, padding: '14px 20px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12,
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: clr.text }}>Painel de métricas</h1>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: clr.textMuted }}>
            Calculado em tempo real · {fmtDate(data.generated_at)} ·{' '}
            <span style={{ fontStyle: 'italic' }}>Dados 100% sintéticos — simulador acadêmico</span>
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Filtro por modo */}
          <div style={{ display: 'flex', gap: 4, background: clr.surfaceAlt, borderRadius: 6, padding: 3 }}>
            {(['all', 'AI_MODE', 'RULES_MODE'] as ModeFilter[]).map(m => (
              <button
                key={m}
                onClick={() => setModeFilter(m)}
                style={{
                  background: modeFilter === m ? '#2563eb' : 'transparent',
                  color: modeFilter === m ? '#fff' : clr.textMuted,
                  border: 'none', borderRadius: 4, padding: '4px 10px',
                  fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                }}
              >
                {m === 'all' ? 'Todos' : m === 'AI_MODE' ? 'IA generativa' : 'Motor de regras'}
              </button>
            ))}
          </div>
          <Btn variant="ghost" small onClick={refresh}>Atualizar</Btn>
        </div>
      </div>

      {modeNote && (
        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, padding: '8px 14px', fontSize: 12, color: '#92400e' }}>
          {modeNote}
        </div>
      )}

      {/* ── Aviso sobre natureza dos dados ── */}
      <div style={{ background: '#f0f7ff', border: '1px solid #bfdbfe', borderRadius: 8, padding: '10px 16px', fontSize: 12, color: '#1e40af' }}>
        <strong>Contexto acadêmico:</strong> todas as métricas são derivadas de dados sintéticos do simulador.
        Os valores <strong>não representam evidência de redução real de fraudes no Banco do Brasil</strong> nem de qualquer instituição real.
      </div>

      {/* ── KPIs principais ── */}
      <SectionHeader title="1. Indicadores de volume" expanded={expandedSection === 'overview'} onToggle={() => toggle('overview')} />
      {expandedSection === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
          <KpiCard label="Transferências analisadas" value={volume.total_transactions} color="#2563eb" />
          <KpiCard label="Análises concluídas" value={volume.total_analyses} color="#7c3aed" />
          <KpiCard label="Logs de auditoria" value={volume.total_audit_logs} color="#0891b2" />
          <KpiCard label="Decisões auditadas" value={audited_decisions} sub="decision_engine + gateway" color="#059669" />
          <KpiCard
            label="Taxa de confirmação"
            value={rates.insufficient_data ? '—' : rates.confirmation_rate != null ? `${(rates.confirmation_rate * 100).toFixed(1)}%` : '—'}
            sub={`${rates.confirmation_count} operações`}
            color="#d97706"
            note={rates.insufficient_data ? 'Dados insuficientes' : undefined}
          />
          <KpiCard
            label="Taxa de revisão humana"
            value={rates.insufficient_data ? '—' : rates.human_review_rate != null ? `${(rates.human_review_rate * 100).toFixed(1)}%` : '—'}
            sub={`${rates.human_review_count} operações`}
            color="#ea580c"
            note={rates.insufficient_data ? 'Dados insuficientes' : undefined}
          />
          <KpiCard
            label="Taxa de divergência"
            value={divergence.divergence_rate != null ? `${(divergence.divergence_rate * 100).toFixed(1)}%` : '—'}
            sub={`${divergence.divergence_count} divergências`}
            color="#7c3aed"
          />
          <KpiCard
            label="Falhas detectadas"
            value={Object.values(component_failures).reduce((a, b) => a + b, 0)}
            sub="por componentes monitorados"
            color={Object.values(component_failures).reduce((a, b) => a + b, 0) > 0 ? '#dc2626' : '#16a34a'}
          />
        </div>
      )}

      {/* ── Modo de execução ── */}
      <SectionHeader title="2. Tecnologia de análise" expanded={expandedSection === 'mode'} onToggle={() => toggle('mode')} />
      {expandedSection === 'mode' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Distribuição por modo
            </div>
            {modeTotal === 0 ? <Insuf msg="nenhuma análise registrada" /> : (
              <DonutChart
                slices={[
                  { key: 'AI_MODE', value: mode_breakdown.AI_MODE },
                  { key: 'RULES_MODE', value: mode_breakdown.RULES_MODE },
                  { key: 'unknown', value: mode_breakdown.unknown },
                ]}
                colorMap={{ AI_MODE: '#2563eb', RULES_MODE: '#16a34a', unknown: '#9ca3af' }}
                labelMap={{ AI_MODE: 'IA generativa', RULES_MODE: 'Motor de regras', unknown: 'Registros anteriores' }}
              />
            )}
          </Card>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Detalhamento
            </div>
            <MetricRow label="Análises com IA generativa" value={`${mode_breakdown.AI_MODE}`} note="Modelo de linguagem habilitado" />
            <MetricRow label="Análises pelo motor de regras" value={`${mode_breakdown.RULES_MODE}`} note="Avaliação determinística do sistema" />
            <MetricRow label="Registros anteriores" value={`${mode_breakdown.unknown}`} />
            <div style={{ marginTop: 10, background: '#f9fafb', border: '1px dashed #d1d5db', borderRadius: 6, padding: '8px 10px', fontSize: 11, color: clr.textMuted }}>
              O motor de regras mantém a avaliação disponível de forma consistente quando o modelo generativo não está ativo.
            </div>
          </Card>
        </div>
      )}

      {/* ── Distribuição de risco ── */}
      <SectionHeader title="3. Distribuição por nível de risco" expanded={expandedSection === 'risk'} onToggle={() => toggle('risk')} />
      {expandedSection === 'risk' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Por nível de risco
            </div>
            {risk_distribution.total === 0 ? <Insuf /> : (
              <>
                <DonutChart
                  slices={[
                    { key: 'low', value: risk_distribution.counts.low },
                    { key: 'medium', value: risk_distribution.counts.medium },
                    { key: 'high', value: risk_distribution.counts.high },
                    { key: 'critical', value: risk_distribution.counts.critical },
                  ]}
                  colorMap={RISK_COLORS}
                  labelMap={{ low: 'Baixo', medium: 'Médio', high: 'Alto', critical: 'Crítico' }}
                />
              </>
            )}
          </Card>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Histograma de scores de risco
            </div>
            {risk_score_distribution.every(b => b.count === 0) ? <Insuf /> : (
              <ScoreHistogram buckets={risk_score_distribution} />
            )}
          </Card>
        </div>
      )}

      {/* ── Distribuição de ações ── */}
      <SectionHeader title="4. Distribuição de decisões" expanded={expandedSection === 'actions'} onToggle={() => toggle('actions')} />
      {expandedSection === 'actions' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Ações recomendadas pelo pipeline
            </div>
            {action_distribution.total === 0 ? <Insuf /> : (
              <BarChart
                items={Object.entries(action_distribution.counts).map(([k, v]) => ({ key: k, value: v }))}
                colorMap={ACTION_COLORS}
                labelMap={ACTION_LABELS}
              />
            )}
          </Card>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Distribuição de status das transações
            </div>
            {Object.keys(status_distribution.counts).length === 0 ? <Insuf /> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
                {Object.entries(status_distribution.counts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([status, count]) => {
                    const pct = status_distribution.percentages[status]
                    return (
                      <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ minWidth: 180, fontSize: 11, color: clr.textMuted }}>{statusLabel(status)}</span>
                        <div style={{ flex: 1, background: clr.border, borderRadius: 3, height: 8, overflow: 'hidden' }}>
                          <div style={{ width: `${pct ?? 0}%`, height: '100%', background: '#2563eb', borderRadius: 3 }} />
                        </div>
                        <span style={{ fontSize: 11, fontWeight: 700, minWidth: 30, textAlign: 'right' }}>{count}</span>
                        <span style={{ fontSize: 10, color: clr.textLight, minWidth: 36 }}>{pct != null ? `${pct}%` : ''}</span>
                      </div>
                    )
                  })}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Tempo de execução ── */}
      <SectionHeader title="5. Tempo de análise" expanded={expandedSection === 'timing'} onToggle={() => toggle('timing')} />
      {expandedSection === 'timing' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Tempo total de análise por transação
            </div>
            {timing.insufficient_data ? <Insuf msg="necessário ≥ 2 análises completas com timestamps" /> : (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 10 }}>
                  {[
                    { label: 'Média', val: timing.avg_ms },
                    { label: 'Mediana', val: timing.median_ms },
                    { label: 'Mínimo', val: timing.min_ms },
                    { label: 'Máximo', val: timing.max_ms },
                  ].map(({ label, val }) => (
                    <div key={label} style={{ background: clr.surfaceAlt, borderRadius: 6, padding: '8px 10px', border: `1px solid ${clr.border}` }}>
                      <div style={{ fontSize: 10, color: clr.textMuted, fontWeight: 700, textTransform: 'uppercase', marginBottom: 2 }}>{label}</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: clr.text }}>{val != null ? `${val.toFixed(0)}ms` : '—'}</div>
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: clr.textMuted }}>Amostras: {timing.sample_size}</div>
              </>
            )}
          </Card>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Tempo por agente
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Object.entries(agent_timing).map(([agent, stats]) => (
                <div key={agent} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ minWidth: 160, fontSize: 11, color: clr.textMuted }}>{agentLabel(agent)}</span>
                  {stats.insufficient_data || stats.avg_ms == null ? (
                    <span style={{ fontSize: 11, color: clr.textLight, fontStyle: 'italic' }}>Dados insuficientes</span>
                  ) : (
                    <>
                      <div style={{ flex: 1, background: clr.border, borderRadius: 3, height: 6, overflow: 'hidden' }}>
                        <div style={{ width: `${Math.min(stats.avg_ms / 500 * 100, 100)}%`, height: '100%', background: '#2563eb', borderRadius: 3 }} />
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 700, minWidth: 50, textAlign: 'right' }}>{stats.avg_ms.toFixed(0)}ms</span>
                      <span style={{ fontSize: 10, color: clr.textLight, minWidth: 40 }}>n={stats.sample_size}</span>
                    </>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ── Falhas por componente ── */}
      <SectionHeader title="6. Disponibilidade dos componentes" expanded={expandedSection === 'failures'} onToggle={() => toggle('failures')} />
      {expandedSection === 'failures' && (
        <Card>
          {Object.keys(component_failures).length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#16a34a', fontSize: 14 }}>
              <span style={{ fontSize: 24, color: '#15803d' }}>✓</span>
              <span>Nenhuma falha de componente registrada nos dados disponíveis.</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 4 }}>
                Componentes com falhas registradas
              </div>
              {Object.entries(component_failures).sort(([, a], [, b]) => b - a).map(([comp, count]) => (
                <div key={comp} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6 }}>
                  <code style={{ fontSize: 12, color: '#991b1b' }}>{comp}</code>
                  <span style={{ fontWeight: 700, fontSize: 13, color: '#dc2626' }}>{count} erro{count > 1 ? 's' : ''}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ── Avaliação de classificação ── */}
      <SectionHeader title="7. Avaliação dos cenários demonstrativos" expanded={expandedSection === 'classification'} onToggle={() => toggle('classification')} />
      {expandedSection === 'classification' && (
        <ClassificationSection clf={classification} />
      )}

      {/* ── Divergências ── */}
      <SectionHeader title="8. Divergências entre análises" expanded={expandedSection === 'divergence'} onToggle={() => toggle('divergence')} />
      {expandedSection === 'divergence' && (
        <Card>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
            <KpiCard label="Total de divergências" value={divergence.divergence_count} color="#7c3aed" />
            <KpiCard label="Análises concluídas" value={divergence.completed_analyses} />
            <KpiCard
              label="Taxa de divergência"
              value={divergence.divergence_rate != null ? `${(divergence.divergence_rate * 100).toFixed(1)}%` : '—'}
              note="divergências / análises concluídas"
              color={divergence.divergence_rate != null && divergence.divergence_rate > 0.2 ? '#d97706' : '#16a34a'}
            />
          </div>
          <div style={{ fontSize: 12, color: clr.textMuted, background: clr.surfaceAlt, borderRadius: 6, padding: '10px 12px', lineHeight: 1.6 }}>
            <strong>Definição:</strong> Divergência é detectada quando o spread (diferença entre o maior e menor score de risco entre agentes) supera 0,40 (40 pontos percentuais).
            O Decision Engine aplica automaticamente a decisão mais conservadora em caso de divergência.
          </div>
        </Card>
      )}

      {/* ── Documentação das fórmulas ── */}
      <SectionHeader title="9. Metodologia e limitações" expanded={expandedSection === 'docs'} onToggle={() => toggle('docs')} />
      {expandedSection === 'docs' && <FormulaDocumentation />}

    </div>
  )
}

// ── Seção de classificação ────────────────────────────────────────────────────

function ClassificationSection({ clf }: { clf: ReturnType<typeof extractClassification> }) {
  if (!clf.available) {
    return (
      <Card>
        <Insuf msg={clf.reason ?? 'necessário ao menos 2 transações com rótulo de referência'} />
        <div style={{ marginTop: 12, fontSize: 12, color: clr.textMuted }}>
          <strong>Rótulos disponíveis:</strong>{' '}
          {Object.entries(clf.definition?.reference_labels ?? {}).map(([id, label]) => (
            <span key={id} style={{ display: 'inline-block', marginRight: 8 }}>
              <code>{id}</code> → <Badge text={label ? 'positivo' : 'negativo'} color={label ? '#dc2626' : '#16a34a'} small />
            </span>
          ))}
        </div>
      </Card>
    )
  }

  const confMatrix = [
    { label: 'TP', value: clf.tp!, description: 'Verdadeiro Positivo — sistema alertou e era realmente suspeito' },
    { label: 'FP', value: clf.fp!, description: 'Falso Positivo — sistema alertou mas era legítimo' },
    { label: 'TN', value: clf.tn!, description: 'Verdadeiro Negativo — sistema liberou e era realmente seguro' },
    { label: 'FN', value: clf.fn!, description: 'Falso Negativo — sistema liberou mas era suspeito' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Aviso de dados sintéticos */}
      <div style={{ background: '#fef9c3', border: '1px solid #fde047', borderRadius: 8, padding: '10px 16px', fontSize: 12, color: '#713f12' }}>
        <strong>Aviso:</strong> {clf.definition.disclaimer}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Matriz de confusão */}
        <Card>
          <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Matriz de confusão ({clf.labeled_count} cenários rotulados)
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 12 }}>
            {confMatrix.map(({ label, value, description }) => (
              <div key={label} style={{
                background: CLF_COLORS[label] + '12',
                border: `1px solid ${CLF_COLORS[label]}40`,
                borderRadius: 8, padding: '12px',
                borderLeft: `3px solid ${CLF_COLORS[label]}`,
              }}>
                <div style={{ fontSize: 24, fontWeight: 800, color: CLF_COLORS[label] }}>{value}</div>
                <div style={{ fontSize: 11, fontWeight: 700, color: CLF_COLORS[label] }}>{label}</div>
                <div style={{ fontSize: 10, color: clr.textMuted, marginTop: 3, lineHeight: 1.4 }}>{description}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Métricas derivadas */}
        <Card>
          <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Métricas derivadas
          </div>
          <MetricRow
            label="Precisão"
            value={clf.precision != null ? `${(clf.precision * 100).toFixed(1)}%` : '—'}
            note={`Fórmula: TP / (TP + FP) = ${clf.tp!} / (${clf.tp!} + ${clf.fp!})`}
          />
          <MetricRow
            label="Recall (Sensibilidade)"
            value={clf.recall != null ? `${(clf.recall * 100).toFixed(1)}%` : '—'}
            note={`Fórmula: TP / (TP + FN) = ${clf.tp!} / (${clf.tp!} + ${clf.fn!})`}
          />
          <MetricRow
            label="F1-Score"
            value={clf.f1_score != null ? `${(clf.f1_score * 100).toFixed(1)}%` : '—'}
            note="Fórmula: 2 × Precisão × Recall / (Precisão + Recall)"
          />
          <MetricRow
            label="Acurácia"
            value={clf.accuracy != null ? `${(clf.accuracy * 100).toFixed(1)}%` : '—'}
            note={`Fórmula: (TP + TN) / (TP + FP + TN + FN)`}
          />

          <div style={{ marginTop: 10, fontSize: 11, color: clr.textMuted, background: clr.surfaceAlt, borderRadius: 6, padding: '8px 10px' }}>
            <strong>Classe positiva:</strong> {clf.definition.positive_class}
          </div>
        </Card>
      </div>

      {/* Detalhes por cenário */}
      {clf.details && clf.details.length > 0 && (
        <Card>
          <div style={{ fontSize: 12, fontWeight: 700, color: clr.textMuted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Classificação por cenário
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: clr.surfaceAlt }}>
                  {['ID externo', 'Rótulo de referência', 'Previsão do sistema', 'Status', 'Nível de risco', 'Classificação'].map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', borderBottom: `2px solid ${clr.border}` }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {clf.details.map((d: ClassificationDetail) => (
                  <tr key={d.external_id}>
                    <td style={{ padding: '8px 12px', borderBottom: `1px solid ${clr.border}` }}>
                      <code style={{ fontSize: 11 }}>{d.external_id}</code>
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: `1px solid ${clr.border}` }}>
                      <Badge text={d.reference_label} color={d.reference_label === 'positive' ? '#dc2626' : '#16a34a'} />
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: `1px solid ${clr.border}` }}>
                      <Badge text={d.predicted} color={d.predicted === 'positive' ? '#ea580c' : '#2563eb'} />
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: `1px solid ${clr.border}`, fontSize: 11, color: clr.textMuted }}>
                      {statusLabel(d.status)}
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: `1px solid ${clr.border}` }}>
                      <span style={{ color: RISK_COLORS[d.risk_level] ?? '#6b7280', fontWeight: 700, fontSize: 11 }}>
                        {d.risk_level}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: `1px solid ${clr.border}` }}>
                      <ClassificationBadge type={d.classification} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

// Helper para tipagem (satisfaz TS sem duplicar o tipo)
function extractClassification(clf: MetricsSummary['classification']) { return clf }

// ── Documentação de fórmulas ──────────────────────────────────────────────────

function FormulaDocumentation() {
  const formulas = [
    { name: 'Taxa de confirmação', formula: 'confirmações / total de transações', vars: 'confirmações = status awaiting_confirmation ou analyses com confirmation_purpose ≠ null' },
    { name: 'Taxa de revisão humana', formula: 'revisões humanas / total de transações', vars: 'revisões = status human_review_pending | escalated_to_human | human_approved | human_rejected' },
    { name: 'Tempo médio de análise', formula: 'mean(completed_at − started_at) por análise', vars: 'Em milissegundos; requer started_at e completed_at preenchidos' },
    { name: 'Tempo por agente', formula: 'mean(execution_time_ms) por componente', vars: 'Fontes: audit_logs.execution_time_ms + AgentResult.execution_time_ms nos campos JSON' },
    { name: 'Taxa de divergência', formula: 'divergências / análises concluídas', vars: 'Divergência quando spread entre agentes > 0,40' },
    { name: 'Precisão', formula: 'TP / (TP + FP)', vars: 'Entre os alertados, fração realmente suspeita' },
    { name: 'Recall', formula: 'TP / (TP + FN)', vars: 'Entre os realmente suspeitos, fração capturada' },
    { name: 'F1-Score', formula: '2 × P × R / (P + R)', vars: 'Média harmônica entre Precisão e Recall' },
    { name: 'Acurácia', formula: '(TP + TN) / (TP + FP + TN + FN)', vars: 'Fração de previsões corretas no total' },
    { name: 'Histograma de scores', formula: 'Bucket[i] = count(scores ∈ [i×10%, (i+1)×10%))', vars: '10 buckets de 10% cada; bucket 9 inclui score = 100%' },
  ]

  const limitations = [
    'Os 3 cenários seed têm rótulos de referência definidos manualmente — não são coletados de fraudes reais.',
    'Transações criadas via simulador livre não têm rótulo — são excluídas das métricas de classificação.',
    'O sistema não tem acesso a dados históricos reais de fraudes.',
    'O motor de regras e o modelo generativo usam abordagens diferentes; seus resultados devem ser interpretados separadamente.',
    'Tempo de análise pode ser 0ms para transações seed (sem execução real do pipeline).',
    'Métricas de classificação com 3 amostras têm baixa significância estatística.',
    'NÃO use estes resultados como evidência de desempenho em produção.',
  ]

  const metrics_available = [
    'Volume de transações e análises — concluído',
    'Distribuição por nível de risco — concluído',
    'Taxa de confirmação adicional — concluído',
    'Taxa de revisão humana — concluído',
    'Tempo médio de análise — concluído quando o pipeline é executado',
    'Tempo por agente — concluído quando há medição de execução',
    'Taxa de divergência — concluído',
    'Decisões auditadas — concluído',
    'Falhas por componente — concluído',
    'Distribuição de ações finais — concluído',
    'Métricas de classificação — concluído nos três cenários rotulados',
    'Comparação entre modos — concluído quando ambos estão presentes',
  ]

  const metrics_unavailable = [
    'Comparação de resultados por cenário filtrado por modo — dados insuficientes para separação significativa.',
    'Calibração de score (reliability diagram) — requer ≥ 50 amostras por bucket.',
    'AUC-ROC — requer saída de probabilidade contínua + múltiplas amostras por classe.',
    'Métricas de latência de rede — não monitorado nesta versão.',
    'Desempenho em produção — este simulador usa dados 100% sintéticos.',
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card>
        <CardHeader title="Fórmulas implementadas" subtitle="Denominadores e definições de cada métrica" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {formulas.map(({ name, formula, vars }) => (
            <div key={name} style={{ padding: '8px 0', borderBottom: `1px solid ${clr.border}` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: clr.text }}>{name}</div>
              <div style={{ display: 'flex', gap: 8, marginTop: 3 }}>
                <code style={{ fontSize: 11, background: '#f0f7ff', color: '#1e40af', borderRadius: 4, padding: '1px 6px' }}>{formula}</code>
                <span style={{ fontSize: 11, color: clr.textMuted }}>{vars}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Card>
          <CardHeader title="Métricas disponíveis" />
          <ul style={{ margin: 0, padding: '0 0 0 18px', fontSize: 12, color: clr.text, lineHeight: 2 }}>
            {metrics_available.map(m => <li key={m}>{m}</li>)}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Métricas não mensuráveis com este MVP" />
          <ul style={{ margin: 0, padding: '0 0 0 18px', fontSize: 12, color: '#dc2626', lineHeight: 2 }}>
            {metrics_unavailable.map(m => <li key={m}>{m}</li>)}
          </ul>
        </Card>
      </div>

      <Card>
        <CardHeader title="Limitações documentadas" />
        <ul style={{ margin: 0, paddingLeft: 28, paddingTop: 12, paddingBottom: 12, paddingRight: 12, fontSize: 12, color: '#92400e', lineHeight: 2, background: '#fffbeb', borderRadius: 6 }}>
          {limitations.map(l => <li key={l}>{l}</li>)}
        </ul>
      </Card>
    </div>
  )
}

// ── Cabeçalho de seção expansível ─────────────────────────────────────────────

function SectionHeader({ title, expanded, onToggle }: { title: string; expanded: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: expanded ? '#eff6ff' : '#f9fafb',
        border: `1px solid ${expanded ? '#bfdbfe' : clr.border}`,
        borderRadius: 8, padding: '10px 16px',
        width: '100%', textAlign: 'left', cursor: 'pointer',
        fontFamily: 'inherit', transition: 'background 0.15s',
      }}
    >
      <span style={{ fontWeight: 700, fontSize: 14, color: expanded ? '#1e40af' : clr.text }}>{title}</span>
      <span style={{ fontSize: 12, color: clr.textMuted }}>{expanded ? '▲ recolher' : '▼ expandir'}</span>
    </button>
  )
}
