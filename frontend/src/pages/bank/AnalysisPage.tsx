// ─── Nexus Bank — Security Analysis Page (Client View) ───────────────────
// Shows contextual, user-friendly security processing states.
// NEVER exposes: risk scores, agent names, heuristics, model names, flags.
// After analysis: routes to result or contextual confirmation page.

import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import type { TransferInitiatedResponse } from '../../types'
import { t, Spinner, Btn, fmtBRL, Card } from '../../components/ui'

// Processing steps shown visually (no false progress bars)
const PROCESSING_STEPS = [
  { label: 'Iniciando transferência', duration: 400 },
  { label: 'Verificando segurança', duration: 600 },
  { label: 'Processando operação', duration: 500 },
]

type VisualState =
  | 'processing'
  | 'awaiting_confirmation'
  | 'human_review'
  | 'released'
  | 'rejected'
  | 'pipeline_failed'

function getVisualState(result: TransferInitiatedResponse): VisualState {
  if (result.pipeline_failed) return 'pipeline_failed'
  const status = result.transaction.status
  if (['released', 'human_approved', 'approved'].includes(status)) return 'released'
  if (['awaiting_confirmation', 'under_verification', 'requires_verification'].includes(status)) return 'awaiting_confirmation'
  if (['human_review_pending', 'escalated_to_human'].includes(status)) return 'human_review'
  if (['rejected', 'human_rejected', 'blocked'].includes(status)) return 'rejected'
  return 'pipeline_failed'
}

// ── Processing animation ───────────────────────────────────────────────────

function ProcessingView({ onDone }: { onDone: () => void }) {
  const [stepIdx, setStepIdx] = useState(0)

  useEffect(() => {
    let total = 0
    PROCESSING_STEPS.forEach((s, i) => {
      total += s.duration
      setTimeout(() => {
        setStepIdx(i + 1)
        if (i === PROCESSING_STEPS.length - 1) {
          setTimeout(onDone, 200)
        }
      }, total)
    })
  }, [onDone])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '48px 24px', gap: 32 }}>
      <Spinner size={48} color={t.accent} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '100%', maxWidth: 300 }}>
        {PROCESSING_STEPS.map((s, i) => {
          const done = i < stepIdx
          const active = i === stepIdx
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                background: done ? t.success : active ? t.accent + '22' : t.surface2,
                border: `1.5px solid ${done ? t.success : active ? t.accent : t.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11,
              }}>
                {done ? <span style={{ color: '#fff', fontSize: 10 }}>✓</span>
                  : active ? <Spinner size={10} color={t.accent} />
                  : null}
              </div>
              <span style={{ fontSize: 13, color: done ? t.success : active ? t.text : t.textLight, fontWeight: active || done ? 600 : 400 }}>
                {s.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Released state ─────────────────────────────────────────────────────────

function ReleasedView({ result }: { result: TransferInitiatedResponse }) {
  const navigate = useNavigate()
  const { transaction: txn } = result

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '32px 24px', gap: 16 }}>
      <div style={{
        width: 64, height: 64, borderRadius: '50%',
        background: t.successBg, border: `2px solid ${t.successBorder}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 28, color: t.success,
      }}>
        ✓
      </div>
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 800, color: t.text, margin: 0 }}>Transferência realizada</h2>
        <p style={{ fontSize: 14, color: t.textMuted, margin: '6px 0 0', lineHeight: 1.6 }}>
          Sua transferência de <strong>{fmtBRL(txn.amount)}</strong> foi processada com sucesso.
        </p>
      </div>
      <div style={{
        background: t.surface2, border: `1px solid ${t.border}`,
        borderRadius: 10, padding: '14px 20px', width: '100%', textAlign: 'left',
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
          <div>
            <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3, marginBottom: 2 }}>Para</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>{txn.beneficiary_name ?? '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3, marginBottom: 2 }}>Valor</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>{fmtBRL(txn.amount)}</div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3, marginBottom: 2 }}>Status</div>
            <div style={{ fontSize: 13, color: t.success, fontWeight: 600 }}>Concluída</div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3, marginBottom: 2 }}>Identificador</div>
            <div style={{ fontSize: 11, color: t.textLight, fontFamily: 'monospace' }}>
              {txn.external_id.slice(0, 16)}…
            </div>
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
        <Btn variant="secondary" onClick={() => navigate('/bank')}>Início</Btn>
        <Btn onClick={() => navigate('/bank/transfer')}>Nova transferência</Btn>
      </div>
    </div>
  )
}

// ── Awaiting confirmation ──────────────────────────────────────────────────

function AwaitingConfirmationView({ result }: { result: TransferInitiatedResponse }) {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '32px 24px', gap: 16 }}>
      <div style={{
        width: 64, height: 64, borderRadius: '50%',
        background: t.warningBg, border: `2px solid ${t.warningBorder}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 22, color: '#d97706', fontWeight: 800,
      }}>
        !
      </div>
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 800, color: t.text, margin: 0 }}>Confirmação necessária</h2>
        <p style={{ fontSize: 14, color: t.textMuted, margin: '8px 0 0', lineHeight: 1.7, maxWidth: 360 }}>
          Para proteger sua transferência, precisamos confirmar algumas informações antes de processá-la.
        </p>
      </div>
      <div style={{
        background: t.surface2, border: `1px solid ${t.border}`,
        borderRadius: 10, padding: '14px 20px', width: '100%', textAlign: 'left',
      }}>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 4, fontWeight: 600 }}>Transferência de</div>
        <div style={{ fontSize: 20, fontWeight: 800, color: t.text }}>{fmtBRL(result.transaction.amount)}</div>
        <div style={{ fontSize: 13, color: t.textMuted, marginTop: 4 }}>
          Para {result.transaction.beneficiary_name ?? 'destinatário'}
        </div>
      </div>
      <Btn fullWidth onClick={() => navigate('/bank/confirm', { state: { result } })}>
        Confirmar informações →
      </Btn>
      <Btn variant="secondary" fullWidth onClick={() => navigate('/bank')}>
        Cancelar e voltar
      </Btn>
    </div>
  )
}

// ── Human review ───────────────────────────────────────────────────────────

function HumanReviewView({ result }: { result: TransferInitiatedResponse }) {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '32px 24px', gap: 16 }}>
      <div style={{
        width: 64, height: 64, borderRadius: '50%',
        background: t.orangeBg, border: `2px solid ${t.orangeBorder}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 22,
      }}>
        ·
      </div>
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 800, color: t.text, margin: 0 }}>Verificação adicional em andamento</h2>
        <p style={{ fontSize: 14, color: t.textMuted, margin: '8px 0 0', lineHeight: 1.7, maxWidth: 380 }}>
          Por segurança, esta transferência precisa de uma verificação adicional antes de ser concluída.
          Você receberá uma confirmação em breve.
        </p>
      </div>
      <div style={{
        background: t.surface2, border: `1px solid ${t.border}`,
        borderRadius: 10, padding: '14px 20px', width: '100%', textAlign: 'left',
      }}>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 4, fontWeight: 600 }}>Transferência de</div>
        <div style={{ fontSize: 20, fontWeight: 800, color: t.text }}>{fmtBRL(result.transaction.amount)}</div>
        <div style={{ fontSize: 13, color: t.textMuted, marginTop: 4 }}>
          Para {result.transaction.beneficiary_name ?? 'destinatário'} · Aguardando análise
        </div>
      </div>
      <div style={{
        background: '#fff3cd', border: '1px solid #ffc107',
        borderRadius: 8, padding: '10px 14px',
        fontSize: 12, color: '#664d03',
        lineHeight: 1.6, width: '100%', textAlign: 'left',
      }}>
        Nenhuma ação adicional necessária por enquanto. A análise ocorrerá em instantes.
        Em uma aplicação real, você seria notificado pelo aplicativo ou SMS.
      </div>
      <Btn variant="secondary" onClick={() => navigate('/bank')}>Voltar ao início</Btn>
    </div>
  )
}

// ── Rejected ───────────────────────────────────────────────────────────────

function RejectedView({ result }: { result: TransferInitiatedResponse }) {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '32px 24px', gap: 16 }}>
      <div style={{
        width: 64, height: 64, borderRadius: '50%',
        background: t.dangerBg, border: `2px solid ${t.dangerBorder}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 22, color: t.danger, fontWeight: 800,
      }}>
        ✕
      </div>
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 800, color: t.text, margin: 0 }}>Transferência não autorizada</h2>
        <p style={{ fontSize: 14, color: t.textMuted, margin: '8px 0 0', lineHeight: 1.7, maxWidth: 380 }}>
          Esta transferência não pôde ser processada. O sistema de segurança identificou características
          que impedem sua realização neste momento.
        </p>
      </div>
      <div style={{
        background: t.surface2, border: `1px solid ${t.border}`,
        borderRadius: 10, padding: '14px 20px', width: '100%', textAlign: 'left',
      }}>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 4, fontWeight: 600 }}>Transferência de</div>
        <div style={{ fontSize: 18, fontWeight: 800, color: t.text }}>{fmtBRL(result.transaction.amount)}</div>
        <div style={{ fontSize: 13, color: t.danger, marginTop: 4, fontWeight: 600 }}>Não autorizada</div>
      </div>
      <div style={{
        background: t.dangerBg, border: `1px solid ${t.dangerBorder}`,
        borderRadius: 8, padding: '10px 14px',
        fontSize: 12, color: t.danger,
        lineHeight: 1.6, width: '100%', textAlign: 'left',
      }}>
        Em caso de dúvidas, entre em contato com o suporte. Esta é uma demonstração acadêmica.
      </div>
      <div style={{ display: 'flex', gap: 10 }}>
        <Btn variant="secondary" onClick={() => navigate('/bank')}>Voltar ao início</Btn>
        <Btn onClick={() => navigate('/bank/transfer')}>Tentar novamente</Btn>
      </div>
    </div>
  )
}

// ── Pipeline failed ────────────────────────────────────────────────────────

function PipelineFailedView({ result }: { result: TransferInitiatedResponse }) {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '32px 24px', gap: 16 }}>
      <div style={{
        width: 64, height: 64, borderRadius: '50%',
        background: t.warningBg, border: `2px solid ${t.warningBorder}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 24,
      }}>
        !
      </div>
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 800, color: t.text, margin: 0 }}>Erro temporário</h2>
        <p style={{ fontSize: 14, color: t.textMuted, margin: '8px 0 0', lineHeight: 1.7, maxWidth: 380 }}>
          Ocorreu um problema temporário ao processar sua transferência.
          A operação não foi concluída e nenhum valor foi movimentado.
          Tente novamente em alguns momentos.
        </p>
      </div>
      <div style={{
        background: t.surface2, border: `1px solid ${t.border}`,
        borderRadius: 10, padding: '12px 16px', width: '100%', textAlign: 'left',
        fontSize: 12, color: t.textMuted,
      }}>
        Referência: {result.transaction.external_id.slice(0, 18)}…
      </div>
      <div style={{ display: 'flex', gap: 10 }}>
        <Btn variant="secondary" onClick={() => navigate('/bank')}>Voltar ao início</Btn>
        <Btn onClick={() => navigate('/bank/transfer')}>Tentar novamente</Btn>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export default function AnalysisPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const result = location.state?.result as TransferInitiatedResponse | null

  const [showResult, setShowResult] = useState(false)

  useEffect(() => {
    if (!result) {
      navigate('/bank', { replace: true })
    }
  }, [result, navigate])

  if (!result) return null

  const visualState = getVisualState(result)

  return (
    <div style={{ maxWidth: 520, margin: '0 auto' }}>
      <Card style={{ overflow: 'hidden', padding: 0 }}>
        {/* Top accent bar */}
        <div style={{
          height: 4,
          background: visualState === 'released' ? t.success
            : visualState === 'rejected' ? t.danger
            : visualState === 'human_review' ? t.orange
            : t.accent,
        }} />

        {!showResult ? (
          <ProcessingView onDone={() => setShowResult(true)} />
        ) : (
          <div className="animate-fadein">
            {visualState === 'released' && <ReleasedView result={result} />}
            {visualState === 'awaiting_confirmation' && <AwaitingConfirmationView result={result} />}
            {visualState === 'human_review' && <HumanReviewView result={result} />}
            {visualState === 'rejected' && <RejectedView result={result} />}
            {visualState === 'pipeline_failed' && <PipelineFailedView result={result} />}
          </div>
        )}
      </Card>
    </div>
  )
}
