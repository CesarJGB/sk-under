import { useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, matchPath, useLocation } from 'react-router'
import { api, type Health } from './api'
import { AccountsProvider, useAccounts } from './AccountContext'
import { SimpleTopbar } from './Brand'
import { DashboardPage } from './pages/DashboardPage'
import { AddAccountPage } from './pages/AddAccountPage'
import { AccountPage } from './pages/AccountPage'
import { CloudAccountsPage } from './pages/CloudAccountsPage'
import { LabEditorPage } from './pages/LabEditorPage'
import { Loading, PageTitle } from './ui'

function LabRoute() {
  const [health, setHealth] = useState<Health | null>(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState('')
  const [adminToken, setAdminToken] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 8_000)
    let active = true
    void api.health(controller.signal).then((next) => {
      if (active && next.status === 'ok') setHealth(next)
    }).catch(() => undefined).finally(() => {
      window.clearTimeout(timeout)
      if (active) setLoading(false)
    })
    return () => {
      active = false
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [])

  return <LabEditorPage token={token} setToken={setToken} adminToken={adminToken}
    setAdminToken={setAdminToken} health={health} loading={loading} />
}

function LegacyAccountRoute({ kind }: { kind: 'partida' | 'editor' }) {
  const { accounts, loading } = useAccounts()
  const { pathname, search } = useLocation()

  if (loading && accounts.length === 0) return <Loading>Comprobando las cuentas…</Loading>
  if (accounts.length === 0) return <Navigate to="/cuentas/nueva" replace />
  if (accounts.length > 1) return <Navigate to="/" replace />
  const account = accounts[0]
  const suffix = kind === 'editor' ? pathname.replace(/^\/editor/, '') : ''
  return <Navigate to={`/cuentas/${account.id}/${kind}${suffix}${search}`} replace />
}

function NotFound() {
  return <>
    <SimpleTopbar />
    <main id="content" className="shell main-content">
      <PageTitle title="Página no encontrada" />
      <Link className="button primary" to="/">Volver al inicio</Link>
    </main>
  </>
}

function RouteScroll() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  const { pathname } = useLocation()
  const accountMatch = matchPath('/cuentas/:accountId/*', pathname)
  const inAccount = Boolean(accountMatch && accountMatch.params.accountId !== 'nueva')
  return <AccountsProvider>
    <a className="skip-link" href="#content">Saltar al contenido</a>
    <RouteScroll />
    {inAccount ? <AccountPage /> : <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/cuentas/nueva" element={<AddAccountPage />} />
      <Route path="/partida/vinculadas" element={<>
        <SimpleTopbar />
        <main id="content" className="shell main-content"><CloudAccountsPage /></main>
      </>} />
      <Route path="/partida/laboratorio" element={<>
        <SimpleTopbar />
        <main id="content" className="shell main-content"><LabRoute /></main>
      </>} />
      <Route path="/partida/*" element={<main id="content" className="shell main-content"><LegacyAccountRoute kind="partida" /></main>} />
      <Route path="/editor/*" element={<main id="content" className="shell main-content"><LegacyAccountRoute kind="editor" /></main>} />
      <Route path="/importar" element={<Navigate to="/partida" replace />} />
      <Route path="/exportar" element={<Navigate to="/partida" replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>}
  </AccountsProvider>
}