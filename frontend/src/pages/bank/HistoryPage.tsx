import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { fetchClients, fetchClientStatement, getApiErrorMessage } from '../../services/api'
import type { ClientSummary, StatementEntryResponse } from '../../types'
import { t, fmtBRL, fmtDate, Card, Btn, Spinner, ErrorBox } from '../../components/ui'

function getStoredClientId(): string {
  try { return localStorage.getItem('bobia_client_id') ?? '' } catch { return '' }
}

const ENTRY_LABEL: Record<StatementEntryResponse['entry_type'], string> = {
  debit: 'Pix enviado', credit: 'Valor recebido', reserve: 'Valor reservado', release: 'Reserva liberada',
}
const STATUS_LABEL: Record<StatementEntryResponse['status'], string> = {
  posted: 'Concluído', pending: 'Em processamento', reversed: 'Estornado',
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const locState = location.state as { clientId?: string } | null
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [selectedId, setSelectedId] = useState(locState?.clientId ?? getStoredClientId())
  const [entries, setEntries] = useState<StatementEntryResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchClients().then(data => {
      setClients(data)
      if (!selectedId && data.length) setSelectedId(data[0].external_id)
    }).catch(err => setError(getApiErrorMessage(err, 'Não foi possível carregar as contas.')))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const loadStatement = useCallback(async () => {
    if (!selectedId) return
    setLoading(true)
    setError(null)
    try { setEntries(await fetchClientStatement(selectedId, 100)) }
    catch (err) { setError(getApiErrorMessage(err, 'Não foi possível carregar o extrato.')) }
    finally { setLoading(false) }
  }, [selectedId])

  useEffect(() => {
    if (!selectedId) return
    try { localStorage.setItem('bobia_client_id', selectedId) } catch { /* sem persistência */ }
    loadStatement()
  }, [selectedId, loadStatement])

  const client = clients.find(c => c.external_id === selectedId)
  return (
    <div style={{ maxWidth: 820, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="section-heading" style={{ marginBottom: 0 }}>
        <div><div className="eyebrow">MOVIMENTAÇÕES DA CONTA</div><h1>Extrato</h1><p>{client ? `Lançamentos de ${client.name}` : 'Acompanhe entradas, saídas e valores em processamento.'}</p></div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select value={selectedId} onChange={e => setSelectedId(e.target.value)} style={{ border: `1px solid ${t.borderStrong}`, borderRadius: 10, padding: '8px 11px', fontSize: 13, background: 'rgba(255,255,255,.88)', color: t.text, fontFamily: t.font }}>
            {clients.map(c => <option key={c.external_id} value={c.external_id}>{c.name}</option>)}
          </select>
          <Btn variant="ghost" small onClick={loadStatement} disabled={loading}>Atualizar</Btn>
          <Btn small onClick={() => navigate('/bank/transfer', { state: { clientId: selectedId } })}>Nova transferência</Btn>
        </div>
      </div>
      {error && <ErrorBox message={error} />}
      <Card className="statement-card" style={{ padding: 22 }}>
        {loading && <div className="center-loader"><Spinner size={28} /></div>}
        {!loading && entries.length === 0 && <div className="empty-state"><strong>Nenhuma movimentação encontrada</strong><span>As transferências concluídas aparecerão aqui automaticamente.</span><div style={{ marginTop: 14 }}><Btn onClick={() => navigate('/bank/transfer', { state: { clientId: selectedId } })}>Fazer um Pix</Btn></div></div>}
        {!loading && entries.length > 0 && <div>
          <div style={{ color: t.textMuted, fontSize: 12, marginBottom: 8 }}>{entries.length} lançamento{entries.length === 1 ? '' : 's'}</div>
          {entries.map((entry, index) => {
            const incoming = entry.entry_type === 'credit' || entry.entry_type === 'release'
            const color = entry.status === 'reversed' ? t.textMuted : incoming ? t.success : t.text
            return <div key={entry.id} className="statement-row" style={{ display: 'grid', gridTemplateColumns: '42px minmax(0,1fr) auto', gap: 13, alignItems: 'center', padding: '14px 4px', borderBottom: index < entries.length - 1 ? `1px solid ${t.border}` : 'none' }}>
              <div style={{ width: 40, height: 40, borderRadius: 13, display: 'grid', placeItems: 'center', background: incoming ? t.successBg : t.primaryLight, color: incoming ? t.success : t.primaryHover, fontSize: 18 }}>{incoming ? '↓' : '↑'}</div>
              <div style={{ minWidth: 0 }}><div style={{ fontSize: 14, color: t.text, fontWeight: 750 }}>{ENTRY_LABEL[entry.entry_type]}</div><div style={{ fontSize: 12, color: t.textMuted, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{entry.counterpart_name || entry.description}{entry.counterpart_bank ? ` · ${entry.counterpart_bank}` : ''}</div><div style={{ color: t.textLight, fontSize: 11, marginTop: 2 }}>{fmtDate(entry.posted_at)} · {STATUS_LABEL[entry.status]}</div></div>
              <div style={{ textAlign: 'right' }}><div style={{ fontSize: 14, color, fontWeight: 800 }}>{incoming ? '+' : '−'} {fmtBRL(entry.amount)}</div><div style={{ color: t.textLight, fontSize: 10, marginTop: 2 }}>Saldo {fmtBRL(entry.balance_after)}</div></div>
            </div>
          })}
        </div>}
      </Card>
    </div>
  )
}
