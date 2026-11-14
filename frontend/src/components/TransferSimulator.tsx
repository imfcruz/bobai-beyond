// Componente de simulação de transferência
// Permite selecionar cliente, beneficiário, valor e disparar o pipeline multiagente

import { useState, useEffect } from 'react'
import {
  fetchClients,
  fetchBeneficiaries,
  initiateTransfer,
} from '../services/api'
import type {
  ClientSummary,
  BeneficiaryResponse,
  TransferInitiatedResponse,
  AgentResultParsed,
} from '../types'

const RISK_COLOR: Record<string, string> = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
}

const STATUS_LABEL: Record<string, string> = {
  released: '✅ Liberada',
  under_verification: '⚠️ Em verificação',
  escalated_to_human: '🔴 Escalada para humano',
  rejected: '❌ Rejeitada',
  pending: '⏳ Pendente',
}

const ACTION_LABEL: Record<string, string> = {
  approve: 'Aprovar',
  request_confirmation: 'Solicitar confirmação',
  escalate_to_human: 'Escalar para humano',
  block: 'Bloquear',
}

function parseAgentResult(raw: string | null): AgentResultParsed | null {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function parseFlags(raw: string | null): string[] {
  if (!raw) return []
  try {
    return JSON.parse(raw)
  } catch {
    return []
  }
}

function RiskBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score < 0.3 ? '#22c55e' : score < 0.6 ? '#f59e0b' : score < 0.85 ? '#f97316' : '#ef4444'
  return (
    <div style={{ margin: '8px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: '#57606a' }}>Score de risco</span>
        <span style={{ fontWeight: 700, color }}>{pct}%</span>
      </div>
      <div style={{ background: '#e5e7eb', borderRadius: 4, height: 8 }}>
        <div
          style={{
            width: `${pct}%`,
            height: 8,
            borderRadius: 4,
            background: color,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
    </div>
  )
}

function AgentCard({ label, result }: { label: string; result: AgentResultParsed | null }) {
  if (!result) return null
  const pct = Math.round(result.risk_score * 100)
  const color = RISK_COLOR[result.risk_score < 0.3 ? 'low' : result.risk_score < 0.6 ? 'medium' : result.risk_score < 0.85 ? 'high' : 'critical']
  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: 8,
      padding: '12px 14px',
      background: '#f7f8fa',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{label}</span>
        <span style={{ fontWeight: 700, color, fontSize: 14 }}>{pct}%</span>
      </div>
      {result.flags.length > 0 && (
        <div style={{ marginBottom: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {result.flags.map(f => (
            <span key={f} style={{
              background: '#fee2e2', color: '#b91c1c',
              borderRadius: 4, padding: '1px 6px', fontSize: 11,
            }}>{f}</span>
          ))}
        </div>
      )}
      <p style={{ margin: 0, fontSize: 12, color: '#374151', lineHeight: 1.5 }}>{result.reasoning}</p>
    </div>
  )
}

export function TransferSimulator({ onTransferDone }: { onTransferDone?: () => void }) {
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [beneficiaries, setBeneficiaries] = useState<BeneficiaryResponse[]>([])
  const [selectedClient, setSelectedClient] = useState('')
  const [selectedBen, setSelectedBen] = useState('')
  const [amount, setAmount] = useState('1500.00')
  const [purpose, setPurpose] = useState('')
  const [deviceRecognized, setDeviceRecognized] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<TransferInitiatedResponse | null>(null)

  useEffect(() => {
    fetchClients().then(setClients).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedClient) {
      setBeneficiaries([])
      setSelectedBen('')
      return
    }
    fetchBeneficiaries(selectedClient)
      .then(data => {
        setBeneficiaries(data)
        setSelectedBen(data[0]?.external_id ?? '')
      })
      .catch(() => {})
  }, [selectedClient])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedClient || !selectedBen) {
      setError('Selecione cliente e beneficiário.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await initiateTransfer({
        client_external_id: selectedClient,
        beneficiary_external_id: selectedBen,
        amount,
        purpose: purpose || undefined,
        device_recognized: deviceRecognized,
      })
      setResult(res)
      onTransferDone?.()
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Erro desconhecido.'
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setLoading(false)
    }
  }

  const gw = result?.gateway
  const analysis = result?.analysis
  const txn = result?.transaction

  return (
    <div>
      {/* ── Formulário ── */}
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#57606a' }}>CLIENTE</span>
            <select
              value={selectedClient}
              onChange={e => setSelectedClient(e.target.value)}
              style={inputStyle}
              required
            >
              <option value="">— selecione —</option>
              {clients.map(c => (
                <option key={c.external_id} value={c.external_id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#57606a' }}>BENEFICIÁRIO</span>
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
                  {b.name} {!b.is_known ? '(novo)' : ''}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#57606a' }}>VALOR (BRL)</span>
            <input
              type="text"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              style={inputStyle}
              placeholder="ex: 1500.00"
              required
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#57606a' }}>FINALIDADE</span>
            <input
              type="text"
              value={purpose}
              onChange={e => setPurpose(e.target.value)}
              style={inputStyle}
              placeholder="Descrição da transferência"
            />
          </label>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={deviceRecognized}
            onChange={e => setDeviceRecognized(e.target.checked)}
          />
          Dispositivo reconhecido
        </label>

        {error && (
          <div style={{
            background: '#fee2e2', color: '#b91c1c', borderRadius: 6,
            padding: '8px 12px', marginBottom: 10, fontSize: 13,
          }}>
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            background: loading ? '#9ca3af' : '#3b82d4',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            padding: '10px 24px',
            fontWeight: 700,
            fontSize: 14,
            cursor: loading ? 'not-allowed' : 'pointer',
            width: '100%',
          }}
        >
          {loading ? '⏳ Analisando...' : '▶ Executar pipeline de análise'}
        </button>
      </form>

      {/* ── Resultado ── */}
      {result && txn && gw && analysis && (
        <div style={{ marginTop: 20 }}>
          <div style={{
            borderRadius: 8,
            border: `2px solid ${RISK_COLOR[gw.risk_level]}`,
            padding: '14px 16px',
            background: '#fff',
            marginBottom: 16,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
                  {result.message}
                </div>
                <div style={{ fontSize: 12, color: '#57606a' }}>
                  Transação: <code>{txn.external_id}</code>
                </div>
              </div>
              <span style={{
                background: RISK_COLOR[gw.risk_level],
                color: '#fff',
                borderRadius: 4,
                padding: '2px 10px',
                fontWeight: 700,
                fontSize: 12,
                textTransform: 'uppercase',
              }}>
                {gw.risk_level}
              </span>
            </div>

            <RiskBar score={gw.risk_score} />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 8 }}>
              <InfoCell label="Status" value={STATUS_LABEL[txn.status] ?? txn.status} />
              <InfoCell label="Ação" value={ACTION_LABEL[gw.final_action] ?? gw.final_action} />
              <InfoCell label="Autorizado" value={gw.authorized ? '✅ Sim' : '❌ Não'} />
              {gw.requires_confirmation && <InfoCell label="Confirmação" value="⚠️ Necessária" />}
              {gw.requires_human_review && <InfoCell label="Humano" value="👤 Necessário" />}
            </div>

            {gw.flags.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#57606a' }}>FLAGS DETECTADAS:</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                  {gw.flags.map(f => (
                    <span key={f} style={{
                      background: '#fee2e2', color: '#b91c1c',
                      borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 600,
                    }}>{f}</span>
                  ))}
                </div>
              </div>
            )}

            <div style={{ marginTop: 10, fontSize: 12, color: '#374151', borderTop: '1px solid #e5e7eb', paddingTop: 8 }}>
              {gw.gateway_reasoning}
            </div>
          </div>

          {/* ── Resultados por agente ── */}
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8, color: '#57606a' }}>
            RESULTADOS POR AGENTE
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
            <AgentCard label="🕵️ Agente de Fraude" result={parseAgentResult(analysis.fraud_agent_result)} />
            <AgentCard label="🔍 Agente de Inconsistência" result={parseAgentResult(analysis.inconsistency_agent_result)} />
            <AgentCard label="📊 Agente Comportamental" result={parseAgentResult(analysis.behavioral_agent_result)} />
            <AgentCard label="⚖️ Agente de Risco" result={parseAgentResult(analysis.risk_agent_result)} />
          </div>

          {parseFlags(analysis.flags).length > 0 && (
            <div style={{ fontSize: 11, color: '#57606a', marginTop: 4 }}>
              Flags consolidados: {parseFlags(analysis.flags).join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      background: '#f7f8fa', borderRadius: 6, padding: '6px 10px',
      border: '1px solid #e5e7eb',
    }}>
      <div style={{ fontSize: 10, color: '#57606a', fontWeight: 600, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600 }}>{value}</div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  border: '1px solid #d1d5db',
  borderRadius: 6,
  padding: '8px 10px',
  fontSize: 13,
  background: '#fff',
  width: '100%',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
}
