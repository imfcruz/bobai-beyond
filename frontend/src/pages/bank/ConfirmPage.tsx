// ─── Nexus Bank — Transfer Confirmation Page (Client View) ───────────────
// Shown when backend returns awaiting_confirmation.
// Asks for transfer purpose in natural language. No technical data shown.

import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { confirmTransfer } from '../../services/api'
import type { TransferInitiatedResponse, ConfirmTransferResponse } from '../../types'
import { t, Card, Btn, Spinner, ErrorBox, inputStyle, fmtBRL } from '../../components/ui'

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
          <ErrorBox message="Nenhuma transferência encontrada. Volte ao início." />
          <div style={{ marginTop: 12 }}>
            <Btn onClick={() => navigate('/bank')}>← Voltar ao início</Btn>
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

  // ── Post-confirmation result ──────────────────────────────────────────────

  if (confirmResult) {
    const status = confirmResult.new_status
    const released = ['released', 'human_approved', 'approved'].includes(status)
    const humanReview = ['human_review_pending', 'escalated_to_human'].includes(status)
    const rejected = ['rejected', 'human_rejected', 'blocked'].includes(status)

    const statusConfig = released
      ? { bg: t.successBg, border: t.successBorder, color: t.success, icon: '✓', title: 'Transferência realizada', body: 'Sua transferência foi verificada e processada com sucesso.' }
      : humanReview
      ? { bg: t.orangeBg, border: t.orangeBorder, color: t.orange, icon: '·', title: 'Verificação adicional', body: 'Sua transferência foi encaminhada para análise adicional. Você será notificado em breve.' }
      : rejected
      ? { bg: t.dangerBg, border: t.dangerBorder, color: t.danger, icon: '✕', title: 'Transferência não autorizada', body: 'Não foi possível processar esta transferência. Por favor, entre em contato com o suporte se necessário.' }
      : { bg: t.warningBg, border: t.warningBorder, color: '#d97706', icon: '!', title: 'Verificando', body: confirmResult.message }

    return (
      <div style={{ maxWidth: 480, margin: '0 auto' }}>
        <Card style={{ overflow: 'hidden', padding: 0 }}>
          <div style={{ height: 4, background: statusConfig.color }} />
          <div style={{ padding: '32px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 16 }}>
            <div style={{
              width: 56, height: 56, borderRadius: '50%',
              background: statusConfig.bg, border: `2px solid ${statusConfig.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 22, fontWeight: 800, color: statusConfig.color,
            }}>
              {statusConfig.icon}
            </div>
            <div>
              <h2 style={{ fontSize: 20, fontWeight: 800, color: t.text, margin: 0 }}>{statusConfig.title}</h2>
              <p style={{ fontSize: 14, color: t.textMuted, margin: '8px 0 0', lineHeight: 1.6, maxWidth: 340 }}>
                {statusConfig.body}
              </p>
            </div>

            {confirmResult.coercion_detected && (
              <div style={{
                background: t.warningBg, border: `1px solid ${t.warningBorder}`,
                borderRadius: 8, padding: '10px 14px',
                fontSize: 12, color: t.warning, lineHeight: 1.6,
                textAlign: 'left', width: '100%',
              }}>
                <strong>Atenção:</strong> Detectamos possíveis sinais de pressão ou coerção na sua resposta.
                Para sua proteção, a transferência foi encaminhada para análise especializada.
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <Btn variant="secondary" onClick={() => navigate('/bank')}>Voltar ao início</Btn>
              {released && <Btn onClick={() => navigate('/bank/transfer')}>Nova transferência</Btn>}
            </div>
          </div>
        </Card>
      </div>
    )
  }

  // ── Confirmation form ─────────────────────────────────────────────────────

  return (
    <div style={{ maxWidth: 480, margin: '0 auto' }}>
      <Card style={{ padding: '28px 24px' }}>
        {/* Icon + title */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{
            width: 52, height: 52, borderRadius: '50%',
            background: t.primaryLight,
            border: `2px solid ${t.accent}30`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, margin: '0 auto 12px',
            color: t.accent,
          }}>
            B
          </div>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: t.text, margin: 0 }}>
            Confirmação de segurança
          </h2>
          <p style={{ fontSize: 13, color: t.textMuted, margin: '8px 0 0', lineHeight: 1.6 }}>
            Precisamos confirmar algumas informações para proteger sua transferência.
          </p>
        </div>

        {/* Transfer summary */}
        {txn && (
          <div style={{
            background: t.surface2, border: `1px solid ${t.border}`,
            borderRadius: 10, padding: '14px 16px', marginBottom: 20,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 2 }}>Transferência para</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>
                {txn.beneficiary_name ?? 'Destinatário'}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: t.text }}>{fmtBRL(txn.amount)}</div>
            </div>
          </div>
        )}

        {/* Purpose form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: t.text }}>
                Qual é a finalidade desta transferência?
              </span>
              <span style={{ fontSize: 12, color: t.textMuted, lineHeight: 1.5 }}>
                Descreva o motivo da transferência. Por exemplo: pagamento de fornecedor,
                compra de equipamento, envio para familiar, etc.
              </span>
              <textarea
                value={purpose}
                onChange={e => setPurpose(e.target.value)}
                style={{
                  ...inputStyle,
                  minHeight: 88,
                  resize: 'vertical',
                  lineHeight: 1.6,
                }}
                placeholder="Descreva a finalidade da transferência…"
                maxLength={1000}
                required
                autoFocus
              />
              <span style={{ fontSize: 11, color: t.textPlaceholder, textAlign: 'right' }}>
                {purpose.length}/1000
              </span>
            </label>
          </div>

          <div style={{
            background: t.primaryLight, border: `1px solid ${t.accent}30`,
            borderRadius: 8, padding: '10px 12px', marginBottom: 16,
            fontSize: 12, color: t.accent, lineHeight: 1.5,
          }}>
            Sua resposta será analisada pelo sistema de segurança. A transferência não será liberada automaticamente.
          </div>

          {error && <div style={{ marginBottom: 12 }}><ErrorBox message={error} /></div>}

          <div style={{ display: 'flex', gap: 10 }}>
            <Btn variant="secondary" onClick={() => navigate('/bank')} disabled={loading}>
              Cancelar
            </Btn>
            <Btn type="submit" disabled={loading || !purpose.trim()} style={{ flex: 1 }}>
              {loading
                ? <><Spinner size={14} color="#fff" /> Verificando…</>
                : 'Enviar confirmação'
              }
            </Btn>
          </div>
        </form>
      </Card>
    </div>
  )
}
