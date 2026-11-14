import { useEffect, useMemo, useState } from 'react'
import { fetchClients, fetchClientCards, fetchCreditLimitRequests, submitCreditLimitRequest } from '../../services/api'
import type { ClientSummary, CreditCardResponse, CreditLimitRequestResponse } from '../../types'
import { Btn, ErrorBox, Spinner, fmtBRL, t } from '../../components/ui'

const input: React.CSSProperties = { width: '100%', border: `1px solid ${t.borderStrong}`, borderRadius: 12, padding: '12px 14px', background: '#fff', color: t.text, fontSize: 14 }

export default function CardsPage() {
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [clientId, setClientId] = useState(() => {
    try { return localStorage.getItem('bobia_client_id') ?? '' } catch { return '' }
  })
  const [cards, setCards] = useState<CreditCardResponse[]>([])
  const [requests, setRequests] = useState<CreditLimitRequestResponse[]>([])
  const [requestedLimit, setRequestedLimit] = useState('')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const [flipped, setFlipped] = useState(false)
  const card = cards[0]

  useEffect(() => {
    fetchClients().then(data => {
      setClients(data)
      setClientId(current => current && data.some(item => item.external_id === current) ? current : data[0]?.external_id ?? '')
    }).catch(() => setError('Não foi possível carregar as contas.'))
  }, [])

  useEffect(() => {
    if (!clientId) return
    try { localStorage.setItem('bobia_client_id', clientId) } catch { /* sem persistência */ }
    setLoading(true)
    Promise.all([fetchClientCards(clientId), fetchCreditLimitRequests({ clientExternalId: clientId })])
      .then(([cardData, requestData]) => { setCards(cardData); setRequests(requestData); setError('') })
      .catch(() => setError('Não foi possível carregar cartão e solicitações.'))
      .finally(() => setLoading(false))
  }, [clientId])

  const usage = useMemo(() => card ? Math.min(100, (Number(card.used_credit) / Number(card.credit_limit)) * 100) : 0, [card])

  async function submit() {
    if (!card || !requestedLimit) return
    setSubmitting(true); setError('')
    try {
      const item = await submitCreditLimitRequest(card.external_id, requestedLimit.replace(',', '.'), reason || undefined)
      setRequests(current => [item, ...current])
      setRequestedLimit(''); setReason('')
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { error?: string; detail?: string } } }).response?.data
      setError(data?.error || data?.detail || 'Não foi possível enviar a solicitação.')
    } finally { setSubmitting(false) }
  }

  function moveCard(event: React.PointerEvent<HTMLDivElement>) {
    if (event.pointerType === 'touch') return
    const rect = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - rect.left) / rect.width - 0.5
    const y = (event.clientY - rect.top) / rect.height - 0.5
    setTilt({ x: -y * 13, y: x * 17 })
  }

  return (
    <div style={{ maxWidth: 920, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap', marginBottom: 22 }}>
        <div><div style={{ color: t.primary, fontSize: 12, fontWeight: 800, letterSpacing: .5 }}>MEUS CARTÕES</div><h1 style={{ fontSize: 26, marginTop: 3, color: t.text }}>Controle seu limite</h1><p style={{ color: t.textMuted, marginTop: 4, fontSize: 13 }}>Acompanhe gastos e envie um pedido para análise.</p></div>
        <select value={clientId} onChange={event => setClientId(event.target.value)} style={{ ...input, width: 220 }} aria-label="Conta do cliente">
          {clients.map(client => <option key={client.external_id} value={client.external_id}>{client.name}</option>)}
        </select>
      </div>

      {error && <div style={{ marginBottom: 16 }}><ErrorBox message={error} /></div>}
      {loading ? <div style={{ padding: 60, textAlign: 'center' }}><Spinner size={30} /></div> : !card ? <p>Nenhum cartão disponível.</p> : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 330px), 1fr))', gap: 22, alignItems: 'start' }}>
          <section>
            <div
              className="credit-card-scene"
              onPointerMove={moveCard}
              onPointerLeave={() => setTilt({ x: 0, y: 0 })}
              onClick={() => setFlipped(value => !value)}
              role="button"
              tabIndex={0}
              aria-label="Virar cartão"
              onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') setFlipped(value => !value) }}
            >
              <div className="credit-card-3d" style={{ transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y + (flipped ? 180 : 0)}deg)` }}>
                <div className="credit-card-face credit-card-front" style={{ background: `linear-gradient(135deg, ${card.color_start}, ${card.color_end})` }}>
                  <div className="card-orbit" />
                  <div style={{ display: 'flex', justifyContent: 'space-between', position: 'relative' }}><strong style={{ fontSize: 18 }}>BobIA</strong><span style={{ fontWeight: 800 }}>{card.brand}</span></div>
                  <div className="card-chip"><span /><span /><span /></div>
                  <div style={{ position: 'absolute', left: 24, right: 24, bottom: 22 }}>
                    <div style={{ fontSize: 17, letterSpacing: 2.2, fontWeight: 700 }}>{card.masked_number}</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 11, fontSize: 11, opacity: .84 }}><span>{clients.find(c => c.external_id === clientId)?.name.toUpperCase()}</span><span>VENCE {String(card.due_day).padStart(2, '0')}</span></div>
                  </div>
                </div>
                <div className="credit-card-face credit-card-back" style={{ background: `linear-gradient(145deg, ${card.color_end}, ${card.color_start})` }}>
                  <div className="magnetic-strip" />
                  <div className="signature-strip"><span>USO EXCLUSIVO DO CLIENTE</span><strong>347</strong></div>
                  <div className="card-back-copy"><strong>BobIA Bank</strong><span>Cartão sintético para demonstração acadêmica.</span></div>
                </div>
              </div>
            </div>
            <p className="card-interaction-hint">Mova o ponteiro para inclinar. Clique ou toque para virar.</p>

            <div style={{ background: '#fff', border: `1px solid ${t.border}`, borderRadius: 20, padding: 20, marginTop: 24, boxShadow: t.shadowSm }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><div><span style={{ color: t.textMuted, fontSize: 12 }}>Limite disponível</span><strong style={{ display: 'block', color: t.text, fontSize: 24, marginTop: 2 }}>{fmtBRL(card.available_credit)}</strong></div><div style={{ textAlign: 'right' }}><span style={{ color: t.textMuted, fontSize: 12 }}>Limite total</span><strong style={{ display: 'block', color: t.primary, marginTop: 5 }}>{fmtBRL(card.credit_limit)}</strong></div></div>
              <div style={{ height: 9, borderRadius: 99, background: t.primaryLight, marginTop: 17, overflow: 'hidden' }}><div style={{ width: `${usage}%`, height: '100%', borderRadius: 99, background: `linear-gradient(90deg,${t.primary},${t.primaryHover})` }} /></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 7, color: t.textMuted, fontSize: 11 }}><span>{fmtBRL(card.used_credit)} usados</span><span>{usage.toFixed(0)}%</span></div>
            </div>
          </section>

          <section style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ background: '#fff', border: `1px solid ${t.border}`, borderRadius: 20, padding: 21, boxShadow: t.shadowSm }}>
              <h2 style={{ fontSize: 18, color: t.text }}>Solicitar aumento</h2>
              <p style={{ color: t.textMuted, fontSize: 12, margin: '5px 0 16px', lineHeight: 1.5 }}>O pedido passa pelos agentes de risco e sempre exige uma decisão do funcionário.</p>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: t.textMuted, marginBottom: 6 }}>Novo limite</label>
              <input value={requestedLimit} onChange={event => setRequestedLimit(event.target.value.replace(/[^\d,.]/g, ''))} placeholder="Ex.: 18000,00" inputMode="decimal" style={input} />
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: t.textMuted, margin: '13px 0 6px' }}>Por que você precisa?</label>
              <textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Explique em poucas palavras" rows={3} style={{ ...input, resize: 'vertical' }} />
              <Btn onClick={submit} disabled={submitting || !requestedLimit} style={{ width: '100%', marginTop: 14, background: t.yellow, color: t.primaryHover }}>
                {submitting ? <><Spinner size={14} /> Enviando…</> : 'Enviar para análise'}
              </Btn>
              <div style={{ color: t.textLight, fontSize: 11, textAlign: 'center', marginTop: 9 }}>Resposta demonstrativa em até 2 dias úteis.</div>
            </div>

            <div style={{ background: '#fff', border: `1px solid ${t.border}`, borderRadius: 20, padding: 20 }}>
              <h3 style={{ fontSize: 15, marginBottom: 12 }}>Últimos pedidos</h3>
              {requests.length === 0 ? <p style={{ color: t.textMuted, fontSize: 12 }}>Nenhum pedido enviado ainda.</p> : requests.slice(0, 4).map(item => {
                const colors = item.status === 'approved' ? [t.successBg, t.success] : item.status === 'rejected' ? [t.dangerBg, t.danger] : [t.warningBg, t.warning]
                const labels = { approved: 'Aprovado', rejected: 'Não aprovado', pending_review: 'Em análise' }
                return <div key={item.external_id} style={{ borderTop: `1px solid ${t.border}`, padding: '12px 0', display: 'flex', justifyContent: 'space-between', gap: 10 }}><div><strong style={{ fontSize: 13 }}>{fmtBRL(item.requested_limit)}</strong><div style={{ color: t.textMuted, fontSize: 11, marginTop: 2 }}>{new Date(item.created_at).toLocaleDateString('pt-BR')}</div></div><span style={{ alignSelf: 'center', background: colors[0], color: colors[1], borderRadius: 999, padding: '5px 9px', fontSize: 10, fontWeight: 800 }}>{labels[item.status]}</span></div>
              })}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
