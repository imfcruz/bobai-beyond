import type { ReactNode } from 'react'

export type NavIconName =
  | 'home' | 'pix' | 'card' | 'contacts' | 'statement' | 'employee'
  | 'overview' | 'clients' | 'audit' | 'metrics' | 'demo'

export default function NavIcon({ name, size = 18 }: { name: NavIconName; size?: number }) {
  const paths: Record<NavIconName, ReactNode> = {
    home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/><path d="M9.5 20v-6h5v6"/></>,
    pix: <><path d="m8 3 4 4-4 4-4-4 4-4Z"/><path d="m16 13 4 4-4 4-4-4 4-4Z"/><path d="m16 3 4 4-4 4-4-4 4-4Z"/><path d="m8 13 4 4-4 4-4-4 4-4Z"/></>,
    card: <><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 10h18"/><path d="M7 15h3"/></>,
    contacts: <><circle cx="9" cy="8" r="3"/><path d="M3.5 20c.4-4 2.2-6 5.5-6s5.1 2 5.5 6"/><path d="M16 7h5M18.5 4.5v5"/></>,
    statement: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/></>,
    employee: <><circle cx="12" cy="8" r="3"/><path d="M5.5 21c.5-4.5 2.7-7 6.5-7s6 2.5 6.5 7"/><path d="m17 11 2 2 3-4"/></>,
    overview: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    clients: <><circle cx="8" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M2.5 20c.4-4 2.2-6 5.5-6s5.1 2 5.5 6M14 15c3.8-.5 6 1.2 6.8 5"/></>,
    audit: <><path d="M6 3h12v18H6z"/><path d="M9 8h6M9 12h6M9 16h4"/><path d="M9 3V1M15 3V1"/></>,
    metrics: <><path d="M4 20V10M10 20V4M16 20v-7M22 20V7"/><path d="M2 20h22"/></>,
    demo: <><circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4V8Z"/></>,
  }

  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
