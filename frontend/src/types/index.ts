// Tipos compartilhados da aplicação — alinhados com os schemas do backend

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export type TransactionStatus =
  | 'pending'
  | 'released'
  | 'under_verification'
  | 'awaiting_confirmation'
  | 'escalated_to_human'
  | 'human_review_pending'
  | 'human_approved'
  | 'human_rejected'
  | 'rejected'
  | 'approved'
  | 'requires_verification'
  | 'blocked'

export type RecommendedAction =
  | 'approve'
  | 'request_confirmation'
  | 'escalate_to_human'
  | 'block'

// ── Health ────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string
  version: string
  environment: string
  database: string
  llm_provider: string
}

// ── Clientes ──────────────────────────────────────────────────────────────────

export interface ClientSummary {
  id: number
  external_id: string
  name: string
  risk_profile: 'low' | 'medium' | 'high'
  is_active: boolean
}

export interface ClientResponse extends ClientSummary {
  document_hint: string
  agency: string
  account_number: string
  account_type: string
  balance: string
  reserved_balance: string
  available_balance: string
  transfer_limit: string
  account_age_days: number
  created_at: string
}

export interface StatementEntryResponse {
  id: number
  client_id: number
  transaction_id: number | null
  entry_type: 'debit' | 'credit' | 'reserve' | 'release'
  amount: string
  currency: string
  description: string
  counterpart_name: string | null
  counterpart_bank: string | null
  status: 'posted' | 'pending' | 'reversed'
  balance_after: string
  posted_at: string
  created_at: string
}

export interface LimitInfoResponse {
  client_external_id: string
  transfer_limit: string
  used_today: string
  available_limit: string
  balance: string
  reserved_balance: string
  available_balance: string
}

export interface LimitChangeResponse {
  previous_limit: string
  requested_limit: string
  approved_limit: string | null
  status: string
  approved: boolean
  client_external_id: string
  event_correlation_id: string
  message: string
}

// ── Beneficiários ─────────────────────────────────────────────────────────────

export interface BeneficiaryResponse {
  id: number
  external_id: string
  client_id: number
  name: string
  account_hint: string
  bank_name: string
  is_known: boolean
  is_favorite: boolean
  transfer_count: number
  total_transferred: string
  risk_hint: number
  first_registered_at: string
  created_at: string
}

export interface BeneficiaryCreatePayload {
  name: string
  account_hint: string
  bank_name: string
  is_known?: boolean
  risk_hint?: number
}

// ── Transações ────────────────────────────────────────────────────────────────

export interface TransactionResponse {
  id: number
  external_id: string
  client_id: number
  beneficiary_id: number
  amount: string
  currency: string
  purpose: string | null
  funding_source?: 'debit' | 'credit'
  card_id?: number | null
  is_new_recipient: boolean
  recent_limit_change: boolean
  device_recognized: boolean
  risk_level: RiskLevel
  risk_score: number
  status: TransactionStatus
  decision_reasoning: string | null
  created_at: string
  updated_at: string
  client_name?: string
  beneficiary_name?: string
}

// ── Análise de Risco ──────────────────────────────────────────────────────────

export interface RiskAnalysisResponse {
  id: number
  external_id: string
  transaction_id: number
  overall_risk_score: number
  risk_level: string
  recommended_action: RecommendedAction
  reasoning: string | null
  flags: string | null
  status: string
  orchestrator_result: string | null
  fraud_agent_result: string | null
  inconsistency_agent_result: string | null
  behavioral_agent_result: string | null
  intention_agent_result?: string | null
  risk_agent_result: string | null
  // Etapa 6
  divergence_detected: boolean
  divergence_details: string | null
  policy_version: string | null
  confirmation_purpose: string | null
  phase: string
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface AgentResultParsed {
  agent_name: string
  analysis_id: string
  risk_level: string
  confidence: number
  detected_signals: string[]
  evidence: string[]
  explanation: string
  recommended_action: string
  model_used: string
  execution_time_ms: number
  status: string
  mode: string
  // legado
  risk_score: number
  flags: string[]
  reasoning: string
  metadata: Record<string, unknown>
}

// ── Gateway ───────────────────────────────────────────────────────────────────

export interface GatewayResponse {
  authorized: boolean
  final_status: TransactionStatus
  final_action: RecommendedAction
  risk_level: RiskLevel
  risk_score: number
  requires_confirmation: boolean
  requires_human_review: boolean
  gateway_reasoning: string
  flags: string[]
  policy_version: string | null
  divergence_detected: boolean
  unauthorized_action_attempted: boolean
}

// ── Resposta de transferência ─────────────────────────────────────────────────

export interface TransferInitiatedResponse {
  transaction: TransactionResponse
  analysis: RiskAnalysisResponse
  gateway: GatewayResponse | null
  message: string
  idempotent: boolean
  pipeline_failed: boolean
  failure_reason: string | null
}

// ── Payload para iniciar transferência ────────────────────────────────────────

export interface TransferPayload {
  client_external_id: string
  beneficiary_external_id: string
  amount: string
  purpose?: string
  device_recognized?: boolean
  funding_source?: 'debit' | 'credit'
  card_external_id?: string
  idempotency_key?: string
}

// ── Cartões e limite de crédito ──────────────────────────────────────────────

export interface CreditCardResponse {
  id: number
  external_id: string
  client_id: number
  nickname: string
  masked_number: string
  brand: string
  color_start: string
  color_end: string
  credit_limit: string
  used_credit: string
  reserved_credit: string
  available_credit: string
  due_day: number
  closing_day: number
  status: 'active' | 'blocked'
  created_at: string
}

export interface LimitAgentContribution {
  agent_name: string
  risk_score: number
  flags: string[]
  explanation: string
}

export interface CreditLimitAssessment {
  overall_risk_score: number
  risk_level: RiskLevel
  flags: string[]
  agents: LimitAgentContribution[]
  human_review_required: boolean
  recommendation: string
}

export interface CreditLimitRequestResponse {
  id: number
  external_id: string
  client_id: number
  card_id: number
  current_limit: string
  requested_limit: string
  reason: string | null
  status: 'pending_review' | 'approved' | 'rejected'
  risk_score: number
  risk_level: string
  agent_assessment: string
  reviewer_id: string | null
  reviewer_notes: string | null
  reviewed_at: string | null
  created_at: string
  card?: CreditCardResponse | null
  client_name?: string | null
}

// ── Confirmação contextual ────────────────────────────────────────────────────

export interface ConfirmTransferResponse {
  transaction: TransactionResponse
  analysis: RiskAnalysisResponse
  new_status: string
  reasoning: string
  coercion_detected: boolean
  message: string
}

// ── Revisão humana ────────────────────────────────────────────────────────────

export interface HumanReviewResponse {
  transaction: TransactionResponse
  new_status: string
  action: string
  reviewer_id: string
  reasoning: string
  message: string
}

// ── Auditoria ─────────────────────────────────────────────────────────────────

export interface AuditLog {
  id: number
  transaction_id: number | null
  component: string
  agent_name: string
  action: string
  event: string | null
  result: string | null
  input_summary: string | null
  output_summary: string | null
  reasoning: string | null
  risk_score: number | null
  flags: string | null
  correlation_id: string | null
  policy_version: string | null
  execution_time_ms: number | null
  agent_contributions: string | null
  created_at: string
}

// ── Demo ──────────────────────────────────────────────────────────────────────

export interface DemoScenario {
  description: string
  client_id?: string
  recipient_id?: string
  recipient_name?: string
  amount?: number
  purpose?: string
  is_new_recipient?: boolean
  recent_limit_change?: boolean
  device_recognized?: boolean
}
