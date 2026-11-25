import { Cloud, FilePenLine, House, ScanLine } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, matchPath, Navigate, NavLink, Route, Routes, useLocation } from 'react-router'
import { api, type Health } from './api'
import { LabEditorPage } from './pages/LabEditorPage'
import { CloudAccountsPage } from './pages/CloudAccountsPage'
import { NativeAuthPage } from './pages/NativeAuthPage'
import { PageTitle } from './ui'

const navigation = [
  { path: '/', label: 'Inicio', icon: House, view: 'home' },
  { path: '/partida', label: 'Partida', icon: Cloud, view: 'save' },
  { path: '/editor', label: 'Editor', icon: FilePenLine, view: 'editor' },
] as const

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

export default function App() {
  const { pathname } = useLocation()
  const main = useRef<HTMLElement>(null)
  const view = pathname === '/editor' || pathname.startsWith('/editor/')
    ? 'editor'
    : navigation.find(({ path }) => matchPath(path, pathname))?.view

  useEffect(() => {
    window.scrollTo(0, 0)
    if (view !== 'editor' || !main.current?.contains(document.activeElement)) {
      main.current?.focus({ preventScroll: true })
    }
  }, [pathname, view])

  return <>
    <a className="skip-link" href="#content">Saltar al contenido</a>
    {view !== 'editor' && <header className="topbar">
      <div className="shell topbar-inner">
        <Link to="/" className="brand">
          <span className="brand-icon"><ScanLine size={22} aria-hidden="true" /></span>
          SK-Under
        </Link>
        <nav className="navigation" aria-label="Navegación principal">
          {navigation.map(({ path, label, icon: Icon }) => (
            <NavLink key={path} to={path} end={path === '/'} className="nav-link">
              <Icon size={17} aria-hidden="true" />{label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>}
    <main id="content" ref={main} tabIndex={-1}
      className={`shell main-content${view === 'editor' ? ' main-editor' : view === 'save' ? ' main-partida' : ''}`}>
      {view ? <NativeAuthPage view={view} /> : <Routes>
        <Route path="/partida/vinculadas" element={<CloudAccountsPage />} />
        <Route path="/partida/laboratorio" element={<LabRoute />} />
        <Route path="/importar" element={<Navigate to="/partida" replace />} />
        <Route path="/exportar" element={<Navigate to="/partida" replace />} />
        <Route path="*" element={<>
          <PageTitle title="Página no encontrada" />
          <Link className="button primary" to="/">Volver a Inicio</Link>
        </>} />
      </Routes>}
    </main>
  </>
}
