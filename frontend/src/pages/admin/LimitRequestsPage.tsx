import { useEffect, useState } from 'react'
import { fetchCreditLimitRequests, getApiErrorMessage, reviewCreditLimitRequest } from '../../services/api'
import type { CreditLimitAssessment, CreditLimitRequestResponse } from '../../types'
import { Btn, ErrorBox, Spinner, agentLabel, fmtBRL, riskColor, t } from '../../components/ui'

function assessment(raw: string): CreditLimitAssessment | null { try { return JSON.parse(raw) as CreditLimitAssessment } catch { return null } }

export default function LimitRequestsPage() {
  const [items, setItems] = useState<CreditLimitRequestResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [reviewerId, setReviewerId] = useState('funcionario-001')

  function load() { setLoading(true); fetchCreditLimitRequests().then(setItems).catch(() => setError('Não foi possível carregar a fila.')).finally(() => setLoading(false)) }
  useEffect(load, [])

  async function review(item: CreditLimitRequestResponse, action: 'approve' | 'reject') {
    setBusy(item.external_id); setError('')
    try {
      const updated = await reviewCreditLimitRequest(item.external_id, action, reviewerId, action === 'approve' ? 'Histórico e sinais revisados pelo funcionário.' : 'Pedido não aprovado após revisão humana.')
      setItems(current => current.map(row => row.external_id === item.external_id ? { ...row, ...updated } : row))
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Não foi possível registrar a decisão.'))
    } finally { setBusy('') }
  }

  return <div style={{ maxWidth: 1100, margin: '0 auto' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'end', marginBottom: 22 }}>
      <div><div style={{ fontSize: 11, color: t.primary, fontWeight: 800 }}>DECISÃO HUMANA OBRIGATÓRIA</div><h1 style={{ fontSize: 25, margin: '4px 0' }}>Pedidos de limite</h1><p style={{ color: t.textMuted, fontSize: 13 }}>Os agentes explicam os sinais; você confirma a decisão.</p></div>
      <label style={{ fontSize: 11, color: t.textMuted, fontWeight: 700 }}>IDENTIFICAÇÃO DO FUNCIONÁRIO<input value={reviewerId} onChange={event => setReviewerId(event.target.value)} style={{ display: 'block', marginTop: 5, border: `1px solid ${t.borderStrong}`, borderRadius: 10, padding: '9px 11px' }} /></label>
    </div>
    {error && <div style={{ marginBottom: 16 }}><ErrorBox message={error} /></div>}
    {loading ? <div style={{ padding: 60, textAlign: 'center' }}><Spinner size={30} /></div> : items.length === 0 ? <div style={{ background: '#fff', borderRadius: 18, padding: 36, color: t.textMuted, textAlign: 'center' }}>Nenhum pedido na fila.</div> : <div style={{ display: 'grid', gap: 15 }}>
      {items.map(item => { const data = assessment(item.agent_assessment); const pending = item.status === 'pending_review'; return <article key={item.external_id} style={{ background: '#fff', border: `1px solid ${pending ? t.warningBorder : t.border}`, borderRadius: 20, padding: 20, boxShadow: t.shadowSm }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}><div><span style={{ color: t.textMuted, fontSize: 11 }}>{item.client_name || `Cliente #${item.client_id}`}</span><h2 style={{ fontSize: 19, marginTop: 3 }}>{fmtBRL(item.current_limit)} → <span style={{ color: t.primary }}>{fmtBRL(item.requested_limit)}</span></h2><p style={{ color: t.textMuted, fontSize: 12, marginTop: 5 }}>{item.reason || 'Finalidade não informada'}</p></div><div style={{ textAlign: 'right' }}><span style={{ background: pending ? t.warningBg : item.status === 'approved' ? t.successBg : t.dangerBg, color: pending ? t.warning : item.status === 'approved' ? t.success : t.danger, borderRadius: 999, padding: '5px 10px', fontSize: 10, fontWeight: 800 }}>{pending ? 'AGUARDANDO VOCÊ' : item.status === 'approved' ? 'APROVADO' : 'RECUSADO'}</span>{data && <div style={{ marginTop: 9, color: riskColor(data.overall_risk_score), fontWeight: 800, fontSize: 13 }}>Risco {(data.overall_risk_score * 100).toFixed(0)}%</div>}</div></div>
        {data && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 9, marginTop: 17 }}>{data.agents.map(agent => <div key={agent.agent_name} style={{ background: t.surface2, border: `1px solid ${t.border}`, borderRadius: 12, padding: 12 }}><strong style={{ fontSize: 12 }}>{agentLabel(agent.agent_name)}</strong><div style={{ color: riskColor(agent.risk_score), fontWeight: 800, fontSize: 12, marginTop: 3 }}>Risco identificado: {(agent.risk_score * 100).toFixed(0)}%</div><p style={{ color: t.textMuted, fontSize: 11, lineHeight: 1.45, marginTop: 5 }}>{agent.explanation}</p></div>)}</div>}
        {pending && <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 9, marginTop: 17 }}><Btn variant="secondary" disabled={busy === item.external_id || !reviewerId} onClick={() => review(item, 'reject')}>Recusar</Btn><Btn disabled={busy === item.external_id || !reviewerId} onClick={() => review(item, 'approve')}>{busy === item.external_id ? <Spinner size={14} color="#fff" /> : 'Aprovar novo limite'}</Btn></div>}
      </article> })}
    </div>}
  </div>
}
