// Tela 4 — Verificação Contextual (Confirmação Fase 2)
// Exibida quando backend retorna awaiting_confirmation.
// Solicita finalidade em linguagem simples e respeitosa.
// A resposta é reavaliada pelo backend — não aceita automaticamente.

import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { confirmTransfer } from '../services/api'
import type { TransferInitiatedResponse, ConfirmTransferResponse } from '../types'
import {
  Card, CardHeader, Btn, ErrorBox, Spinner, inputStyle, clr,
  fmtBRL, StatusBadge,
} from './ui'

export default function ConfirmPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const result = location.state?.result as TransferInitiatedResponse | null
  const txnIdFromState = location.state?.txnId as string | undefined

  const txn = result?.transaction
  const txnId = txn?.external_id ?? txnIdFromState ?? ''

  const [purpose, setPurpose] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmResult, setConfirmResult] = useState<ConfirmTransferResponse | null>(null)

  if (!txnId) {
    return (
      <div style={{ maxWidth: 520, margin: '0 auto' }}>
        <Card>
          <ErrorBox message="Nenhuma transação encontrada. Volte ao início e realize uma transferência." />
          <div style={{ marginTop: 12 }}>
            <Btn onClick={() => navigate('/')}>← Voltar ao início</Btn>
          </div>
        </Card>
      </div>
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!purpose.trim()) {
      setError('Por favor, descreva a finalidade da transferência.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await confirmTransfer(txnId, purpose)
      setConfirmResult(res)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const msg = detail ?? (err as Error)?.message ?? 'Erro ao processar confirmação.'
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setLoading(false)
    }
  }

  // Exibe resultado da confirmação
  if (confirmResult) {
    const status = confirmResult.new_status
    const icon = status === 'released' ? '✅' : status === 'human_review_pending' ? '👤' : '⚠️'
    const color = status === 'released' ? '#16a34a' : status === 'human_review_pending' ? '#ea580c' : '#d97706'

    return (
      <div style={{ maxWidth: 540, margin: '0 auto' }}>
        <Card style={{ borderTop: `4px solid ${color}` }}>
          <div style={{ textAlign: 'center', padding: '20px 0 12px' }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>{icon}</div>
            <h2 style={{ margin: '0 0 6px', color, fontSize: 20 }}>{confirmResult.message}</h2>
            <p style={{ color: clr.textMuted, fontSize: 13, margin: '0 0 16px' }}>
              {confirmResult.reasoning}
            </p>
          </div>

          {confirmResult.coercion_detected && (
            <div style={{
              background: '#fff7ed', border: '1px solid #fed7aa',
              borderRadius: 8, padding: '10px 14px', marginBottom: 14,
              fontSize: 13, color: '#9a3412',
            }}>
              ⚠️ <strong>Indicador de coerção detectado.</strong> O sistema identificou possíveis sinais
              de pressão na resposta fornecida. A transação foi encaminhada para revisão humana como medida de proteção.
            </div>
          )}

          <div style={{ marginBottom: 14 }}>
            <StatusBadge status={status} />
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <Btn variant="secondary" onClick={() => navigate('/')}>← Início</Btn>
            {status === 'human_review_pending' && (
              <Btn variant="secondary" onClick={() => navigate('/human-review')}>
                👤 Ver revisão humana
              </Btn>
            )}
            <Btn variant="secondary" onClick={() => navigate('/audit')}>📋 Auditoria</Btn>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 540, margin: '0 auto' }}>
      <Card>
        <CardHeader
          title="Verificação adicional necessária"
          subtitle="Identificamos características incomuns nesta operação"
        />

        <div style={{
          background: '#fffbeb', border: '1px solid #fde68a',
          borderRadius: 8, padding: '12px 16px', marginBottom: 18,
        }}>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.7, color: '#92400e' }}>
            O sistema de segurança identificou algumas características incomuns nesta transferência.{' '}
            <strong>Isso não significa que a operação está sendo rejeitada</strong> — apenas precisamos
            entender melhor a sua finalidade para poder processá-la com segurança.
          </p>
        </div>

        {txn && (
          <div style={{
            background: clr.surfaceAlt, border: `1px solid ${clr.border}`,
            borderRadius: 8, padding: '12px 14px', marginBottom: 18,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 8 }}>
              Detalhes da transferência
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', fontSize: 13 }}>
              <span><span style={{ color: clr.textMuted }}>Valor:</span> <strong>{fmtBRL(txn.amount)}</strong></span>
              <span><span style={{ color: clr.textMuted }}>Status:</span> <StatusBadge status={txn.status} /></span>
              <span style={{ gridColumn: '1/-1', fontSize: 11, color: clr.textMuted, marginTop: 2 }}>
                ID: {txn.external_id.slice(0, 18)}…
              </span>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: clr.text }}>
                Qual é a finalidade desta transferência?
              </span>
              <span style={{ fontSize: 12, color: clr.textMuted, lineHeight: 1.5 }}>
                Descreva com suas palavras o motivo da transferência. Por exemplo: pagamento de fornecedor,
                compra de equipamento, envio para familiar, etc.
              </span>
              <textarea
                value={purpose}
                onChange={e => setPurpose(e.target.value)}
                style={{
                  ...inputStyle,
                  minHeight: 90,
                  resize: 'vertical',
                  lineHeight: 1.6,
                }}
                placeholder="Descreva a finalidade da transferência…"
                maxLength={1000}
                required
              />
              <span style={{ fontSize: 11, color: clr.textLight, textAlign: 'right' }}>
                {purpose.length}/1000 caracteres
              </span>
            </label>
          </div>

          <div style={{
            background: '#f0fdf4', border: '1px solid #bbf7d0',
            borderRadius: 6, padding: '8px 12px', marginBottom: 14,
            fontSize: 12, color: '#166534',
          }}>
            ℹ️ Sua resposta será analisada pelo sistema e <strong>não será aceita automaticamente</strong>.
            O contexto completo da operação é considerado na reavaliação.
          </div>

          {error && <div style={{ marginBottom: 12 }}><ErrorBox message={error} /></div>}

          <div style={{ display: 'flex', gap: 10 }}>
            <Btn variant="secondary" onClick={() => navigate('/')}>Cancelar</Btn>
            <Btn type="submit" disabled={loading || !purpose.trim()}>
              {loading
                ? <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Spinner size={14} color="#fff" /> Reavaliando…
                  </span>
                : 'Confirmar e reavaliar'}
            </Btn>
          </div>
        </form>
      </Card>
    </div>
  )
}
