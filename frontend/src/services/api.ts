// Cliente HTTP para comunicação com a API backend

import axios from 'axios'
import type {
  AuditLog,
  BeneficiaryResponse,
  ClientResponse,
  ClientSummary,
  ConfirmTransferResponse,
  DemoScenario,
  HealthResponse,
  HumanReviewResponse,
  RiskAnalysisResponse,
  TransactionResponse,
  TransferInitiatedResponse,
  TransferPayload,
  CreditCardResponse,
  CreditLimitRequestResponse,
  BeneficiaryCreatePayload,
  StatementEntryResponse,
  LimitInfoResponse,
  LimitChangeResponse,
} from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 45_000,
  headers: { 'Content-Type': 'application/json' },
})

export function getApiErrorMessage(error: unknown, fallback = 'Não foi possível concluir a operação.'): string {
  const payload = (error as { response?: { data?: unknown } })?.response?.data
  if (payload && typeof payload === 'object') {
    const data = payload as { error?: unknown; detail?: unknown; message?: unknown }
    for (const candidate of [data.error, data.detail, data.message]) {
      if (typeof candidate === 'string' && candidate.trim()) return candidate
      if (Array.isArray(candidate)) {
        const messages = candidate
          .map(item => item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : '')
          .filter(Boolean)
        if (messages.length) return messages.join(' ')
      }
    }
  }
  const message = (error as { message?: unknown })?.message
  if (typeof message === 'string' && !/^Request failed with status code/i.test(message)) return message
  return fallback
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health')
  return data
}

// ── Clientes ──────────────────────────────────────────────────────────────────

export async function fetchClients(): Promise<ClientSummary[]> {
  const { data } = await api.get<ClientSummary[]>('/clients/')
  return data
}

export async function fetchClient(externalId: string): Promise<ClientResponse> {
  const { data } = await api.get<ClientResponse>(`/clients/${externalId}`)
  return data
}

export async function fetchClientStatement(
  externalId: string,
  limit = 100
): Promise<StatementEntryResponse[]> {
  const { data } = await api.get<StatementEntryResponse[]>(`/clients/${externalId}/statement`, {
    params: { limit },
  })
  return data
}

export async function fetchClientLimits(externalId: string): Promise<LimitInfoResponse> {
  const { data } = await api.get<LimitInfoResponse>(`/clients/${externalId}/limits`)
  return data
}

export async function requestTransferLimitChange(
  externalId: string,
  requestedLimit: string,
  reason?: string
): Promise<LimitChangeResponse> {
  const { data } = await api.post<LimitChangeResponse>(`/clients/${externalId}/limits`, {
    requested_limit: requestedLimit,
    reason,
  })
  return data
}

// ── Beneficiários ─────────────────────────────────────────────────────────────

export async function fetchBeneficiaries(
  clientExternalId: string
): Promise<BeneficiaryResponse[]> {
  const { data } = await api.get<BeneficiaryResponse[]>(
    `/beneficiaries/client/${clientExternalId}`
  )
  return data
}

export async function setBeneficiaryFavorite(
  externalId: string,
  isFavorite: boolean
): Promise<BeneficiaryResponse> {
  const { data } = await api.patch<BeneficiaryResponse>(
    `/beneficiaries/${externalId}/favorite`,
    { is_favorite: isFavorite }
  )
  return data
}

export async function createBeneficiary(
  clientExternalId: string,
  payload: BeneficiaryCreatePayload
): Promise<BeneficiaryResponse> {
  const { data } = await api.post<BeneficiaryResponse>(
    `/clients/${clientExternalId}/beneficiaries`,
    payload
  )
  return data
}

// ── Transferências ────────────────────────────────────────────────────────────

export async function initiateTransfer(
  payload: TransferPayload
): Promise<TransferInitiatedResponse> {
  const { data } = await api.post<TransferInitiatedResponse>('/transactions/', payload)
  return data
}

export async function fetchTransactions(limit = 50): Promise<TransactionResponse[]> {
  const { data } = await api.get<TransactionResponse[]>('/transactions/', {
    params: { limit },
  })
  return data
}

export async function fetchTransaction(externalId: string): Promise<TransactionResponse> {
  const { data } = await api.get<TransactionResponse>(`/transactions/${externalId}`)
  return data
}

export async function confirmTransfer(
  externalId: string,
  confirmationPurpose: string
): Promise<ConfirmTransferResponse> {
  const { data } = await api.post<ConfirmTransferResponse>(
    `/transactions/${externalId}/confirm`,
    { confirmation_purpose: confirmationPurpose }
  )
  return data
}

export async function submitHumanReview(
  externalId: string,
  action: 'approve' | 'reject',
  reviewerId: string,
  reviewerNotes?: string
): Promise<HumanReviewResponse> {
  const { data } = await api.post<HumanReviewResponse>(
    `/transactions/${externalId}/human-review/${action}`,
    { reviewer_id: reviewerId, reviewer_notes: reviewerNotes }
  )
  return data
}

export async function fetchClientTransactions(
  clientExternalId: string,
  limit = 20
): Promise<TransactionResponse[]> {
  const { data } = await api.get<TransactionResponse[]>(
    `/transactions/client/${clientExternalId}`,
    { params: { limit } }
  )
  return data
}

// ── Cartões e solicitações de limite ────────────────────────────────────────

export async function fetchClientCards(clientExternalId: string): Promise<CreditCardResponse[]> {
  const { data } = await api.get<CreditCardResponse[]>(`/cards/client/${clientExternalId}`)
  return data
}

export async function submitCreditLimitRequest(
  cardExternalId: string,
  requestedLimit: string,
  reason?: string
): Promise<CreditLimitRequestResponse> {
  const { data } = await api.post<CreditLimitRequestResponse>(
    `/cards/${cardExternalId}/limit-requests`,
    { requested_limit: requestedLimit, reason }
  )
  return data
}

export async function fetchCreditLimitRequests(params?: {
  status?: 'pending_review' | 'approved' | 'rejected'
  clientExternalId?: string
}): Promise<CreditLimitRequestResponse[]> {
  const { data } = await api.get<CreditLimitRequestResponse[]>('/cards/limit-requests', {
    params: { status: params?.status, client_external_id: params?.clientExternalId },
  })
  return data
}

export async function reviewCreditLimitRequest(
  requestExternalId: string,
  action: 'approve' | 'reject',
  reviewerId: string,
  reviewerNotes?: string
): Promise<CreditLimitRequestResponse> {
  const { data } = await api.post<CreditLimitRequestResponse>(
    `/cards/limit-requests/${requestExternalId}/review/${action}`,
    { reviewer_id: reviewerId, reviewer_notes: reviewerNotes }
  )
  return data
}

// ── Análises de risco ─────────────────────────────────────────────────────────

export async function fetchRiskAnalyses(limit = 50): Promise<RiskAnalysisResponse[]> {
  const { data } = await api.get<RiskAnalysisResponse[]>('/risk-analyses/', {
    params: { limit },
  })
  return data
}

export async function fetchRiskAnalysis(
  transactionExternalId: string
): Promise<RiskAnalysisResponse> {
  const { data } = await api.get<RiskAnalysisResponse>(
    `/risk-analyses/transaction/${transactionExternalId}`
  )
  return data
}

// ── Demo ──────────────────────────────────────────────────────────────────────

export async function fetchScenarios(): Promise<Record<string, { description: string }>> {
  const { data } = await api.get<{ scenarios: Record<string, { description: string }> }>(
    '/simulation/scenarios'
  )
  return data.scenarios
}

export async function fetchScenario(key: string): Promise<DemoScenario> {
  const { data } = await api.get<DemoScenario>(`/simulation/scenarios/${key}`)
  return data
}

export async function resetDemo(): Promise<void> {
  await api.post('/demo/reset')
}

// ── Auditoria ─────────────────────────────────────────────────────────────────

export async function fetchAuditLogs(limit = 100): Promise<AuditLog[]> {
  const { data } = await api.get<AuditLog[]>('/audit/', { params: { limit } })
  return data
}

// ── Métricas (Etapa 8) ────────────────────────────────────────────────────────

export async function fetchMetrics(): Promise<import('../types/metrics').MetricsSummary> {
  const { data } = await api.get('/metrics/summary')
  return data
}

export default api
