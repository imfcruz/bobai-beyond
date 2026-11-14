// ─── Nexus Bank — Transfer Flow (Multi-step) ─────────────────────────────
// Steps: Recipient → Amount → Review → (Processing) → Result
// No technical data exposed to the client.

import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  fetchClients, fetchBeneficiaries, fetchClientCards, fetchClientLimits,
  getApiErrorMessage, initiateTransfer, requestTransferLimitChange,
} from '../../services/api'
import type {
  ClientSummary, BeneficiaryResponse, CreditCardResponse, TransferInitiatedResponse,
  LimitInfoResponse,
} from '../../types'
import {
  t, fmtBRL, StepIndicator, Card, Btn, Spinner, ErrorBox, inputStyle, AmountDisplay,
} from '../../components/ui'

interface LocationState {
  clientId?: string
  beneficiaryId?: string
  step?: string
}

function getStoredClientId(): string {
  try { return localStorage.getItem('bobia_client_id') ?? '' } catch { return '' }
}

type Step = 0 | 1 | 2 | 3

const STEPS = ['Destinatário', 'Valor', 'Revisão', 'Confirmação']

// ── Step 0: Select Recipient ───────────────────────────────────────────────

function StepRecipient({
  clients, selectedClientId, onClientChange,
  beneficiaries, selectedBenId, onBenChange,
  onNext,
}: {
  clients: ClientSummary[]
  selectedClientId: string
  onClientChange: (id: string) => void
  beneficiaries: BeneficiaryResponse[]
  selectedBenId: string
  onBenChange: (id: string) => void
  onNext: () => void
}) {
  const selectedBen = beneficiaries.find(b => b.external_id === selectedBenId)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Account selector */}
      <div>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: t.textMuted }}>Sua conta</span>
          <select
            value={selectedClientId}
            onChange={e => onClientChange(e.target.value)}
            style={{ ...inputStyle, cursor: 'pointer' }}
          >
            <option value="">— Selecione a conta —</option>
            {clients.map(c => (
              <option key={c.external_id} value={c.external_id}>{c.name}</option>
            ))}
          </select>
        </label>
      </div>

      {/* Beneficiary list */}
      {selectedClientId && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: t.textMuted, marginBottom: 10 }}>
            Para quem deseja transferir?
          </div>
          {beneficiaries.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 24, color: t.textLight, fontSize: 13 }}>
              Nenhum destinatário cadastrado.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {beneficiaries.map(ben => {
                const selected = ben.external_id === selectedBenId
                return (
                  <button
                    key={ben.external_id}
                    onClick={() => onBenChange(ben.external_id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 14,
                      padding: '14px 16px',
                      background: selected ? t.primaryLight : t.surface,
                      border: `1.5px solid ${selected ? t.accent : t.border}`,
                      borderRadius: 10,
                      cursor: 'pointer',
                      fontFamily: t.font,
                      textAlign: 'left',
                      transition: 'border-color 0.15s, background 0.15s',
                      width: '100%',
                    }}
                  >
                    {/* Avatar */}
                    <div style={{
                      width: 40, height: 40, borderRadius: '50%',
                      background: selected ? t.accent : t.border,
                      color: selected ? '#fff' : t.textMuted,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 15, fontWeight: 700, flexShrink: 0,
                    }}>
                      {ben.name.charAt(0).toUpperCase()}
                    </div>

                    {/* Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>
                        {ben.name}
                        {!ben.is_known && (
                          <span style={{ marginLeft: 6, fontSize: 10, background: '#fde68a', color: '#92400e', borderRadius: 3, padding: '1px 5px', fontWeight: 600 }}>
                            NOVO
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>
                        {ben.bank_name} · Conta {ben.account_hint}
                      </div>
                      {ben.transfer_count > 0 && (
                        <div style={{ fontSize: 11, color: t.textLight, marginTop: 1 }}>
                          {ben.transfer_count} transferência{ben.transfer_count > 1 ? 's' : ''} anterior{ben.transfer_count > 1 ? 'es' : ''}
                        </div>
                      )}
                    </div>

                    {/* Check */}
                    {selected && (
                      <div style={{ color: t.accent, fontSize: 18, flexShrink: 0 }}>✓</div>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Preview card when selected */}
      {selectedBen && (
        <div style={{
          background: t.primaryLight,
          border: `1px solid ${t.accent}40`,
          borderRadius: 10,
          padding: '14px 16px',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: t.accent, color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, fontWeight: 700, flexShrink: 0,
          }}>
            {selectedBen.name.charAt(0)}
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: t.text }}>{selectedBen.name}</div>
            <div style={{ fontSize: 12, color: t.textMuted }}>{selectedBen.bank_name}</div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Btn disabled={!selectedClientId || !selectedBenId} onClick={onNext}>
          Continuar
        </Btn>
      </div>
    </div>
  )
}

// ── Step 1: Enter Amount ───────────────────────────────────────────────────

function StepAmount({
  amount, setAmount,
  purpose, setPurpose,
  deviceRecognized, setDeviceRecognized,
  fundingSource, setFundingSource, card,
  limitInfo, clientId, onLimitUpdated,
  onBack, onNext,
}: {
  amount: string
  setAmount: (v: string) => void
  purpose: string
  setPurpose: (v: string) => void
  deviceRecognized: boolean
  setDeviceRecognized: (v: boolean) => void
  fundingSource: 'debit' | 'credit'
  setFundingSource: (v: 'debit' | 'credit') => void
  card?: CreditCardResponse
  limitInfo: LimitInfoResponse | null
  clientId: string
  onLimitUpdated: () => Promise<void>
  onBack: () => void
  onNext: () => void
}) {
  const [amountError, setAmountError] = useState('')
  const [showLimitEditor, setShowLimitEditor] = useState(false)
  const [newLimit, setNewLimit] = useState('')
  const [limitMessage, setLimitMessage] = useState<string | null>(null)
  const [changingLimit, setChangingLimit] = useState(false)

  function handleAmountChange(raw: string) {
    // Allow only numbers, comma and dot
    const cleaned = raw.replace(/[^\d,.]/g, '')
    setAmount(cleaned)
    setAmountError('')
  }

  function handleNext() {
    const num = parseFloat(amount.replace(',', '.'))
    if (isNaN(num) || num <= 0) {
      setAmountError('Informe um valor válido maior que zero.')
      return
    }
    if (num > 50000) {
      setAmountError('O valor máximo por transferência é R$ 50.000,00.')
      return
    }
    if (fundingSource === 'debit' && limitInfo && num > Number(limitInfo.transfer_limit)) {
      setAmountError(`Esse valor ultrapassa seu limite Pix por transferência de ${fmtBRL(limitInfo.transfer_limit)}.`)
      setNewLimit(Math.ceil(num).toString())
      setShowLimitEditor(true)
      return
    }
    onNext()
  }

  async function handleLimitChange() {
    const requested = Number(newLimit.replace(',', '.'))
    if (!requested || requested <= 0) {
      setLimitMessage('Informe um novo limite válido.')
      return
    }
    setChangingLimit(true)
    setLimitMessage(null)
    try {
      const result = await requestTransferLimitChange(clientId, requested.toFixed(2), 'Ajuste solicitado durante uma transferência Pix')
      if (result.approved) {
        await onLimitUpdated()
        setLimitMessage(`Limite Pix atualizado para ${fmtBRL(result.approved_limit ?? requested)}.`)
        setAmountError('')
        setShowLimitEditor(false)
      } else {
        setLimitMessage('O pedido foi enviado para análise. Para aprovação imediata nesta demonstração, solicite no máximo o dobro do limite atual.')
      }
    } catch (err) {
      setLimitMessage(getApiErrorMessage(err, 'Não foi possível ajustar o limite Pix.'))
    } finally {
      setChangingLimit(false)
    }
  }

  const numVal = parseFloat(amount.replace(',', '.'))
  const exceedsDebitLimit = fundingSource === 'debit' && !!limitInfo && numVal > Number(limitInfo.transfer_limit)
  const valid = !isNaN(numVal) && numVal > 0 && numVal <= 50000 && !exceedsDebitLimit

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Amount input */}
      <div>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: t.textMuted }}>Valor da transferência *</span>
          <div style={{ position: 'relative' }}>
            <span style={{
              position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
              fontSize: 14, fontWeight: 600, color: t.textMuted,
            }}>
              R$
            </span>
            <input
              type="text"
              value={amount}
              onChange={e => handleAmountChange(e.target.value)}
              style={{ ...inputStyle, paddingLeft: 36, fontSize: 20, fontWeight: 700 }}
              placeholder="0,00"
              autoFocus
            />
          </div>
          {!isNaN(numVal) && numVal > 0 && (
            <div style={{ fontSize: 13, color: t.accent, fontWeight: 600 }}>
              {fmtBRL(numVal)}
            </div>
          )}
          {amountError && (
            <div style={{ fontSize: 12, color: t.danger }}>{amountError}</div>
          )}
        </label>
      </div>

      <div>
        <div style={{ fontSize: 12, fontWeight: 700, color: t.textMuted, marginBottom: 8 }}>Como você quer pagar?</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
          <button type="button" onClick={() => setFundingSource('debit')} style={{ border: `1.5px solid ${fundingSource === 'debit' ? t.primary : t.border}`, background: fundingSource === 'debit' ? t.primaryLight : '#fff', borderRadius: 12, padding: 13, color: t.text, textAlign: 'left', cursor: 'pointer' }}><strong style={{ display: 'block', fontSize: 13 }}>Saldo da conta</strong><span style={{ color: t.textMuted, fontSize: 11 }}>Pix no débito</span></button>
          <button type="button" disabled={!card} onClick={() => setFundingSource('credit')} style={{ border: `1.5px solid ${fundingSource === 'credit' ? t.primary : t.border}`, background: fundingSource === 'credit' ? t.primaryLight : '#fff', borderRadius: 12, padding: 13, color: t.text, textAlign: 'left', cursor: card ? 'pointer' : 'not-allowed', opacity: card ? 1 : .55 }}><strong style={{ display: 'block', fontSize: 13 }}>Cartão de crédito</strong><span style={{ color: t.textMuted, fontSize: 11 }}>{card ? `${fmtBRL(card.available_credit)} disponíveis` : 'Sem cartão'}</span></button>
        </div>
        {fundingSource === 'debit' && limitInfo && (
          <div style={{ marginTop: 10, border: `1px solid ${exceedsDebitLimit ? t.warningBorder : t.border}`, background: exceedsDebitLimit ? t.warningBg : t.surface2, borderRadius: 12, padding: '11px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
              <div>
                <div style={{ color: t.textMuted, fontSize: 11 }}>Limite Pix por transferência</div>
                <strong style={{ color: exceedsDebitLimit ? t.warning : t.text, fontSize: 14 }}>{fmtBRL(limitInfo.transfer_limit)}</strong>
              </div>
              <button type="button" onClick={() => { setShowLimitEditor(v => !v); setNewLimit(Math.max(Number(limitInfo.transfer_limit), Number.isFinite(numVal) ? Math.ceil(numVal) : 0).toString()) }} style={{ border: `1px solid ${t.primary}55`, background: t.primaryLight, color: t.primaryHover, borderRadius: 9, padding: '7px 10px', fontSize: 11, fontWeight: 800, cursor: 'pointer' }}>
                Ajustar limite
              </button>
            </div>
            {showLimitEditor && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, marginTop: 10 }}>
                <input value={newLimit} onChange={e => setNewLimit(e.target.value.replace(/[^\d,.]/g, ''))} placeholder="Novo limite" style={{ ...inputStyle, padding: '8px 10px' }} />
                <Btn small onClick={handleLimitChange} disabled={changingLimit}>{changingLimit ? <Spinner size={13} color="#fff" /> : 'Confirmar'}</Btn>
              </div>
            )}
            {limitMessage && <div style={{ marginTop: 8, color: limitMessage.includes('atualizado') ? t.success : t.warning, fontSize: 11, lineHeight: 1.45 }}>{limitMessage}</div>}
          </div>
        )}
      </div>

      {/* Purpose */}
      <div>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: t.textMuted }}>
            Finalidade <span style={{ fontWeight: 400, color: t.textLight }}>(opcional)</span>
          </span>
          <input
            type="text"
            value={purpose}
            onChange={e => setPurpose(e.target.value)}
            style={inputStyle}
            placeholder="Ex.: pagamento de serviço, envio para familiar…"
            maxLength={500}
          />
        </label>
      </div>

      {/* Device recognized (demo param) */}
      <div style={{
        background: t.surface2,
        border: `1px solid ${t.border}`,
        borderRadius: 8,
        padding: '12px 14px',
      }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={deviceRecognized}
            onChange={e => setDeviceRecognized(e.target.checked)}
            style={{ width: 16, height: 16, cursor: 'pointer' }}
          />
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Dispositivo reconhecido</div>
            <div style={{ fontSize: 11, color: t.textMuted, marginTop: 1 }}>
              Parâmetro de simulação para demonstrar diferentes cenários de segurança
            </div>
          </div>
        </label>
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between' }}>
        <Btn variant="secondary" onClick={onBack}>← Voltar</Btn>
        <Btn disabled={!valid} onClick={handleNext}>Continuar</Btn>
      </div>
    </div>
  )
}

// ── Step 2: Review ────────────────────────────────────────────────────────

function StepReview({
  selectedClientName, selectedBenName, selectedBenBank,
  amount, purpose,
  fundingSource,
  onBack, onSubmit, loading,
}: {
  selectedClientName: string
  selectedBenName: string
  selectedBenBank: string
  amount: string
  purpose: string
  fundingSource: 'debit' | 'credit'
  onBack: () => void
  onSubmit: () => void
  loading: boolean
}) {
  const numVal = parseFloat(amount.replace(',', '.'))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Summary card */}
      <div style={{
        background: t.surface2,
        border: `1px solid ${t.border}`,
        borderRadius: 12,
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ background: t.primaryLight, padding: '16px 20px', borderBottom: `1px solid ${t.border}` }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: t.accent, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
            Resumo da transferência
          </div>
          <AmountDisplay amount={numVal} size="xl" color={t.primary} />
        </div>

        {/* Details */}
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div>
              <div style={{ fontSize: 11, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3, marginBottom: 3 }}>
                De
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>{selectedClientName}</div>
              <div style={{ fontSize: 12, color: t.textMuted }}>BobIA Bank · protótipo</div>
              <div style={{ fontSize: 11, color: t.primary, fontWeight: 700, marginTop: 3 }}>{fundingSource === 'credit' ? 'Cartão de crédito' : 'Saldo da conta'}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3, marginBottom: 3 }}>
                Para
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>{selectedBenName}</div>
              <div style={{ fontSize: 12, color: t.textMuted }}>{selectedBenBank}</div>
            </div>
          </div>

          {purpose && (
            <div>
              <div style={{ fontSize: 11, color: t.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.3, marginBottom: 3 }}>
                Finalidade
              </div>
              <div style={{ fontSize: 13, color: t.text2 }}>{purpose}</div>
            </div>
          )}
        </div>
      </div>

      {/* Notice */}
      <div style={{
        background: t.warningBg,
        border: `1px solid ${t.warningBorder}`,
        borderRadius: 8,
        padding: '10px 14px',
        fontSize: 12,
        color: t.warning,
        lineHeight: 1.6,
      }}>
        Ao confirmar, a transferência será submetida ao sistema de verificação de segurança antes de ser processada.
        Dados fictícios — nenhum valor real é movimentado.
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between' }}>
        <Btn variant="secondary" onClick={onBack} disabled={loading}>← Voltar</Btn>
        <Btn onClick={onSubmit} disabled={loading}>
          {loading
            ? <><Spinner size={14} color="#fff" /> Processando…</>
            : 'Confirmar transferência'
          }
        </Btn>
      </div>
    </div>
  )
}

// ── Main Transfer Page ─────────────────────────────────────────────────────

export default function TransferFlowPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const locState = location.state as LocationState | null

  const [step, setStep] = useState<Step>(0)
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [beneficiaries, setBeneficiaries] = useState<BeneficiaryResponse[]>([])
  const [selectedClientId, setSelectedClientId] = useState(locState?.clientId ?? getStoredClientId())
  const [selectedBenId, setSelectedBenId] = useState(locState?.beneficiaryId ?? '')
  const [amount, setAmount] = useState('')
  const [purpose, setPurpose] = useState('')
  const [deviceRecognized, setDeviceRecognized] = useState(true)
  const [fundingSource, setFundingSource] = useState<'debit' | 'credit'>('debit')
  const [cards, setCards] = useState<CreditCardResponse[]>([])
  const [limitInfo, setLimitInfo] = useState<LimitInfoResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load clients
  useEffect(() => {
    fetchClients().then(data => {
      setClients(data)
      if (!selectedClientId && data.length) setSelectedClientId(data[0].external_id)
    }).catch(() => {})
  }, []) // eslint-disable-line

  // Load beneficiaries when client changes
  const loadBeneficiaries = useCallback((clientId: string) => {
    if (!clientId) { setBeneficiaries([]); setSelectedBenId(''); return }
    fetchBeneficiaries(clientId).then(data => {
      setBeneficiaries(data)
      if (!locState?.beneficiaryId || clientId !== locState.clientId) {
        setSelectedBenId(data[0]?.external_id ?? '')
      }
    }).catch(() => {})
  }, []) // eslint-disable-line

  useEffect(() => { loadBeneficiaries(selectedClientId) }, [selectedClientId, loadBeneficiaries])

  useEffect(() => {
    if (!selectedClientId) return
    try { localStorage.setItem('bobia_client_id', selectedClientId) } catch { /* sem persistência */ }
  }, [selectedClientId])

  useEffect(() => {
    if (!selectedClientId) { setCards([]); setLimitInfo(null); setFundingSource('debit'); return }
    fetchClientCards(selectedClientId).then(setCards).catch(() => setCards([]))
    fetchClientLimits(selectedClientId).then(setLimitInfo).catch(() => setLimitInfo(null))
  }, [selectedClientId])

  const refreshLimit = useCallback(async () => {
    if (!selectedClientId) return
    setLimitInfo(await fetchClientLimits(selectedClientId))
  }, [selectedClientId])

  const selectedClient = clients.find(c => c.external_id === selectedClientId)
  const selectedBen = beneficiaries.find(b => b.external_id === selectedBenId)

  async function handleSubmit() {
    if (!selectedClientId || !selectedBenId) return
    setLoading(true)
    setError(null)
    try {
      const result: TransferInitiatedResponse = await initiateTransfer({
        client_external_id: selectedClientId,
        beneficiary_external_id: selectedBenId,
        amount: amount.replace(',', '.'),
        purpose: purpose || undefined,
        device_recognized: deviceRecognized,
        funding_source: fundingSource,
        card_external_id: fundingSource === 'credit' ? cards[0]?.external_id : undefined,
      })
      navigate('/bank/analysis', { state: { result } })
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Não foi possível processar a transferência. Confira os dados e tente novamente.'))
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 540, margin: '0 auto' }}>
      {/* Back */}
      <button
        onClick={() => step > 0 ? setStep(s => (s - 1) as Step) : navigate('/bank')}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: t.textMuted, fontSize: 13, padding: '0 0 16px', fontFamily: t.font, display: 'flex', alignItems: 'center', gap: 4 }}
      >
        ← {step > 0 ? 'Etapa anterior' : 'Início'}
      </button>

      <Card style={{ padding: '24px 24px' }}>
        <div style={{ marginBottom: 8 }}>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: t.text, margin: 0 }}>Nova transferência</h1>
          <p style={{ fontSize: 13, color: t.textMuted, margin: '4px 0 0' }}>Siga as etapas para concluir</p>
        </div>

        <div style={{ marginTop: 20, marginBottom: 24 }}>
          <StepIndicator steps={STEPS} current={step} />
        </div>

        {error && <div style={{ marginBottom: 16 }}><ErrorBox message={error} /></div>}

        {step === 0 && (
          <StepRecipient
            clients={clients}
            selectedClientId={selectedClientId}
            onClientChange={id => { setSelectedClientId(id); setSelectedBenId('') }}
            beneficiaries={beneficiaries}
            selectedBenId={selectedBenId}
            onBenChange={setSelectedBenId}
            onNext={() => setStep(1)}
          />
        )}

        {step === 1 && (
          <StepAmount
            amount={amount}
            setAmount={setAmount}
            purpose={purpose}
            setPurpose={setPurpose}
            deviceRecognized={deviceRecognized}
            setDeviceRecognized={setDeviceRecognized}
            fundingSource={fundingSource}
            setFundingSource={setFundingSource}
            card={cards[0]}
            limitInfo={limitInfo}
            clientId={selectedClientId}
            onLimitUpdated={refreshLimit}
            onBack={() => setStep(0)}
            onNext={() => setStep(2)}
          />
        )}

        {step === 2 && selectedClient && selectedBen && (
          <StepReview
            selectedClientName={selectedClient.name}
            selectedBenName={selectedBen.name}
            selectedBenBank={selectedBen.bank_name}
            amount={amount}
            purpose={purpose}
            fundingSource={fundingSource}
            onBack={() => setStep(1)}
            onSubmit={handleSubmit}
            loading={loading}
          />
        )}
      </Card>
    </div>
  )
}
