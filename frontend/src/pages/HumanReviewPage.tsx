// Tela 8 — Revisão Humana
// Área de demonstração para operador simular revisão humana.
// Deixa explícito que é operador fictício, não integração real.

import { useState, useEffect, useCallback } from 'react'
import { fetchTransactions, getApiErrorMessage, submitHumanReview } from '../services/api'
import type { TransactionResponse, HumanReviewResponse } from '../types'
import {
  Card, CardHeader, Btn, ErrorBox, Spinner, StatusBadge, RiskBadge,
  clr, fmtBRL, fmtDate, inputStyle, riskColor, employeeExplanation,
} from './ui'

const REVIEWABLE_STATUSES = ['human_review_pending', 'escalated_to_human']

export default function HumanReviewPage() {
  const [transactions, setTransactions] = useState<TransactionResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<TransactionResponse | null>(null)
  const [reviewerId, setReviewerId] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reviewResult, setReviewResult] = useState<HumanReviewResponse | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const all = await fetchTransactions(100)
      setTransactions(all.filter(t => REVIEWABLE_STATUSES.includes(t.status)))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  function handleSelect(txn: TransactionResponse) {
    setSelected(txn)
    setError(null)
    setReviewResult(null)
    setNotes('')
  }

  async function handleReview(action: 'approve' | 'reject') {
    if (!selected) return
    if (!reviewerId.trim()) {
      setError('Informe o identificador do operador.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const result = await submitHumanReview(
        selected.external_id,
        action,
        reviewerId.trim(),
        notes || undefined,
      )
      setReviewResult(result)
      // Atualiza lista
      await load()
      setSelected(null)
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Não foi possível registrar a revisão.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: 20, alignItems: 'start' }}>
      {/* Lista de casos */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Card>
          <CardHeader title="Casos pendentes" subtitle="Transferências aguardando revisão humana" />

          {/* Aviso de operador fictício */}
          <div style={{
            background: '#fef9c3', border: '1px solid #fde047',
            borderRadius: 6, padding: '8px 12px', marginBottom: 14,
            fontSize: 12, color: '#713f12', lineHeight: 1.5,
          }}>
            <strong>Operador fictício de demonstração.</strong> Esta área simula a interface de revisão humana.
            Não representa integração com funcionários reais.
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 12, color: clr.textMuted }}>
              {loading ? 'Carregando…' : `${transactions.length} caso(s) pendente(s)`}
            </span>
            <Btn variant="ghost" small onClick={load} disabled={loading}>
              {loading ? <Spinner size={11} /> : '↻'}
            </Btn>
          </div>

          {!loading && transactions.length === 0 && (
            <div style={{ textAlign: 'center', padding: '30px 0', color: clr.textLight, fontSize: 13 }}>
              Nenhum caso aguardando revisão.
            </div>
          )}

          {transactions.map(txn => (
            <button
              key={txn.id}
              onClick={() => handleSelect(txn)}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                border: selected?.id === txn.id ? `2px solid #ea580c` : `1px solid ${clr.border}`,
                borderRadius: 8, padding: '10px 12px',
                background: selected?.id === txn.id ? '#fff7ed' : '#fff',
                cursor: 'pointer', marginBottom: 6, fontFamily: 'inherit',
                transition: 'border-color 0.1s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {txn.client_name ?? `Cliente #${txn.client_id}`}
                  </div>
                  <div style={{ fontSize: 11, color: clr.textMuted }}>
                    → {txn.beneficiary_name ?? `Beneficiário #${txn.beneficiary_id}`}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 800, fontSize: 14, color: riskColor(txn.risk_score) }}>
                    {fmtBRL(txn.amount)}
                  </div>
                  <div style={{ fontSize: 11, color: riskColor(txn.risk_score) }}>
                    {(txn.risk_score * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center' }}>
                <StatusBadge status={txn.status} />
                <span style={{ fontSize: 10, color: clr.textLight }}>{fmtDate(txn.created_at)}</span>
              </div>
              {txn.purpose && (
                <div style={{ marginTop: 4, fontSize: 11, color: clr.textMuted, fontStyle: 'italic' }}>
                  "{txn.purpose.slice(0, 60)}{txn.purpose.length > 60 ? '…' : ''}"
                </div>
              )}
            </button>
          ))}
        </Card>
      </div>

      {/* Painel de revisão */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {reviewResult && (
          <Card style={{ borderTop: `4px solid ${reviewResult.action === 'approve' ? '#16a34a' : '#dc2626'}` }}>
            <div style={{ textAlign: 'center', padding: '12px 0' }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>
                {reviewResult.action === 'approve' ? '✓' : '×'}
              </div>
              <h3 style={{ margin: '0 0 6px', color: reviewResult.action === 'approve' ? '#16a34a' : '#dc2626' }}>
                {reviewResult.message}
              </h3>
              <p style={{ color: clr.textMuted, fontSize: 13, margin: 0 }}>
                {reviewResult.reasoning}
              </p>
              <div style={{ marginTop: 12 }}>
                <Btn variant="secondary" small onClick={() => setReviewResult(null)}>
                  Nova revisão
                </Btn>
              </div>
            </div>
          </Card>
        )}

        {selected && !reviewResult ? (
          <Card>
            <CardHeader
              title="Revisar transferência"
              subtitle={`ID: ${selected.external_id.slice(0, 18)}…`}
            />

            {/* Detalhes da transação */}
            <div style={{
              background: clr.surfaceAlt, border: `1px solid ${clr.border}`,
              borderRadius: 8, padding: '14px 16px', marginBottom: 16,
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px 20px', fontSize: 13 }}>
                <div>
                  <span style={{ color: clr.textMuted, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3 }}>Cliente</span>
                  <div style={{ fontWeight: 600 }}>{selected.client_name ?? `#${selected.client_id}`}</div>
                </div>
                <div>
                  <span style={{ color: clr.textMuted, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3 }}>Beneficiário</span>
                  <div style={{ fontWeight: 600 }}>{selected.beneficiary_name ?? `#${selected.beneficiary_id}`}</div>
                </div>
                <div>
                  <span style={{ color: clr.textMuted, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3 }}>Valor</span>
                  <div style={{ fontWeight: 700, fontSize: 16 }}>{fmtBRL(selected.amount)}</div>
                </div>
                <div>
                  <span style={{ color: clr.textMuted, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3 }}>Risco</span>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 2 }}>
                    <RiskBadge level={selected.risk_level} />
                    <span style={{ color: riskColor(selected.risk_score), fontWeight: 700 }}>
                      {(selected.risk_score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                <div>
                  <span style={{ color: clr.textMuted, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3 }}>Status atual</span>
                  <div style={{ marginTop: 2 }}><StatusBadge status={selected.status} /></div>
                </div>
                <div>
                  <span style={{ color: clr.textMuted, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3 }}>Data</span>
                  <div style={{ fontSize: 12 }}>{fmtDate(selected.created_at)}</div>
                </div>
                {selected.purpose && (
                  <div style={{ gridColumn: '1/-1' }}>
                    <span style={{ color: clr.textMuted, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3 }}>Finalidade declarada</span>
                    <div style={{ fontStyle: 'italic', color: '#374151' }}>"{selected.purpose}"</div>
                  </div>
                )}
                {selected.decision_reasoning && (
                  <div style={{ gridColumn: '1/-1' }}>
                    <span style={{ color: clr.textMuted, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3 }}>Justificativa do sistema</span>
                    <div style={{ fontSize: 12, color: '#374151', lineHeight: 1.5 }}>{employeeExplanation(selected.decision_reasoning)}</div>
                  </div>
                )}
              </div>
            </div>

            {/* Indicadores de risco */}
            {(selected.is_new_recipient || selected.recent_limit_change || !selected.device_recognized) && (
              <div style={{
                background: '#fff7ed', border: '1px solid #fed7aa',
                borderRadius: 8, padding: '10px 14px', marginBottom: 16,
              }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#9a3412', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.3 }}>
                  Indicadores de risco identificados
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {selected.is_new_recipient && (
                    <span style={{ background: '#fee2e2', color: '#b91c1c', borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                      Beneficiário novo
                    </span>
                  )}
                  {selected.recent_limit_change && (
                    <span style={{ background: '#fee2e2', color: '#b91c1c', borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                      Limite recentemente alterado
                    </span>
                  )}
                  {!selected.device_recognized && (
                    <span style={{ background: '#fee2e2', color: '#b91c1c', borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                      Dispositivo não reconhecido
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Formulário de revisão */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                  Identificador do operador *
                </span>
                <input
                  type="text"
                  value={reviewerId}
                  onChange={e => setReviewerId(e.target.value)}
                  style={inputStyle}
                  placeholder="ex: operador_demo_001"
                  maxLength={64}
                />
                <span style={{ fontSize: 11, color: clr.textMuted }}>
                  Não use identificadores de sistema (ai, bot, auto, etc.)
                </span>
              </label>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: clr.textMuted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                  Justificativa <span style={{ fontWeight: 400 }}>(opcional)</span>
                </span>
                <textarea
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  style={{ ...inputStyle, minHeight: 80, resize: 'vertical' }}
                  placeholder="Descreva o motivo da decisão…"
                  maxLength={1000}
                />
              </label>
            </div>

            {error && <div style={{ marginBottom: 12 }}><ErrorBox message={error} /></div>}

            <div style={{ display: 'flex', gap: 10 }}>
              <Btn
                onClick={() => handleReview('approve')}
                disabled={submitting || !reviewerId.trim()}
                style={{ background: '#16a34a', border: 'none' } as React.CSSProperties}
              >
                {submitting ? <Spinner size={14} color="#fff" /> : 'Aprovar transferência'}
              </Btn>
              <Btn
                variant="danger"
                onClick={() => handleReview('reject')}
                disabled={submitting || !reviewerId.trim()}
              >
                {submitting ? <Spinner size={14} color="#fff" /> : 'Rejeitar transferência'}
              </Btn>
            </div>
          </Card>
        ) : !reviewResult ? (
          <Card>
            <div style={{ textAlign: 'center', padding: '60px 0', color: clr.textLight }}>
              <div style={{ fontSize: 40, marginBottom: 12, fontWeight: 800 }}>—</div>
              <div style={{ fontSize: 14, marginBottom: 6 }}>Selecione um caso na lista ao lado</div>
              <div style={{ fontSize: 12 }}>Apenas transferências em revisão humana podem ser analisadas aqui.</div>
            </div>
          </Card>
        ) : null}
      </div>
    </div>
  )
}
