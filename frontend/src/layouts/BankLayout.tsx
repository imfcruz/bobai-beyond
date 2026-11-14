import { useLocation, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { t } from '../components/ui'
import RoleTransitionOverlay from '../components/RoleTransitionOverlay'
import NavIcon, { type NavIconName } from '../components/NavIcon'

interface BankLayoutProps { children: ReactNode; clientName?: string }

const NAV = [
  { to: '/bank', label: 'Início', icon: 'home' as NavIconName, end: true },
  { to: '/bank/transfer', label: 'Pix', icon: 'pix' as NavIconName },
  { to: '/bank/cards', label: 'Cartões', icon: 'card' as NavIconName },
  { to: '/bank/contacts', label: 'Contatos', icon: 'contacts' as NavIconName },
  { to: '/bank/history', label: 'Extrato', icon: 'statement' as NavIconName },
]

export default function BankLayout({ children, clientName }: BankLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [switchingRole, setSwitchingRole] = useState(false)
  const active = (to: string, end?: boolean) => end ? location.pathname === to : location.pathname.startsWith(to)
  const openEmployee = () => {
    if (switchingRole) return
    setSwitchingRole(true)
    window.setTimeout(() => navigate('/admin'), 520)
  }

  return (
    <div className="bank-shell" style={{ fontFamily: t.font }}>
      <header style={{
        background: `linear-gradient(135deg, ${t.primary} 0%, ${t.primaryHover} 100%)`,
        color: '#fff', position: 'sticky', top: 0, zIndex: 100,
        boxShadow: '0 8px 28px rgba(51,51,189,.22)',
      }}>
        <div className="bank-header-inner">
          <button onClick={() => navigate('/bank')} aria-label="Ir para o início" style={{ background: 'transparent', color: '#fff', border: 0, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 11, padding: 0, textAlign: 'left' }}>
            <span style={{ width: 40, height: 40, borderRadius: 12, background: t.yellow, color: t.primaryHover, display: 'grid', placeItems: 'center', fontWeight: 900, fontSize: 21, transform: 'rotate(-4deg)' }}>B</span>
            <span>
              <strong style={{ display: 'block', fontSize: 18, lineHeight: 1.05, letterSpacing: '-.4px' }}>BobIA Bank</strong>
              <small style={{ opacity: .74, fontSize: 10 }}>protótipo acadêmico · dados sintéticos</small>
            </span>
          </button>

          <div className="desktop-client-nav" style={{ alignItems: 'center', gap: 4 }}>
            {NAV.map(item => (
              <button key={item.to} onClick={() => navigate(item.to)} style={{
                border: 0, borderRadius: 12, padding: '9px 12px', cursor: 'pointer',
                background: active(item.to, item.end) ? 'rgba(255,255,255,.18)' : 'transparent',
                color: '#fff', fontWeight: active(item.to, item.end) ? 700 : 500,
              }}>{item.label}</button>
            ))}
          </div>

          <div className="bank-header-actions">
            <button onClick={openEmployee} style={{ border: `1px solid ${t.yellow}`, background: t.yellow, color: t.primaryHover, borderRadius: 999, padding: '8px 13px', fontWeight: 800, cursor: 'pointer' }}>Modo funcionário</button>
            <button onClick={openEmployee} title="Alternar para funcionário" style={{ width: 38, height: 38, border: '1px solid rgba(255,255,255,.35)', background: 'rgba(255,255,255,.12)', color: '#fff', borderRadius: '50%', cursor: 'pointer', fontWeight: 800 }}>{(clientName || 'Cliente').charAt(0)}</button>
          </div>
        </div>
      </header>

      <main className="bank-main">{children}</main>

      <nav className="bank-bottom-nav" aria-label="Navegação principal">
        {NAV.map(item => (
          <button key={item.to} onClick={() => navigate(item.to)} style={{ border: 0, background: 'transparent', color: active(item.to, item.end) ? t.primary : t.textMuted, padding: '3px 1px', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, fontWeight: active(item.to, item.end) ? 800 : 600, fontSize: 10 }}>
            <NavIcon name={item.icon} size={20} />{item.label}
          </button>
        ))}
        <button onClick={openEmployee} style={{ border: 0, background: 'transparent', color: t.textMuted, padding: '3px 1px', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, fontWeight: 600, fontSize: 10 }}>
          <NavIcon name="employee" size={20} />Funcionário
        </button>
      </nav>
      {switchingRole && <RoleTransitionOverlay target="employee" />}
    </div>
  )
}
