// Tipos para o sistema de métricas — espelham a resposta de /api/v1/metrics/summary

export interface MetricsVolume {
  total_transactions: number
  total_analyses: number
  total_audit_logs: number
}

export interface RiskCounts {
  low: number
  medium: number
  high: number
  critical: number
}

export interface RiskDistribution {
  counts: RiskCounts
  percentages: { low: number | null; medium: number | null; high: number | null; critical: number | null }
  total: number
}

export interface MetricsRates {
  confirmation_rate: number | null
  confirmation_count: number
  human_review_rate: number | null
  human_review_count: number
  insufficient_data: boolean
}

export interface TimingStats {
  avg_ms: number | null
  min_ms: number | null
  max_ms: number | null
  median_ms: number | null
  sample_size: number
  insufficient_data: boolean
}

export interface AgentTimingEntry {
  avg_ms: number | null
  min_ms: number | null
  max_ms: number | null
  sample_size: number
  insufficient_data: boolean
}

export interface DivergenceMetrics {
  divergence_count: number
  completed_analyses: number
  divergence_rate: number | null
}

export interface ActionCounts {
  approve: number
  request_confirmation: number
  escalate_to_human: number
  block: number
  [key: string]: number
}

export interface ActionDistribution {
  counts: ActionCounts
  percentages: { [key: string]: number | null }
  total: number
}

export interface StatusDistribution {
  counts: { [status: string]: number }
  percentages: { [status: string]: number | null }
}

export interface ClassificationDetail {
  external_id: string
  reference_label: 'positive' | 'negative'
  predicted: 'positive' | 'negative'
  status: string
  risk_level: string
  classification: 'TP' | 'FP' | 'TN' | 'FN'
}

export interface ClassificationDefinition {
  positive_class: string
  negative_class?: string
  precision_formula?: string
  recall_formula?: string
  f1_formula?: string
  disclaimer: string
  reference_labels?: Record<string, boolean>
  prediction_rule?: string
}

export interface ClassificationMetrics {
  available: boolean
  reason?: string
  labeled_count: number
  tp?: number
  fp?: number
  tn?: number
  fn?: number
  precision?: number | null
  recall?: number | null
  f1_score?: number | null
  accuracy?: number | null
  details?: ClassificationDetail[]
  definition: ClassificationDefinition
}

export interface ModeBreakdown {
  AI_MODE: number
  RULES_MODE: number
  unknown: number
  total: number
}

export interface RiskScoreBucket {
  range: string
  count: number
  percentage: number
}

export interface MetricsSummary {
  generated_at: string
  volume: MetricsVolume
  risk_distribution: RiskDistribution
  rates: MetricsRates
  timing: TimingStats
  agent_timing: Record<string, AgentTimingEntry>
  divergence: DivergenceMetrics
  audited_decisions: number
  component_failures: Record<string, number>
  action_distribution: ActionDistribution
  status_distribution: StatusDistribution
  classification: ClassificationMetrics
  mode_breakdown: ModeBreakdown
  risk_score_distribution: RiskScoreBucket[]
}
