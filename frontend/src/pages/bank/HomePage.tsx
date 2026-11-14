// ─── Nexus Bank — Client Home Page ───────────────────────────────────────
// Modern banking homepage: greeting, balance, quick actions, recent history.
// No technical info exposed to the client (no risk scores, agent names, etc.)

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchClients, fetchClientTransactions, fetchClient } from '../../services/api'
import type { ClientSummary, TransactionResponse, ClientResponse } from '../../types'
import {
  t, fmtBRL, fmtDate, Spinner, AmountDisplay,
  Card, Btn,
} from '../../components/ui'
import NavIcon, { type NavIconName } from '../../components/NavIcon'

// Persistence of selected client
function getStoredClientId(): string {
  try { return localStorage.getItem('bobia_client_id') ?? '' } catch { return '' }
}
function storeClientId(id: string) {
  try { localStorage.setItem('bobia_client_id', id) } catch { /* noop */ }
}

function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Bom dia'
  if (h < 18) return 'Boa tarde'
  return 'Boa noite'
}

function formatClientName(name: string): string {
  return name.split(' ')[0] // first name only
}

// Map readable transaction status for client view
function clientStatusLabel(status: string): string {
  const map: Record<string, string> = {
    released: 'Concluída',
    human_approved: 'Concluída',
    approved: 'Concluída',
    awaiting_confirmation: 'Verificando',
    under_verification: 'Verificando',
    requires_verification: 'Verificando',
    human_review_pending: 'Em análise',
    escalated_to_human: 'Em análise',
    pending: 'Processando',
    rejected: 'Não realizada',
    human_rejected: 'Não realizada',
    blocked: 'Não autorizada',
  }
  return map[status] ?? 'Processando'
}

function clientStatusColor(status: string): string {
  const map: Record<string, string> = {
    released: t.success,
    human_approved: t.success,
    approved: t.success,
    awaiting_confirmation: '#d97706',
    under_verification: '#d97706',
    requires_verification: '#d97706',
    human_review_pending: t.orange,
    escalated_to_human: t.orange,
    pending: t.textLight,
    rejected: t.danger,
    human_rejected: t.danger,
    blocked: t.danger,
  }
  return map[status] ?? t.textLight
}

// Quick action button
function QuickAction({ icon, label, onClick }: { icon: NavIconName; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        background: t.surface,
        border: `1px solid ${t.border}`,
        borderRadius: 10,
        padding: '16px 12px',
        cursor: 'pointer',
        fontFamily: t.font,
        transition: 'box-shadow 0.15s, border-color 0.15s',
        flex: 1,
        minWidth: 80,
      }}
      onMouseEnter={e => {
        ;(e.currentTarget as HTMLButtonElement).style.borderColor = t.accent
        ;(e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 0 2px ${t.accent}22`
      }}
      onMouseLeave={e => {
        ;(e.currentTarget as HTMLButtonElement).style.borderColor = t.border
        ;(e.currentTarget as HTMLButtonElement).style.boxShadow = 'none'
      }}
    >
      <div style={{
        width: 40, height: 40, borderRadius: 10,
        background: t.primaryLight,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 18,
      }}>
        <NavIcon name={icon} size={20} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, color: t.textMuted }}>{label}</span>
    </button>
  )
}

export default function BankHomePage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [selectedId, setSelectedId] = useState<string>(getStoredClientId())
  const [clientDetail, setClientDetail] = useState<ClientResponse | null>(null)
  const [history, setHistory] = useState<TransactionResponse[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [showBalance, setShowBalance] = useState(true)
  const [switching, setSwitching] = useState(false)

  // Load clients list
  useEffect(() => {
    fetchClients().then(data => {
      setClients(data)
      if (!selectedId && data.length) {
        const first = data[0].external_id
        setSelectedId(first)
        storeClientId(first)
      }
    }).catch(() => {})
  }, []) // eslint-disable-line

  // Load client detail + history when selected changes
  const loadClientData = useCallback((id: string) => {
    if (!id) return
    storeClientId(id)
    setLoadingHistory(true)
    setClientDetail(null)
    Promise.all([
      fetchClient(id).catch(() => null),
      fetchClientTransactions(id, 8).catch(() => [] as TransactionResponse[]),
    ]).then(([detail, txns]) => {
      setClientDetail(detail)
      setHistory(txns)
    }).finally(() => setLoadingHistory(false))
  }, [])

  useEffect(() => {
    if (selectedId) loadClientData(selectedId)
  }, [selectedId, loadClientData])

  const clientSummary = clients.find(c => c.external_id === selectedId)
  const balanceDisplay = clientDetail
    ? (showBalance ? fmtBRL(clientDetail.available_balance) : 'R$ ••••••')
    : '—'

  // Pending transactions
  const pendingTxns = history.filter(t => ['human_review_pending', 'escalated_to_human', 'awaiting_confirmation', 'under_verification'].includes(t.status))

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Account selector (demo context) ── */}
      <div style={{
        background: t.surface,
        border: `1px solid ${t.border}`,
        borderRadius: 10,
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        boxShadow: t.shadowSm,
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: t.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, whiteSpace: 'nowrap' }}>
          Conta
        </span>
        <select
          value={selectedId}
          onChange={e => {
            setSwitching(true)
            setSelectedId(e.target.value)
            setTimeout(() => setSwitching(false), 600)
          }}
          style={{
            border: `1px solid ${t.borderStrong}`,
            borderRadius: 6,
            padding: '6px 10px',
            fontSize: 14,
            background: t.surface,
            color: t.text,
            fontFamily: t.font,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {clients.map(c => (
            <option key={c.external_id} value={c.external_id}>{c.name}</option>
          ))}
        </select>
        <span style={{ fontSize: 11, color: t.textPlaceholder, marginLeft: 'auto' }}>
          Dados sintéticos · demonstração
        </span>
      </div>

      {switching ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spinner size={28} /></div>
      ) : (
        <>
          {/* ── Balance card ── */}
          <div style={{
            background: `linear-gradient(140deg, ${t.primary} 0%, ${t.primaryHover} 100%)`,
            borderRadius: 24,
            padding: '28px 28px 24px',
            color: '#fff',
            position: 'relative',
            overflow: 'hidden',
            boxShadow: t.shadowMd,
          }}>
            {/* Decorative circle */}
            <div style={{
              position: 'absolute', right: -20, top: -30,
              width: 180, height: 180, borderRadius: '50%',
              background: 'rgba(255,255,255,0.05)',
            }} />
            <div style={{
              position: 'absolute', right: 40, top: 60,
              width: 100, height: 100, borderRadius: '50%',
              background: 'rgba(255,255,255,0.04)',
            }} />

            <div style={{ position: 'relative' }}>
              {/* Greeting */}
              <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.70)', marginBottom: 4 }}>
                {getGreeting()}, {clientSummary ? formatClientName(clientSummary.name) : '—'}
              </div>

              {/* Balance */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>
                    Saldo disponível
                  </div>
                  <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: '-0.5px', fontVariantNumeric: 'tabular-nums' }}>
                    {balanceDisplay}
                  </div>
                </div>
                <button
                  onClick={() => setShowBalance(b => !b)}
                  style={{
                    background: 'rgba(255,255,255,0.12)',
                    border: 'none',
                    borderRadius: 6,
                    padding: '5px 10px',
                    color: 'rgba(255,255,255,0.8)',
                    cursor: 'pointer',
                    fontSize: 11,
                    fontFamily: t.font,
                    marginTop: 16,
                  }}
                >
                  {showBalance ? 'Ocultar' : 'Mostrar'}
                </button>
              </div>

              {/* Account info */}
              {clientDetail && (
                <div style={{ display: 'flex', gap: 20, marginTop: 16, paddingTop: 16, borderTop: '1px solid rgba(255,255,255,0.15)' }}>
                  <div>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2 }}>
                      Limite de transferência
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.85)' }}>
                      {fmtBRL(clientDetail.transfer_limit)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2 }}>
                      Conta
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.85)' }}>
                      Ag. {clientDetail.agency} · {clientDetail.account_number}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── Quick actions ── */}
          <Card style={{ padding: '18px 20px' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: t.textMuted, marginBottom: 14, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              O que deseja fazer?
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(105px, 1fr))', gap: 10 }}>
              <QuickAction
                icon="pix"
                label="Fazer Pix"
                onClick={() => navigate('/bank/transfer', { state: { clientId: selectedId } })}
              />
              <QuickAction
                icon="card"
                label="Cartões"
                onClick={() => navigate('/bank/cards')}
              />
              <QuickAction
                icon="statement"
                label="Extrato"
                onClick={() => navigate('/bank/history', { state: { clientId: selectedId } })}
              />
              <QuickAction
                icon="contacts"
                label="Contatos"
                onClick={() => navigate('/bank/contacts', { state: { clientId: selectedId } })}
              />
            </div>
          </Card>

          {/* ── Pending operations ── */}
          {pendingTxns.length > 0 && (
            <Card style={{ borderLeft: `3px solid #d97706` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#b45309', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Operações aguardando ação
              </div>
              {pendingTxns.map(txn => (
                <div
                  key={txn.id}
                  onClick={() => navigate('/bank/analysis', { state: { txnId: txn.external_id } })}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 12px',
                    background: '#fffbeb',
                    border: '1px solid #fde68a',
                    borderRadius: 8,
                    cursor: 'pointer',
                    marginBottom: 8,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: t.text }}>
                      Pix {txn.funding_source === 'credit' ? 'no crédito' : 'no débito'} para {txn.beneficiary_name ?? 'destinatário'}
                    </div>
                    <div style={{ fontSize: 12, color: '#b45309' }}>
                      {clientStatusLabel(txn.status)} · {fmtDate(txn.created_at)}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <AmountDisplay amount={txn.amount} size="sm" color={t.text} />
                  </div>
                </div>
              ))}
            </Card>
          )}

          {/* ── Recent transactions ── */}
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: t.text }}>Movimentações recentes</div>
                <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>Últimas 8 transferências realizadas</div>
              </div>
              <Btn
                variant="secondary"
                small
                onClick={() => navigate('/bank/transfer', { state: { clientId: selectedId } })}
              >
                + Nova transferência
              </Btn>
            </div>

            {loadingHistory && (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
                <Spinner size={24} />
              </div>
            )}

            {!loadingHistory && history.length === 0 && (
              <div style={{ textAlign: 'center', padding: '32px 0', color: t.textLight }}>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8, opacity: 0.45 }}><NavIcon name="pix" size={30} /></div>
                <div style={{ fontSize: 14, fontWeight: 600, color: t.textMuted }}>Nenhuma movimentação ainda</div>
                <div style={{ fontSize: 13, marginTop: 4 }}>Realize sua primeira transferência</div>
                <div style={{ marginTop: 16 }}>
                  <Btn onClick={() => navigate('/bank/transfer', { state: { clientId: selectedId } })}>
                    Transferir agora
                  </Btn>
                </div>
              </div>
            )}

            {!loadingHistory && history.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {history.map((txn, i) => (
                  <div
                    key={txn.id}
                    onClick={() => navigate('/bank/result', { state: { txnId: txn.external_id } })}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 14,
                      padding: '13px 4px',
                      borderBottom: i < history.length - 1 ? `1px solid ${t.border}` : 'none',
                      cursor: 'pointer',
                      transition: 'background 0.1s',
                      borderRadius: 6,
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = t.surface2 }}
                    onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
                  >
                    {/* Icon */}
                    <div style={{
                      width: 38, height: 38, borderRadius: '50%',
                      background: clientStatusColor(txn.status) + '18',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                      fontSize: 15, color: clientStatusColor(txn.status),
                    }}>
                      <NavIcon name="pix" size={17} />
                    </div>

                    {/* Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: t.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        Para {txn.beneficiary_name ?? 'Destinatário'}
                      </div>
                      <div style={{ fontSize: 12, color: t.textMuted, marginTop: 1 }}>
                        {fmtDate(txn.created_at)}
                      </div>
                    </div>

                    {/* Amount + Status */}
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>
                        − {fmtBRL(txn.amount)}
                      </div>
                      <div style={{ fontSize: 11, color: clientStatusColor(txn.status), marginTop: 2, fontWeight: 600 }}>
                        {clientStatusLabel(txn.status)}
                      </div>
                    </div>
                  </div>
                ))}

                <div style={{ marginTop: 12, textAlign: 'center' }}>
                  <Btn variant="ghost" small onClick={() => navigate('/bank/history', { state: { clientId: selectedId } })}>
                    Ver extrato completo
                  </Btn>
                </div>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
