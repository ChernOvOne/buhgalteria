import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAuthStore } from '@/store'
import { Shell } from '@/components/layout'
import { Spinner } from '@/components/ui'

import LoginPage     from '@/pages/Login'
import OnboardingPage from '@/pages/Onboarding'
import Dashboard     from '@/pages/Dashboard'
import { TransactionsPage } from '@/pages/Transactions'
import PartnersPage  from '@/pages/Partners'
import ServersPage   from '@/pages/Servers'
import AdsPage       from '@/pages/Ads'
import InkasPage     from '@/pages/Inkas'
import ReportsPage   from '@/pages/Reports'
import SettingsPage  from '@/pages/Settings'
import PaymentsPage  from '@/pages/Payments'

function AppShell() {
  return (
    <AuthGuard>
      <Shell>
        <Routes>
          <Route path="/"         element={<Dashboard />} />
          <Route path="/income"   element={<TransactionsPage typeFixed="income" />} />
          <Route path="/expenses" element={<TransactionsPage typeFixed="expense" />} />
          <Route path="/ads"      element={<AdsPage />} />
          <Route path="/servers"  element={<ServersPage />} />
          <Route path="/partners" element={<PartnersPage />} />
          <Route path="/inkas"    element={<InkasPage />} />
          <Route path="/payments" element={<PaymentsPage />} />
          <Route path="/reports"  element={<ReportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*"         element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </AuthGuard>
  )
}

export default function App() {
  const { token, fetchMe } = useAuthStore()

  useEffect(() => {
    if (token) fetchMe()
    else useAuthStore.setState({ loading: false })
  }, [])

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#fff',
            color: '#2C2C2A',
            border: '0.5px solid #D3D1C7',
            borderRadius: '10px',
            fontSize: '13px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          },
          success: { iconTheme: { primary: '#1D9E75', secondary: '#fff' } },
          error:   { iconTheme: { primary: '#E24B4A', secondary: '#fff' } },
        }}
      />
      <Routes>
        <Route path="/login"      element={<LoginPage />} />
        <Route path="/onboarding" element={<AuthGuard><OnboardingPage /></AuthGuard>} />
        <Route path="/*"          element={<AppShell />} />
      </Routes>
    </BrowserRouter>
  )
}

function AuthGuard({ children }) {
  const { user, token, loading } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && user && user.onboarding_done === false && window.location.pathname !== '/onboarding') {
      navigate('/onboarding')
    }
  }, [user, loading])

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <Spinner size={32} />
    </div>
  )
  if (!token || !user) return <Navigate to="/login" replace />
  return children
}
