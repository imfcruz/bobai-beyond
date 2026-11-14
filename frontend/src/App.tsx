// ─── Nexus Bank — Main Router ─────────────────────────────────────────────
// Two distinct experiences:
//   /bank/...  → Client-facing banking UI (clean, no technical data)
//   /admin/... → Administrative panel (full technical data, audit, metrics)
//
// Root / redirects to /bank for demo convenience.

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import GuidedTour from './components/GuidedTour'

// Layouts
import BankLayout from './layouts/BankLayout'
import AdminLayout from './layouts/AdminLayout'

// ── Bank (client) pages ────────────────────────────────────────────────────
import BankHomePage from './pages/bank/HomePage'
import BankTransferPage from './pages/bank/TransferPage'
import BankAnalysisPage from './pages/bank/AnalysisPage'
import BankConfirmPage from './pages/bank/ConfirmPage'
import BankHistoryPage from './pages/bank/HistoryPage'
import BankCardsPage from './pages/bank/CardsPage'
import BankContactsPage from './pages/bank/ContactsPage'

// ── Admin pages ────────────────────────────────────────────────────────────
import AdminOverviewPage from './pages/admin/OverviewPage'
import AdminAuditPage from './pages/admin/AuditPage'
import AdminReviewPage from './pages/admin/ReviewPage'
import AdminMetricsPage from './pages/admin/MetricsPage'
import AdminScenariosPage from './pages/admin/ScenariosPage'
import AdminLimitRequestsPage from './pages/admin/LimitRequestsPage'
import AdminClientsPage from './pages/admin/ClientsPage'

// ── Not found ──────────────────────────────────────────────────────────────
import { useNavigate } from 'react-router-dom'
import { t } from './components/ui'

function NotFound() {
  const navigate = useNavigate()
  return (
    <div style={{ textAlign: 'center', padding: '80px 20px', color: t.textMuted }}>
      <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>404</div>
      <h2 style={{ margin: '0 0 8px', color: t.text, fontSize: 18, fontWeight: 700 }}>Página não encontrada</h2>
      <p style={{ fontSize: 13, color: t.textMuted, marginBottom: 20 }}>A página que você procura não existe.</p>
      <button
        onClick={() => navigate('/bank')}
        style={{
          background: t.accent, color: '#fff', border: 'none',
          borderRadius: 6, padding: '9px 20px',
          fontSize: 14, fontWeight: 600, cursor: 'pointer',
          fontFamily: t.font,
        }}
      >
        ← Voltar ao início
      </button>
    </div>
  )
}

// ── Wrapper: Bank routes in BankLayout ────────────────────────────────────

function BankRoutes() {
  return (
    <BankLayout>
      <Routes>
        <Route path="/" element={<BankHomePage />} />
        <Route path="/transfer" element={<BankTransferPage />} />
        <Route path="/analysis" element={<BankAnalysisPage />} />
        <Route path="/confirm" element={<BankConfirmPage />} />
        <Route path="/history" element={<BankHistoryPage />} />
        <Route path="/cards" element={<BankCardsPage />} />
        <Route path="/contacts" element={<BankContactsPage />} />
        {/* Legacy result route: redirect to analysis with txnId in state */}
        <Route path="/result" element={<BankAnalysisPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BankLayout>
  )
}

// ── Wrapper: Admin routes in AdminLayout ─────────────────────────────────

function AdminRoutes() {
  return (
    <AdminLayout>
      <Routes>
        <Route path="/" element={<AdminOverviewPage />} />
        <Route path="/audit" element={<AdminAuditPage />} />
        <Route path="/review" element={<AdminReviewPage />} />
        <Route path="/clients" element={<AdminClientsPage />} />
        <Route path="/limit-requests" element={<AdminLimitRequestsPage />} />
        <Route path="/metrics" element={<AdminMetricsPage />} />
        <Route path="/scenarios" element={<AdminScenariosPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AdminLayout>
  )
}

// ── App ───────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Root → bank home */}
        <Route path="/" element={<Navigate to="/bank" replace />} />

        {/* Client experience */}
        <Route path="/bank/*" element={<BankRoutes />} />

        {/* Admin experience */}
        <Route path="/admin/*" element={<AdminRoutes />} />

        {/* Legacy routes: redirect to new paths */}
        <Route path="/transfer" element={<Navigate to="/bank/transfer" replace />} />
        <Route path="/analysis" element={<Navigate to="/bank/analysis" replace />} />
        <Route path="/confirm" element={<Navigate to="/bank/confirm" replace />} />
        <Route path="/audit" element={<Navigate to="/admin/audit" replace />} />
        <Route path="/human-review" element={<Navigate to="/admin/review" replace />} />
        <Route path="/metrics" element={<Navigate to="/admin/metrics" replace />} />
        <Route path="/scenarios" element={<Navigate to="/admin/scenarios" replace />} />

        <Route path="*" element={<NotFound />} />
      </Routes>
      <GuidedTour />
    </BrowserRouter>
  )
}
