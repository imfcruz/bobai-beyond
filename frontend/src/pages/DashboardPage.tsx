// Tela 1 — Dashboard / Visão geral
// Exibe cliente selecionado, saldo simulado, histórico e modo de análise.

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchClients, fetchClientTransactions, fetchHealth } from '../services/api'
import type { ClientSummary, TransactionResponse, HealthResponse } from '../types'
import {
  Card, CardHeader, Btn, StatusBadge,
  fmtBRL, fmtDate, clr, tableStyle, thStyle, tdStyle, RISK_COLOR,
} from './ui'

const CLIENT_BALANCE: Record<string, string> = {
  'client-ana-costa': '42.350,00',
  'client-carlos-mendes': '198.720,00',
  'client-beatriz-santos': '12.890,50',
}

const CLIENT_LIMIT: Record<string, string> = {
  'client-ana-costa': '8.000,00',
  'client-carlos-mendes': '30.000,00',
  'client-beatriz-santos': '5.000,00',
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [history, setHistory] = useState<TransactionResponse[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)

  useEffect(() => {
    fetchClients().then(data => {
      setClients(data)
      if (data.length) setSelectedId(data[0].external_id)
    }).catch(() => {})
    fetchHealth().then(setHealth).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoadingHistory(true)
    fetchClientTransactions(selectedId, 10)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setLoadingHistory(false))
  }, [selectedId])

  const client = clients.find(c => c.external_id === selectedId)
  const mode = health?.llm_provider === 'mock' ? 'RULES_MODE' : 'AI_MODE'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 20, alignItems: 'start' }}>
      {/* Coluna esquerda — perfil */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Seletor de cliente */}
        <Card>
          <CardHeader title="Conta Simulada" subtitle="Dados 100% sintéticos" />
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Cliente
            </span>
            <select
              value={selectedId}
              onChange={e => setSelectedId(e.target.value)}
              style={{
                border: `1px solid ${clr.border}`, borderRadius: 6,
                padding: '7px 10px', fontSize: 13, background: '#fff',
                fontFamily: 'inherit',
              }}
            >
              {clients.map(c => (
                <option key={c.external_id} value={c.external_id}>{c.name}</option>
              ))}
            </select>
          </label>

          {client && (
            <>
              <div style={{
                background: '#f0f7ff', border: '1px solid #bfdbfe',
                borderRadius: 8, padding: '14px 16px', marginBottom: 14,
              }}>
                <div style={{ fontSize: 11, color: '#1e40af', fontWeight: 700, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                  Saldo disponível (simulado)
                </div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#1e40af' }}>
                  R$ {CLIENT_BALANCE[client.external_id] ?? '—'}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                <div style={{ background: clr.surfaceAlt, borderRadius: 6, padding: '8px 10px', border: `1px solid ${clr.border}` }}>
                  <div style={{ fontSize: 10, color: clr.textMuted, fontWeight: 700, textTransform: 'uppercase', marginBottom: 2 }}>Limite</div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>R$ {CLIENT_LIMIT[client.external_id] ?? '—'}</div>
                </div>
                <div style={{ background: clr.surfaceAlt, borderRadius: 6, padding: '8px 10px', border: `1px solid ${clr.border}` }}>
                  <div style={{ fontSize: 10, color: clr.textMuted, fontWeight: 700, textTransform: 'uppercase', marginBottom: 2 }}>Perfil</div>
                  <div style={{ fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>{client.risk_profile}</div>
                </div>
              </div>

              <Btn
                fullWidth
                onClick={() => navigate('/transfer', { state: { clientId: selectedId } })}
              >
                ➕ Nova transferência
              </Btn>
            </>
          )}
        </Card>

        {/* Modo de análise */}
        <Card>
          <div style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 10 }}>
            Modo de análise
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: mode === 'AI_MODE' ? '#f0f7ff' : '#f0fdf4',
            border: `1px solid ${mode === 'AI_MODE' ? '#bfdbfe' : '#bbf7d0'}`,
            borderRadius: 8, padding: '10px 12px',
          }}>
            <span style={{ fontSize: 20 }}>{mode === 'AI_MODE' ? '🤖' : '⚙️'}</span>
            <div>
              <div style={{ fontWeight: 700, fontSize: 13, color: mode === 'AI_MODE' ? '#1e40af' : '#166534' }}>
                {mode}
              </div>
              <div style={{ fontSize: 11, color: clr.textMuted, marginTop: 1 }}>
                {mode === 'AI_MODE'
                  ? `Modelo: ${health?.llm_provider ?? '—'}`
                  : 'Regras determinísticas (sem LLM)'}
              </div>
            </div>
          </div>

          {mode === 'RULES_MODE' && (
            <p style={{ margin: '10px 0 0', fontSize: 11, color: clr.textMuted, lineHeight: 1.5 }}>
              ℹ️ RULES_MODE utiliza heurísticas determinísticas — não é IA generativa.
              Configure <code>LLM_PROVIDER</code> para ativar AI_MODE.
            </p>
          )}
        </Card>

        {/* Ações rápidas */}
        <Card>
          <div style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 10 }}>
            Demonstração
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Btn variant="secondary" fullWidth onClick={() => navigate('/scenarios')}>
              📚 Cenários pré-configurados
            </Btn>
            <Btn variant="secondary" fullWidth onClick={() => navigate('/audit')}>
              📋 Painel de auditoria
            </Btn>
            <Btn variant="secondary" fullWidth onClick={() => navigate('/human-review')}>
              👤 Revisão humana
            </Btn>
          </div>
        </Card>
      </div>

      {/* Coluna direita — histórico */}
      <Card>
        <CardHeader
          title="Histórico de transferências"
          subtitle={client ? `Últimas operações de ${client.name}` : 'Selecione um cliente'}
        />

        {loadingHistory && (
          <div style={{ textAlign: 'center', padding: 40, color: clr.textMuted }}>
            ⏳ Carregando…
          </div>
        )}

        {!loadingHistory && history.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: clr.textLight, fontSize: 14 }}>
            Nenhuma transação encontrada para este cliente.
          </div>
        )}

        {!loadingHistory && history.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {['Data', 'Beneficiário', 'Valor', 'Risco', 'Status'].map(h => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map(t => (
                  <tr key={t.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/result/${t.external_id}`)}
                  >
                    <td style={tdStyle}><span style={{ fontSize: 11, color: clr.textMuted }}>{fmtDate(t.created_at)}</span></td>
                    <td style={tdStyle}>{t.beneficiary_name ?? `#${t.beneficiary_id}`}</td>
                    <td style={tdStyle}><strong>{fmtBRL(t.amount)}</strong></td>
                    <td style={tdStyle}>
                      <span style={{ color: RISK_COLOR[t.risk_level] ?? '#6b7280', fontWeight: 700, fontSize: 12 }}>
                        {(t.risk_score * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td style={tdStyle}><StatusBadge status={t.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
