// ─── BobIA — ambiente do funcionário ──────────────────────────────────────
// Professional sidebar-based shell for internal/admin experience.

import { useNavigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { t, Spinner } from '../components/ui'
import { useHealth } from '../hooks/useHealth'
import RoleTransitionOverlay from '../components/RoleTransitionOverlay'
import NavIcon, { type NavIconName } from '../components/NavIcon'

interface AdminLayoutProps {
  children: ReactNode
}

const ADMIN_NAV = [
  { to: '/admin',          label: 'Visão geral',   icon: 'overview' as NavIconName, end: true },
  { to: '/admin/clients',  label: 'Clientes',      icon: 'clients' as NavIconName },
  { to: '/admin/audit',    label: 'Auditoria',     icon: 'audit' as NavIconName },
  { to: '/admin/metrics',  label: 'Métricas',      icon: 'metrics' as NavIconName },
  { to: '/admin/scenarios',label: 'Demonstração',  icon: 'demo' as NavIconName },
]

export default function AdminLayout({ children }: AdminLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { data: health, loading: healthLoading } = useHealth()
  const [switchingRole, setSwitchingRole] = useState(false)
  const openClient = () => {
    if (switchingRole) return
    setSwitchingRole(true)
    window.setTimeout(() => navigate('/bank'), 520)
  }

  return (
    <div className="admin-shell" style={{
      minHeight: '100vh',
      background: 'transparent',
      fontFamily: t.font,
      display: 'flex',
    }}>
      {/* Sidebar */}
      <aside className="admin-sidebar" style={{
        width: 220,
        background: t.primary,
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        position: 'sticky',
        top: 0,
        height: '100vh',
        overflowY: 'auto',
      }}>
        {/* Logo */}
        <div
          style={{ padding: '20px 16px 16px', cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.1)' }}
          onClick={() => navigate('/admin')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 7,
              background: 'rgba(255,255,255,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, fontWeight: 800, color: '#fff',
            }}>
              B
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 15, color: '#fff', letterSpacing: '-0.2px', lineHeight: 1.1 }}>
                BobIA Bank
              </div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginTop: 1 }}>
                Ambiente do funcionário
              </div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 0' }}>
          {ADMIN_NAV.map(item => {
            const active = item.end
              ? location.pathname === item.to
              : location.pathname.startsWith(item.to)
            return (
              <button
                key={item.to}
                onClick={() => navigate(item.to)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  width: '100%',
                  padding: '9px 16px',
                  background: active ? 'rgba(255,255,255,0.15)' : 'transparent',
                  color: active ? '#fff' : 'rgba(255,255,255,0.65)',
                  border: 'none',
                  borderLeft: active ? '3px solid rgba(255,255,255,0.7)' : '3px solid transparent',
                  cursor: 'pointer',
                  fontFamily: t.font,
                  fontSize: 13,
                  fontWeight: active ? 700 : 500,
                  textAlign: 'left',
                  transition: 'background 0.15s, color 0.15s',
                }}
              >
                <NavIcon name={item.icon} size={16} />
                {item.label}
              </button>
            )
          })}
        </nav>

        {/* Divider */}
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', padding: '12px 16px' }}>
          <button
            onClick={openClient}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              width: '100%', background: 'transparent', border: 'none',
              color: 'rgba(255,255,255,0.55)', cursor: 'pointer',
              fontFamily: t.font, fontSize: 12, padding: '6px 0',
            }}
          >
            ← Alternar para cliente
          </button>
        </div>

        {/* API Status */}
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
            {healthLoading
              ? <Spinner size={10} color="rgba(255,255,255,0.5)" />
              : <span style={{
                  width: 7, height: 7, borderRadius: '50%',
                  background: health?.status === 'ok' ? '#4ade80' : '#f87171',
                  display: 'inline-block', flexShrink: 0,
                }} />
            }
            <span style={{ color: 'rgba(255,255,255,0.55)' }}>
              {healthLoading ? 'Conectando…' : health?.status === 'ok' ? 'API online' : 'API offline'}
            </span>
          </div>
          {health && !healthLoading && (
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 3 }}>
              Sistema conectado · v{health.version}
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top bar */}
        <div className="admin-topbar" style={{
          background: t.surface,
          borderBottom: `1px solid ${t.border}`,
          padding: '0 24px',
          height: 52,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}>
          <button className="admin-mobile-switch" onClick={openClient} style={{ border: 0, background: t.primaryLight, color: t.primaryHover, borderRadius: 999, padding: '7px 10px', fontWeight: 800, cursor: 'pointer' }}>
            ← Cliente
          </button>
          <div className="admin-context" style={{ fontSize: 13, color: t.textMuted }}>
            <span style={{ color: t.accent, fontWeight: 700 }}>Conta funcionário</span>
            <span className="admin-context-detail"> · análise humana · dados sintéticos</span>
          </div>
          <div className="admin-prototype" style={{
            background: '#fff3cd',
            border: '1px solid #ffc107',
            borderRadius: 4,
            padding: '3px 10px',
            fontSize: 11,
            color: '#664d03',
            fontWeight: 600,
          }}>
            PROTÓTIPO
          </div>
        </div>

        {/* Page content */}
        <main className="admin-main-content" style={{ flex: 1, padding: '24px', overflow: 'auto' }}>
          {children}
        </main>
      </div>
      {switchingRole && <RoleTransitionOverlay target="client" />}
    </div>
  )
}
