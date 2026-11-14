// Tela 3 — Análise em andamento + Tela 5 — Resultado
// Exibe resultado real do backend. Estados: loading → resultado.
// Se backend retornar awaiting_confirmation, navega para /confirm.
// Se retornar human_review_pending, mostra card de revisão humana.

import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import type { TransferInitiatedResponse, AgentResultParsed } from '../types'
import {
  Card, CardHeader, Btn, RiskBar, RiskBadge, InfoCell,
  clr, STATUS_ICON, STATUS_LABEL, ACTION_LABEL,
  fmtBRL, parseJSON, parseFlags, riskColor,
} from './ui'

// Nomes dos agentes para exibição
const AGENT_LABELS: Record<string, { icon: string; label: string }> = {
  fraud_agent:          { icon: '🕵️', label: 'Agente de Fraude' },
  inconsistency_agent:  { icon: '🔍', label: 'Agente de Inconsistência' },
  behavioral_agent:     { icon: '📊', label: 'Agente Comportamental' },
  risk_agent:           { icon: '⚖️', label: 'Agente de Risco e Segurança' },
  orchestrator_agent:   { icon: '🎯', label: 'Orquestrador' },
}

function AgentCard({ agentKey, raw }: { agentKey: string; raw: string | null }) {
  const result = parseJSON<AgentResultParsed>(raw)
  const [expanded, setExpanded] = useState(false)
  if (!result) return null

  const { icon, label } = AGENT_LABELS[agentKey] ?? { icon: '🤖', label: agentKey }
  const color = riskColor(result.risk_score)
  const pct = Math.round(result.risk_score * 100)
  const flags = result.detected_signals?.length ? result.detected_signals : (result.flags ?? [])

  return (
    <div style={{
      border: `1px solid ${clr.border}`, borderRadius: 8,
      background: clr.surfaceAlt, overflow: 'hidden',
    }}>
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 14px', cursor: 'pointer',
          borderLeft: `3px solid ${color}`,
        }}
        onClick={() => setExpanded(e => !e)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>{icon}</span>
          <span style={{ fontWeight: 600, fontSize: 13 }}>{label}</span>
          {flags.length > 0 && (
            <span style={{
              background: '#fee2e2', color: '#b91c1c',
              borderRadius: 10, padding: '0 6px', fontSize: 10, fontWeight: 700,
            }}>
              {flags.length} flag{flags.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontWeight: 700, color, fontSize: 14 }}>{pct}%</span>
          <span style={{ color: clr.textMuted, fontSize: 12 }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '10px 14px', borderTop: `1px solid ${clr.border}` }}>
          {flags.length > 0 && (
            <div style={{ marginBottom: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {flags.map(f => (
                <span key={f} style={{
                  background: '#fee2e2', color: '#b91c1c',
                  borderRadius: 4, padding: '2px 7px', fontSize: 11,
                }}>{f}</span>
              ))}
            </div>
          )}

          <p style={{ margin: '0 0 8px', fontSize: 12, color: '#374151', lineHeight: 1.6 }}>
            {result.explanation || result.reasoning}
          </p>

          {result.evidence?.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 4 }}>
                Evidências
              </div>
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: '#374151', lineHeight: 1.6 }}>
                {result.evidence.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}

          <div style={{ display: 'flex', gap: 16, fontSize: 11, color: clr.textMuted }}>
            <span>Confiança: <strong>{Math.round(result.confidence * 100)}%</strong></span>
            <span>Modo: <strong style={{ color: result.mode === 'AI_MODE' ? '#2563eb' : '#16a34a' }}>{result.mode}</strong></span>
            <span>Modelo: <code>{result.model_used}</code></span>
            {result.execution_time_ms != null && (
              <span>Tempo: <strong>{result.execution_time_ms}ms</strong></span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function AnalysisPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const result = location.state?.result as TransferInitiatedResponse | null

  const [redirecting, setRedirecting] = useState(false)

  useEffect(() => {
    if (!result) {
      navigate('/', { replace: true })
      return
    }
    // Se awaiting_confirmation — navega para tela de confirmação
    if (result.transaction.status === 'awaiting_confirmation' && !redirecting) {
      setRedirecting(true)
      setTimeout(() => {
        navigate('/confirm', { state: { result } })
      }, 1800)
    }
  }, [result, navigate, redirecting])

  if (!result) return null

  const { transaction: txn, analysis, gateway: gw, message, pipeline_failed, failure_reason } = result

  // Pipeline falhou
  if (pipeline_failed) {
    return (
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        <Card>
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>⚠️</div>
            <h2 style={{ margin: '0 0 8px', color: '#b45309' }}>Análise não concluída</h2>
            <p style={{ color: clr.textMuted, fontSize: 14, maxWidth: 420, margin: '0 auto 20px' }}>
              {failure_reason ?? 'O pipeline de análise encontrou um problema. A transação foi mantida como pendente para revisão.'}
            </p>
            <div style={{
              background: '#fffbeb', border: '1px solid #fde68a',
              borderRadius: 8, padding: '10px 16px', marginBottom: 20, fontSize: 13, color: '#92400e',
            }}>
              A transação <code>{txn.external_id.slice(0, 14)}…</code> permanece como <strong>PENDENTE</strong> e não foi liberada automaticamente.
            </div>
            <Btn onClick={() => navigate('/')}>← Voltar ao painel</Btn>
          </div>
        </Card>
      </div>
    )
  }

  const status = txn.status
  const statusIcon = STATUS_ICON[status] ?? '⏳'
  const statusLabel = STATUS_LABEL[status] ?? status

  // Redirecionando para confirmação
  if (status === 'awaiting_confirmation') {
    return (
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        <Card>
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>⚠️</div>
            <h2 style={{ margin: '0 0 8px', color: '#d97706' }}>Confirmação necessária</h2>
            <p style={{ color: clr.textMuted, fontSize: 14 }}>
              Identificamos características incomuns nesta operação. Redirecionando para verificação…
            </p>
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'center' }}>
              <span style={{
                display: 'inline-block', width: 24, height: 24,
                border: '2px solid #d97706', borderTopColor: 'transparent',
                borderRadius: '50%', animation: 'spin 0.7s linear infinite',
              }} />
            </div>
          </div>
        </Card>
      </div>
    )
  }

  const riskScore = gw?.risk_score ?? analysis?.overall_risk_score ?? 0
  const riskLevel = gw?.risk_level ?? 'low'
  const flags = gw?.flags ?? parseFlags(analysis?.flags)

  const resultColor: Record<string, string> = {
    released: '#16a34a', human_approved: '#16a34a',
    awaiting_confirmation: '#d97706', under_verification: '#d97706',
    human_review_pending: '#ea580c', escalated_to_human: '#ea580c',
    rejected: '#dc2626', human_rejected: '#dc2626',
    pending: '#6b7280',
  }
  const borderColor = resultColor[status] ?? '#6b7280'

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── Resultado principal ── */}
      <Card style={{ borderTop: `4px solid ${borderColor}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 28, marginBottom: 4 }}>{statusIcon}</div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: borderColor }}>
              {statusLabel}
            </h2>
            <div style={{ fontSize: 13, color: clr.textMuted, marginTop: 4 }}>{message}</div>
          </div>
          <RiskBadge level={riskLevel} />
        </div>

        <RiskBar score={riskScore} />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 12 }}>
          <InfoCell label="Valor" value={fmtBRL(txn.amount)} />
          <InfoCell label="Ação" value={ACTION_LABEL[gw?.final_action ?? ''] ?? (gw?.final_action ?? '—')} />
          <InfoCell label="Autorizado" value={gw?.authorized ? '✅ Sim' : '❌ Não'} color={gw?.authorized ? '#16a34a' : '#dc2626'} />
          {gw?.requires_confirmation && <InfoCell label="Confirmação" value="⚠️ Necessária" color="#d97706" />}
          {gw?.requires_human_review && <InfoCell label="Revisão humana" value="👤 Necessária" color="#ea580c" />}
          {gw?.policy_version && <InfoCell label="Política" value={gw.policy_version} />}
          {gw?.divergence_detected && <InfoCell label="Divergência" value="⚠️ Detectada" color="#ea580c" />}
        </div>

        {flags.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>
              Sinais detectados
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {flags.map(f => (
                <span key={f} style={{
                  background: '#fee2e2', color: '#b91c1c',
                  borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 600,
                }}>{f}</span>
              ))}
            </div>
          </div>
        )}

        {gw?.gateway_reasoning && (
          <div style={{ marginTop: 14, fontSize: 12, color: '#374151', borderTop: `1px solid ${clr.border}`, paddingTop: 10, lineHeight: 1.6 }}>
            {gw.gateway_reasoning}
          </div>
        )}

        {/* Próximos passos */}
        <div style={{ marginTop: 14, borderTop: `1px solid ${clr.border}`, paddingTop: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 8 }}>
            Próximos passos
          </div>
          <NextSteps status={status} txnId={txn.external_id} />
        </div>
      </Card>

      {/* ── Agentes ── */}
      {analysis && (
        <Card>
          <CardHeader
            title="Análise por agente"
            subtitle="Clique em cada agente para ver evidências e detalhes"
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <AgentCard agentKey="fraud_agent" raw={analysis.fraud_agent_result} />
            <AgentCard agentKey="inconsistency_agent" raw={analysis.inconsistency_agent_result} />
            <AgentCard agentKey="behavioral_agent" raw={analysis.behavioral_agent_result} />
            <AgentCard agentKey="risk_agent" raw={analysis.risk_agent_result} />
          </div>

          {analysis.divergence_detected && (
            <div style={{
              marginTop: 12, background: '#fff7ed', border: '1px solid #fed7aa',
              borderRadius: 8, padding: '10px 14px', fontSize: 12, color: '#9a3412',
            }}>
              <strong>⚠️ Divergência detectada entre agentes.</strong>{' '}
              Os agentes apresentaram avaliações significativamente diferentes. A decisão mais conservadora foi aplicada.
              {analysis.divergence_details && (() => {
                const d = parseJSON<{ spread: number; high_risk_agents: string[]; low_risk_agents: string[] }>(analysis.divergence_details)
                if (!d) return null
                return (
                  <span> Diferença: {(d.spread * 100).toFixed(0)}%.</span>
                )
              })()}
            </div>
          )}

          <div style={{ marginTop: 12, display: 'flex', gap: 10, fontSize: 11, color: clr.textMuted, flexWrap: 'wrap' }}>
            {analysis.policy_version && <span>Política: <code>{analysis.policy_version}</code></span>}
            {analysis.phase && <span>Fase: <code>{analysis.phase}</code></span>}
            {analysis.started_at && analysis.completed_at && (() => {
              const ms = new Date(analysis.completed_at).getTime() - new Date(analysis.started_at).getTime()
              return <span>Tempo total: <strong>{ms}ms</strong></span>
            })()}
          </div>
        </Card>
      )}

      <div style={{ display: 'flex', gap: 10 }}>
        <Btn variant="secondary" onClick={() => navigate('/')}>← Início</Btn>
        <Btn variant="secondary" onClick={() => navigate('/transfer')}>🔄 Nova transferência</Btn>
        <Btn variant="secondary" onClick={() => navigate('/audit')}>📋 Ver auditoria</Btn>
      </div>
    </div>
  )
}

function NextSteps({ status, txnId }: { status: string; txnId: string }) {
  const navigate = useNavigate()
  const steps: Record<string, React.ReactNode> = {
    released: (
      <p style={{ margin: 0, fontSize: 13, color: '#166534', lineHeight: 1.6 }}>
        ✅ A transferência foi liberada automaticamente pelo sistema de segurança adaptativa.
        Nenhuma ação adicional é necessária.
      </p>
    ),
    awaiting_confirmation: (
      <div>
        <p style={{ margin: '0 0 10px', fontSize: 13, lineHeight: 1.6 }}>
          ⚠️ O sistema identificou características incomuns nesta operação e solicita confirmação da finalidade.
        </p>
        <Btn onClick={() => navigate('/confirm', { state: { txnId } })}>
          Fornecer confirmação →
        </Btn>
      </div>
    ),
    human_review_pending: (
      <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6 }}>
        👤 Esta transferência foi encaminhada para revisão por um operador humano.
        O operador poderá aprová-la ou rejeitá-la no painel de revisão.
      </p>
    ),
    escalated_to_human: (
      <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6 }}>
        👤 Esta transferência foi escalada para análise humana adicional.
      </p>
    ),
    rejected: (
      <p style={{ margin: 0, fontSize: 13, color: '#991b1b', lineHeight: 1.6 }}>
        ❌ A transferência foi bloqueada por regra de segurança absoluta. Nenhum recurso automático disponível.
      </p>
    ),
    human_rejected: (
      <p style={{ margin: 0, fontSize: 13, color: '#991b1b', lineHeight: 1.6 }}>
        ❌ A transferência foi rejeitada após revisão humana.
      </p>
    ),
    human_approved: (
      <p style={{ margin: 0, fontSize: 13, color: '#166534', lineHeight: 1.6 }}>
        ✅ A transferência foi aprovada pelo revisor humano.
      </p>
    ),
    pending: (
      <p style={{ margin: 0, fontSize: 13, color: '#6b7280', lineHeight: 1.6 }}>
        ⏳ A análise encontrou um problema. A transação permanece pendente para revisão manual.
      </p>
    ),
  }
  return <>{steps[status] ?? <p style={{ margin: 0, color: clr.textMuted, fontSize: 13 }}>Status: {status}</p>}</>
}
