// ─── BobIA — Design System Components ─────────────────────────────────────
// All shared tokens, utilities and components used across client and admin UIs.

import type { CSSProperties, ReactNode } from 'react'

// ── Brand token (inline JS mirror of CSS vars) ────────────────────────────

export const t = {
  // Brand
  primary: '#465EFF',
  primaryHover: '#3333BD',
  primaryLight: '#EEF0FF',
  accent: '#3333BD',
  accentHover: '#24249A',
  yellow: '#FCFC30',
  yellowHover: '#EEEE18',
  // Semantic
  success: '#15803d',
  successBg: '#f0fdf4',
  successBorder: '#bbf7d0',
  warning: '#b45309',
  warningBg: '#fffbeb',
  warningBorder: '#fde68a',
  danger: '#b91c1c',
  dangerBg: '#fef2f2',
  dangerBorder: '#fecaca',
  orange: '#c2410c',
  orangeBg: '#fff7ed',
  orangeBorder: '#fed7aa',
  // Neutrals
  bg: '#f5f5f7',
  surface: '#ffffff',
  surface2: '#f8f9fb',
  border: '#e2e6ed',
  borderStrong: '#c8cdd8',
  text: '#111827',
  text2: '#374151',
  textMuted: '#4b5563',
  textLight: '#6b7280',
  textPlaceholder: '#9ca3af',
  // Radius
  radiusSm: '6px',
  radius: '14px',
  radiusLg: '22px',
  // Shadow
  shadowSm: '0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04)',
  shadow: '0 2px 8px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.05)',
  shadowMd: '0 4px 16px rgba(0,0,0,0.10), 0 2px 6px rgba(0,0,0,0.06)',
  // Font
  font: '"Segoe UI Variable", "Aptos", "Inter", "Segoe UI", system-ui, sans-serif',
} as const

// Keep 'clr' as backward-compat alias used by admin pages
export const clr = {
  bg: t.bg,
  surface: t.surface,
  surfaceAlt: t.surface2,
  border: t.border,
  borderStrong: t.borderStrong,
  text: t.text,
  textMuted: t.textMuted,
  textLight: t.textLight,
  accent: t.accent,
  accentHover: t.accentHover,
  accentLight: t.primaryLight,
  purple: '#7c3aed',
  header: t.primary,
} as const

// ── Risk / Status Maps ─────────────────────────────────────────────────────

export const RISK_COLOR: Record<string, string> = {
  low: t.success,
  medium: '#d97706',
  high: '#ea580c',
  critical: '#dc2626',
}

export const STATUS_COLOR: Record<string, string> = {
  released: t.success,
  human_approved: t.success,
  approved: t.success,
  awaiting_confirmation: '#d97706',
  under_verification: '#d97706',
  requires_verification: '#d97706',
  human_review_pending: '#ea580c',
  escalated_to_human: '#ea580c',
  pending: '#6b7280',
  rejected: '#dc2626',
  human_rejected: '#dc2626',
  blocked: '#dc2626',
}

export const STATUS_LABEL: Record<string, string> = {
  released: 'Liberada',
  human_approved: 'Aprovada (revisor)',
  approved: 'Aprovada',
  awaiting_confirmation: 'Aguardando confirmação',
  under_verification: 'Em verificação',
  requires_verification: 'Requer verificação',
  human_review_pending: 'Aguardando revisão',
  escalated_to_human: 'Escalada para revisão',
  pending: 'Pendente',
  rejected: 'Rejeitada',
  human_rejected: 'Rejeitada (revisor)',
  blocked: 'Bloqueada',
}

export const STATUS_ICON: Record<string, string> = {
  released: '✓',
  human_approved: '✓',
  approved: '✓',
  awaiting_confirmation: '!',
  under_verification: '!',
  requires_verification: '!',
  human_review_pending: '·',
  escalated_to_human: '·',
  pending: '·',
  rejected: '✕',
  human_rejected: '✕',
  blocked: '✕',
}

export const ACTION_LABEL: Record<string, string> = {
  approve: 'Aprovada',
  approved: 'Aprovada',
  request_confirmation: 'Verificação solicitada',
  escalate_to_human: 'Escalada para revisão',
  require_human_review: 'Revisão humana necessária',
  reject: 'Rejeitada',
  rejected: 'Rejeitada',
  block: 'Bloqueada',
}

export const AGENT_LABEL: Record<string, string> = {
  fraud_agent: 'Prevenção a fraude',
  behavioral_agent: 'Perfil de movimentação',
  inconsistency_agent: 'Consistência da operação',
  intention_agent: 'Finalidade declarada',
  risk_agent: 'Consolidação de risco',
  orchestrator_agent: 'Coordenação da análise',
  orchestrator: 'Coordenação da análise',
}

export function actionLabel(value: string | null | undefined): string {
  if (!value) return 'Ação registrada'
  return ACTION_LABEL[value] ?? 'Encaminhada para análise'
}

export function statusLabel(value: string | null | undefined): string {
  if (!value) return 'Em processamento'
  return STATUS_LABEL[value] ?? ({ completed: 'Concluída', failed: 'Falhou', running: 'Em processamento' }[value] ?? 'Registrada')
}

export function agentLabel(value: string | null | undefined): string {
  if (!value) return 'Sistema de análise'
  return AGENT_LABEL[value] ?? 'Sistema de análise'
}

export function employeeExplanation(value: string | null | undefined): string {
  if (!value) return 'A avaliação foi registrada sem observações adicionais.'
  return value
    .replace(/Sinais identificados:\s*[^.]*\.\s*/gi, '')
    .replace(/Desvios detectados:\s*[^.]*\.\s*/gi, '')
    .replace(/Inconsistências:\s*[^.]*\.\s*/gi, '')
    .replace(/Sinais:\s*[^.]*\.\s*/gi, '')
    .replace(/\(score=[^)]+\)/gi, '')
    .replace(/nível\s+low/gi, 'nível baixo')
    .replace(/nível\s+medium/gi, 'nível médio')
    .replace(/nível\s+high/gi, 'nível alto')
    .replace(/nível\s+critical/gi, 'nível crítico')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

export const RISK_LABEL: Record<string, string> = {
  low: 'Baixo',
  medium: 'Médio',
  high: 'Alto',
  critical: 'Crítico',
}

// ── Utilities ──────────────────────────────────────────────────────────────

export const FONTS = t.font

export function riskColor(score: number): string {
  if (score < 0.3) return RISK_COLOR.low
  if (score < 0.6) return RISK_COLOR.medium
  if (score < 0.85) return RISK_COLOR.high
  return RISK_COLOR.critical
}

export function riskLabel(score: number): string {
  if (score < 0.3) return 'Baixo'
  if (score < 0.6) return 'Médio'
  if (score < 0.85) return 'Alto'
  return 'Crítico'
}

export function fmtBRL(amount: string | number): string {
  return `R$ ${Number(amount).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

export function fmtDateLong(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'long', timeStyle: 'short' })
}

export function parseJSON<T>(raw: string | null): T | null {
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

export function parseFlags(raw: string | null): string[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch { return [] }
}

// ── Base Components ────────────────────────────────────────────────────────

export function Spinner({ size = 20, color = t.accent }: { size?: number; color?: string }) {
  return (
    <span
      role="status"
      aria-label="Carregando"
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        border: `2px solid ${color}33`,
        borderTopColor: color,
        borderRadius: '50%',
        animation: 'spin 0.7s linear infinite',
        flexShrink: 0,
      }}
    />
  )
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div role="alert" style={{
      background: t.dangerBg,
      border: `1px solid ${t.dangerBorder}`,
      borderRadius: 8,
      padding: '12px 16px',
      color: t.danger,
      fontSize: 13,
      lineHeight: 1.5,
      display: 'flex',
      gap: 8,
      alignItems: 'flex-start',
    }}>
      <span style={{ flexShrink: 0, fontWeight: 900 }}>!</span>
      <span>{message}</span>
    </div>
  )
}

export function InfoBox({ message, type = 'info' }: { message: string | ReactNode; type?: 'info' | 'warn' | 'success' | 'orange' }) {
  const map = {
    info:    { bg: t.primaryLight,  border: '#bfdbfe', text: '#1e40af' },
    warn:    { bg: t.warningBg,     border: t.warningBorder, text: t.warning },
    success: { bg: t.successBg,     border: t.successBorder, text: t.success },
    orange:  { bg: t.orangeBg,      border: t.orangeBorder,  text: t.orange },
  }[type]
  return (
    <div style={{
      background: map.bg,
      border: `1px solid ${map.border}`,
      borderRadius: 8,
      padding: '10px 14px',
      color: map.text,
      fontSize: 13,
      lineHeight: 1.5,
    }}>
      {message}
    </div>
  )
}

export function Badge({ text, color, small = false }: { text: string; color: string; small?: boolean }) {
  return (
    <span style={{
      background: color + '18',
      color,
      border: `1px solid ${color}40`,
      borderRadius: 4,
      padding: small ? '1px 6px' : '2px 9px',
      fontSize: small ? 10 : 11,
      fontWeight: 700,
      whiteSpace: 'nowrap',
    }}>
      {text}
    </span>
  )
}

export function RiskBadge({ level }: { level: string }) {
  const color = RISK_COLOR[level] ?? '#6b7280'
  return <Badge text={(RISK_LABEL[level] ?? level).toUpperCase()} color={color} />
}

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLOR[status] ?? '#6b7280'
  const label = statusLabel(status)
  return <Badge text={label} color={color} />
}

export function RiskBar({ score, compact = false }: { score: number; compact?: boolean }) {
  const pct = Math.round(score * 100)
  const color = riskColor(score)
  return (
    <div style={{ margin: compact ? '4px 0' : '8px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 11, color: t.textMuted }}>Score de risco</span>
        <span style={{ fontWeight: 700, color, fontSize: 12 }}>{pct}%</span>
      </div>
      <div style={{ background: t.border, borderRadius: 4, height: compact ? 5 : 8, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', borderRadius: 4,
          background: color, transition: 'width 0.5s ease',
        }} />
      </div>
    </div>
  )
}

export function Card({
  children, style, className
}: { children: ReactNode; style?: CSSProperties; className?: string }) {
  return (
    <div className={['app-card', className].filter(Boolean).join(' ')} style={{
      background: t.surface,
      border: `1px solid ${t.border}`,
      borderRadius: 10,
      padding: 20,
      boxShadow: t.shadowSm,
      ...style,
    }}>
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div style={{ marginBottom: 16, paddingBottom: 12, borderBottom: `1px solid ${t.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: t.text }}>{title}</h2>
        {subtitle && <p style={{ margin: '3px 0 0', color: t.textMuted, fontSize: 13 }}>{subtitle}</p>}
      </div>
      {action && <div style={{ flexShrink: 0 }}>{action}</div>}
    </div>
  )
}

export function InfoCell({ label, value, color }: { label: string; value: ReactNode; color?: string }) {
  return (
    <div style={{
      background: t.surface2, borderRadius: 6, padding: '7px 10px',
      border: `1px solid ${t.border}`,
    }}>
      <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 600, marginBottom: 2, textTransform: 'uppercase', letterSpacing: 0.3 }}>
        {label}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: color ?? t.text }}>{value}</div>
    </div>
  )
}

export function Btn({
  children, onClick, disabled = false, variant = 'primary', fullWidth = false, small = false, type = 'button', style: extraStyle
}: {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success'
  fullWidth?: boolean
  small?: boolean
  type?: 'button' | 'submit'
  style?: CSSProperties
}) {
  const styles: Record<string, CSSProperties> = {
    primary:   { background: disabled ? t.textPlaceholder : t.accent,   color: '#fff', border: 'none' },
    secondary: { background: t.surface, color: t.text,     border: `1px solid ${t.border}` },
    danger:    { background: disabled ? t.textPlaceholder : '#dc2626',  color: '#fff', border: 'none' },
    ghost:     { background: 'transparent', color: t.textMuted, border: `1px solid ${t.border}` },
    success:   { background: disabled ? t.textPlaceholder : '#16a34a',  color: '#fff', border: 'none' },
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        ...styles[variant],
        borderRadius: 6,
        padding: small ? '5px 12px' : '9px 20px',
        fontWeight: 600,
        fontSize: small ? 12 : 14,
        cursor: disabled ? 'not-allowed' : 'pointer',
        width: fullWidth ? '100%' : undefined,
        fontFamily: t.font,
        transition: 'opacity 0.15s, background 0.15s',
        opacity: disabled ? 0.6 : 1,
        lineHeight: 1.4,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        whiteSpace: 'nowrap',
        ...extraStyle,
      }}
    >
      {children}
    </button>
  )
}

export const inputStyle: CSSProperties = {
  border: `1px solid ${t.borderStrong}`,
  borderRadius: 6,
  padding: '9px 12px',
  fontSize: 14,
  background: t.surface,
  width: '100%',
  boxSizing: 'border-box',
  fontFamily: t.font,
  color: t.text,
  lineHeight: 1.4,
  outline: 'none',
}

export const tableStyle: CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 13,
}

export const thStyle: CSSProperties = {
  padding: '9px 12px',
  textAlign: 'left',
  fontSize: 10,
  fontWeight: 700,
  color: t.textMuted,
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  borderBottom: `2px solid ${t.border}`,
  whiteSpace: 'nowrap',
  background: t.surface2,
}

export const tdStyle: CSSProperties = {
  padding: '9px 12px',
  verticalAlign: 'middle',
  borderBottom: `1px solid ${t.border}`,
  color: t.text2,
}

// ── Label ──────────────────────────────────────────────────────────────────

export function FieldLabel({ children, required }: { children: ReactNode; required?: boolean }) {
  return (
    <span style={{ fontSize: 12, fontWeight: 600, color: t.textMuted, display: 'block', marginBottom: 5 }}>
      {children}
      {required && <span style={{ color: t.danger, marginLeft: 2 }}>*</span>}
    </span>
  )
}

// ── Divider ────────────────────────────────────────────────────────────────

export function Divider({ label }: { label?: string }) {
  if (!label) return <hr style={{ border: 'none', borderTop: `1px solid ${t.border}`, margin: '16px 0' }} />
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '16px 0' }}>
      <div style={{ flex: 1, height: 1, background: t.border }} />
      <span style={{ fontSize: 11, color: t.textLight, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: t.border }} />
    </div>
  )
}

// ── AmountDisplay ──────────────────────────────────────────────────────────

export function AmountDisplay({ amount, size = 'lg', color }: { amount: string | number; size?: 'sm' | 'md' | 'lg' | 'xl'; color?: string }) {
  const formatted = fmtBRL(amount)
  const fontSize = { sm: 16, md: 20, lg: 28, xl: 36 }[size]
  return (
    <span style={{ fontWeight: 800, fontSize, color: color ?? t.text, fontVariantNumeric: 'tabular-nums' }}>
      {formatted}
    </span>
  )
}

// ── StepIndicator ──────────────────────────────────────────────────────────

export function StepIndicator({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 24 }}>
      {steps.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', flex: i < steps.length - 1 ? 1 : undefined }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: done ? t.success : active ? t.accent : t.border,
                color: done || active ? '#fff' : t.textLight,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700,
                transition: 'background 0.2s',
                flexShrink: 0,
              }}>
                {done ? '✓' : i + 1}
              </div>
              <span style={{ fontSize: 10, fontWeight: active ? 700 : 500, color: active ? t.accent : done ? t.success : t.textLight, whiteSpace: 'nowrap' }}>
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div style={{ flex: 1, height: 2, background: done ? t.success : t.border, margin: '-14px 4px 0', transition: 'background 0.2s' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── SectionLabel ──────────────────────────────────────────────────────────

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 700, color: t.textMuted, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>
      {children}
    </div>
  )
}

// ── EmptyState ─────────────────────────────────────────────────────────────

export function EmptyState({ icon, title, body }: { icon?: string; title: string; body?: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 24px', color: t.textLight }}>
      {icon && <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.5 }}>{icon}</div>}
      <div style={{ fontSize: 15, fontWeight: 600, color: t.textMuted, marginBottom: 4 }}>{title}</div>
      {body && <div style={{ fontSize: 13, lineHeight: 1.6 }}>{body}</div>}
    </div>
  )
}

// ── ProcessingState ────────────────────────────────────────────────────────

export function ProcessingState({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px 24px', gap: 16 }}>
      <Spinner size={36} color={t.accent} />
      <span style={{ fontSize: 14, color: t.textMuted, fontWeight: 500 }}>{label}</span>
    </div>
  )
}

// ── ResultStatusIcon ───────────────────────────────────────────────────────

export function ResultStatusIcon({ status, size = 56 }: { status: string; size?: number }) {
  const map: Record<string, { bg: string; color: string; symbol: string }> = {
    released:             { bg: t.successBg,   color: t.success, symbol: '✓' },
    human_approved:       { bg: t.successBg,   color: t.success, symbol: '✓' },
    approved:             { bg: t.successBg,   color: t.success, symbol: '✓' },
    awaiting_confirmation:{ bg: t.warningBg,   color: '#d97706',  symbol: '!' },
    under_verification:   { bg: t.warningBg,   color: '#d97706',  symbol: '!' },
    requires_verification:{ bg: t.warningBg,   color: '#d97706',  symbol: '!' },
    human_review_pending: { bg: t.orangeBg,    color: t.orange,   symbol: '·' },
    escalated_to_human:   { bg: t.orangeBg,    color: t.orange,   symbol: '·' },
    pending:              { bg: t.surface2,    color: t.textLight, symbol: '·' },
    rejected:             { bg: t.dangerBg,    color: t.danger,   symbol: '✕' },
    human_rejected:       { bg: t.dangerBg,    color: t.danger,   symbol: '✕' },
    blocked:              { bg: t.dangerBg,    color: t.danger,   symbol: '✕' },
  }
  const cfg = map[status] ?? { bg: t.surface2, color: t.textLight, symbol: '?' }
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: cfg.bg,
      border: `2px solid ${cfg.color}30`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.42, fontWeight: 700, color: cfg.color,
      flexShrink: 0,
    }}>
      {cfg.symbol}
    </div>
  )
}
