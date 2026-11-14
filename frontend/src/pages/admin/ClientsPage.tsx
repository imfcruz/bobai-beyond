import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchClient, fetchClients, fetchCreditLimitRequests, fetchTransactions, getApiErrorMessage } from '../../services/api'
import type { ClientResponse, ClientSummary, CreditLimitRequestResponse, TransactionResponse } from '../../types'
import { Btn, Card, ErrorBox, RiskBadge, Spinner, StatusBadge, fmtBRL, fmtDate, t } from '../../components/ui'

export default function ClientsPage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState<ClientResponse | null>(null)
  const [transactions, setTransactions] = useState<TransactionResponse[]>([])
  const [requests, setRequests] = useState<CreditLimitRequestResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchClients(), fetchTransactions(200), fetchCreditLimitRequests()])
      .then(([clientRows, txRows, requestRows]) => {
        setClients(clientRows); setTransactions(txRows); setRequests(requestRows)
        setSelectedId(current => current || clientRows[0]?.external_id || '')
      })
      .catch(err => setError(getApiErrorMessage(err, 'Não foi possível carregar a gestão de clientes.')))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    fetchClient(selectedId).then(setDetail).catch(err => setError(getApiErrorMessage(err, 'Não foi possível carregar o cliente.')))
  }, [selectedId])

  const clientTransactions = useMemo(() => transactions.filter(row => row.client_id === detail?.id), [transactions, detail])
  const pendingTransactions = clientTransactions.filter(row => ['human_review_pending', 'escalated_to_human'].includes(row.status))
  const clientRequests = requests.filter(row => row.client_id === detail?.id)
  const pendingRequests = clientRequests.filter(row => row.status === 'pending_review')

  if (loading) return <div className="center-loader"><Spinner size={30} /></div>
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
    <div className="section-heading" style={{ marginBottom: 0 }}>
      <div><div className="eyebrow">GESTÃO E REVISÃO</div><h1>Clientes</h1><p>Consulte contas, movimentações sinalizadas e pedidos que dependem de decisão humana.</p></div>
      <select value={selectedId} onChange={event => setSelectedId(event.target.value)} style={{ minWidth: 240, border: `1px solid ${t.borderStrong}`, borderRadius: 11, padding: '10px 12px', background: 'rgba(255,255,255,.9)', color: t.text }}>
        {clients.map(client => <option key={client.external_id} value={client.external_id}>{client.name}</option>)}
      </select>
    </div>
    {error && <ErrorBox message={error} />}
    {detail && <>
      <div className="client-admin-summary">
        <Card><span className="summary-label">Saldo disponível</span><strong>{fmtBRL(detail.available_balance)}</strong><small>Ag. {detail.agency} · Conta {detail.account_number}</small></Card>
        <Card><span className="summary-label">Limite Pix</span><strong>{fmtBRL(detail.transfer_limit)}</strong><small>Limite diário configurado</small></Card>
        <Card><span className="summary-label">Revisões pendentes</span><strong>{pendingTransactions.length}</strong><small>Transferências aguardando decisão</small></Card>
        <Card><span className="summary-label">Pedidos de cartão</span><strong>{pendingRequests.length}</strong><small>Aumentos de limite pendentes</small></Card>
      </div>

      <div className="admin-client-columns">
        <Card>
          <div className="client-panel-heading"><div><h2>Movimentações do cliente</h2><p>Operações mais recentes e seus estados.</p></div>{pendingTransactions.length > 0 && <Btn small onClick={() => navigate('/admin/review')}>Revisar pendências</Btn>}</div>
          {clientTransactions.length === 0 ? <div className="empty-state"><strong>Sem movimentações</strong><span>Este cliente ainda não realizou transferências.</span></div> : clientTransactions.slice(0, 8).map((row, index) => <div key={row.id} className="admin-client-row" style={{ borderBottom: index < Math.min(clientTransactions.length, 8) - 1 ? `1px solid ${t.border}` : 'none' }}>
            <div><strong>{row.beneficiary_name || 'Destinatário'}</strong><span>{fmtDate(row.created_at)}</span></div><div><b>{fmtBRL(row.amount)}</b><RiskBadge level={row.risk_level} /><StatusBadge status={row.status} /></div>
          </div>)}
        </Card>
        <Card>
          <div className="client-panel-heading"><div><h2>Pedidos de limite</h2><p>Solicitações ligadas ao cartão do cliente.</p></div>{pendingRequests.length > 0 && <Btn small onClick={() => navigate('/admin/limit-requests')}>Analisar pedidos</Btn>}</div>
          {clientRequests.length === 0 ? <div className="empty-state"><strong>Nenhum pedido</strong><span>Não há solicitações de limite para este cliente.</span></div> : clientRequests.slice(0, 6).map((row, index) => <div key={row.id} className="admin-client-row" style={{ borderBottom: index < Math.min(clientRequests.length, 6) - 1 ? `1px solid ${t.border}` : 'none' }}>
            <div><strong>{fmtBRL(row.current_limit)} → {fmtBRL(row.requested_limit)}</strong><span>{row.reason || 'Finalidade não informada'}</span></div><span className={`request-status ${row.status}`}>{row.status === 'pending_review' ? 'Aguardando análise' : row.status === 'approved' ? 'Aprovado' : 'Recusado'}</span>
          </div>)}
        </Card>
      </div>
    </>}
  </div>
}
