// Tela 2 — Nova Transferência
// Formulário com cliente, beneficiário, valor e finalidade.
// Após envio, navega para /analysis com o resultado.

import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { fetchClients, fetchBeneficiaries, initiateTransfer } from '../services/api'
import type { ClientSummary, BeneficiaryResponse } from '../types'
import {
  Card, CardHeader, Btn, ErrorBox, inputStyle, clr, fmtBRL,
} from './ui'

interface LocationState {
  clientId?: string
  beneficiaryId?: string
  amount?: string
  purpose?: string
  device?: boolean
}

export default function TransferPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as LocationState | null

  const [clients, setClients] = useState<ClientSummary[]>([])
  const [beneficiaries, setBeneficiaries] = useState<BeneficiaryResponse[]>([])
  const [selectedClient, setSelectedClient] = useState(state?.clientId ?? '')
  const [selectedBen, setSelectedBen] = useState(state?.beneficiaryId ?? '')
  const [amount, setAmount] = useState(state?.amount ?? '1500.00')
  const [purpose, setPurpose] = useState(state?.purpose ?? '')
  const [deviceRecognized, setDeviceRecognized] = useState(state?.device ?? true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchClients().then(data => {
      setClients(data)
      if (!selectedClient && data.length) setSelectedClient(data[0].external_id)
    }).catch(() => {})
  }, []) // eslint-disable-line

  useEffect(() => {
    if (!selectedClient) {
      setBeneficiaries([])
      setSelectedBen('')
      return
    }
    fetchBeneficiaries(selectedClient)
      .then(data => {
        setBeneficiaries(data)
        if (!state?.beneficiaryId) setSelectedBen(data[0]?.external_id ?? '')
      })
      .catch(() => {})
  }, [selectedClient]) // eslint-disable-line

  const selectedBenObj = beneficiaries.find(b => b.external_id === selectedBen)
  const selectedClientObj = clients.find(c => c.external_id === selectedClient)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedClient || !selectedBen) {
      setError('Selecione cliente e beneficiário.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const result = await initiateTransfer({
        client_external_id: selectedClient,
        beneficiary_external_id: selectedBen,
        amount,
        purpose: purpose || undefined,
        device_recognized: deviceRecognized,
      })
      // Navega para análise com resultado completo
      navigate('/analysis', { state: { result } })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const msg = detail ?? (err as Error)?.message ?? 'Erro desconhecido.'
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setLoading(false)
    }
  }

  const amtNum = parseFloat(amount.replace(',', '.'))

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <div style={{ marginBottom: 16 }}>
        <button
          onClick={() => navigate('/')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: clr.textMuted, fontSize: 13, padding: 0 }}
        >
          ← Voltar ao painel
        </button>
      </div>

      <Card>
        <CardHeader
          title="Nova Transferência"
          subtitle="Simulação acadêmica — nenhum dinheiro real é movimentado"
        />

        <div style={{
          background: '#fffbeb', border: '1px solid #fde68a',
          borderRadius: 6, padding: '8px 12px', marginBottom: 16, fontSize: 12, color: '#92400e',
        }}>
          ⚠️ Demonstração acadêmica. Os dados são 100% sintéticos. Não representa o Banco do Brasil.
        </div>

        <form onSubmit={handleSubmit}>
          {/* Linha 1: cliente */}
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                Cliente
              </span>
              <select
                value={selectedClient}
                onChange={e => setSelectedClient(e.target.value)}
                style={inputStyle}
                required
              >
                <option value="">— selecione —</option>
                {clients.map(c => (
                  <option key={c.external_id} value={c.external_id}>{c.name}</option>
                ))}
              </select>
            </label>
          </div>

          {/* Linha 2: beneficiário */}
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                Beneficiário
              </span>
              <select
                value={selectedBen}
                onChange={e => setSelectedBen(e.target.value)}
                style={inputStyle}
                required
                disabled={!selectedClient}
              >
                <option value="">— selecione —</option>
                {beneficiaries.map(b => (
                  <option key={b.external_id} value={b.external_id}>
                    {b.name} — {b.bank_name} {!b.is_known ? '(novo)' : '✓'}
                  </option>
                ))}
              </select>
            </label>
            {selectedBenObj && (
              <div style={{ marginTop: 6, fontSize: 11, color: clr.textMuted, display: 'flex', gap: 12 }}>
                <span>Conta: <code>{selectedBenObj.account_hint}</code></span>
                <span>Transferências anteriores: {selectedBenObj.transfer_count}</span>
                {!selectedBenObj.is_known && (
                  <span style={{ color: '#d97706', fontWeight: 700 }}>⚠ Beneficiário novo</span>
                )}
              </div>
            )}
          </div>

          {/* Linha 3: valor + finalidade */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                Valor (BRL)
              </span>
              <input
                type="text"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                style={inputStyle}
                placeholder="1500.00"
                required
              />
              {!isNaN(amtNum) && amtNum > 0 && (
                <span style={{ fontSize: 11, color: clr.accent }}>{fmtBRL(amtNum)}</span>
              )}
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                Finalidade <span style={{ fontWeight: 400 }}>(opcional)</span>
              </span>
              <input
                type="text"
                value={purpose}
                onChange={e => setPurpose(e.target.value)}
                style={inputStyle}
                placeholder="ex: pagamento de serviço"
                maxLength={500}
              />
            </label>
          </div>

          {/* Dispositivo */}
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18, fontSize: 13, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={deviceRecognized}
              onChange={e => setDeviceRecognized(e.target.checked)}
              style={{ width: 14, height: 14 }}
            />
            <span>Dispositivo reconhecido</span>
            {!deviceRecognized && (
              <span style={{ color: '#d97706', fontSize: 11, fontWeight: 600 }}>
                (eleva o risco)
              </span>
            )}
          </label>

          {/* Resumo da operação */}
          {selectedClientObj && selectedBenObj && !isNaN(amtNum) && amtNum > 0 && (
            <div style={{
              background: clr.surfaceAlt, border: `1px solid ${clr.border}`,
              borderRadius: 8, padding: '12px 14px', marginBottom: 16,
            }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                Resumo da operação
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', fontSize: 13 }}>
                <span><span style={{ color: clr.textMuted }}>De:</span> {selectedClientObj.name}</span>
                <span><span style={{ color: clr.textMuted }}>Para:</span> {selectedBenObj.name}</span>
                <span><span style={{ color: clr.textMuted }}>Valor:</span> <strong>{fmtBRL(amtNum)}</strong></span>
                <span><span style={{ color: clr.textMuted }}>Banco:</span> {selectedBenObj.bank_name}</span>
                {purpose && <span style={{ gridColumn: '1/-1' }}><span style={{ color: clr.textMuted }}>Finalidade:</span> {purpose}</span>}
              </div>
            </div>
          )}

          {error && <div style={{ marginBottom: 12 }}><ErrorBox message={error} /></div>}

          <Btn type="submit" disabled={loading} fullWidth>
            {loading ? '⏳ Executando análise…' : '▶ Analisar e enviar'}
          </Btn>
        </form>
      </Card>
    </div>
  )
}
