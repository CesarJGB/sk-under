import { Download, FilePenLine, FileUp, Gem, House, ScanLine } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router'
import { api, type FormatInfo, type Health } from './api'
import { EditorPage } from './pages/EditorPage'
import { ExportPage } from './pages/ExportPage'
import { HomePage } from './pages/HomePage'
import { ImportPage } from './pages/ImportPage'
import { LabEditorPage } from './pages/LabEditorPage'
import { CloudAccountsPage } from './pages/CloudAccountsPage'
import type { Draft, Session } from './session'
import { PageTitle } from './ui'

const navigation = [
  { path: '/', label: 'Inicio', icon: House },
  { path: '/importar', label: 'Importar', icon: FileUp },
  { path: '/partida', label: 'Partida', icon: Gem },
  { path: '/editor', label: 'Editor', icon: FilePenLine },
  { path: '/exportar', label: 'Exportar', icon: Download },
]

function useService() {
  const [refresh, setRefresh] = useState(0)
  const [result, setResult] = useState<{ health: Health | null; formats: FormatInfo[]; revision: number }>({
    health: null, formats: [], revision: -1,
  })

  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 8_000)
    let active = true
    void Promise.allSettled([api.health(controller.signal), api.formats(controller.signal)]).then(([health, formats]) => {
      if (!active) return
      window.clearTimeout(timeout)
      setResult({
        health: health.status === 'fulfilled' && health.value.status === 'ok' ? health.value : null,
        formats: formats.status === 'fulfilled' && Array.isArray(formats.value.formats) ? formats.value.formats : [],
        revision: refresh,
      })
    })
    return () => {
      active = false
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [refresh])

  return {
    health: result.health,
    formats: result.formats,
    loading: refresh !== result.revision,
    retry: () => setRefresh((revision) => revision + 1),
  }
}

export default function App() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const main = useRef<HTMLElement>(null)
  const service = useService()
  const [token, setToken] = useState('')
  const [adminToken, setAdminToken] = useState('')
  const [session, setSession] = useState<Session | null>(null)
  const [draft, setDraft] = useState<Draft>({})

  useEffect(() => {
    window.scrollTo(0, 0)
    main.current?.focus({ preventScroll: true })
  }, [pathname])

  function importSession(next: Session) {
    setSession(next)
    setDraft({})
    void navigate('/editor')
  }

  function updateDraft(fieldId?: string, value?: string) {
    if (fieldId === undefined) {
      setDraft({})
    } else {
      setDraft((previous) => {
        const next = { ...previous }
        if (value === undefined) delete next[fieldId]
        else next[fieldId] = value
        return next
      })
    }
  }

  return (
    <>
      <a className="skip-link" href="#content">Saltar al contenido</a>
      <header className="topbar">
        <div className="shell topbar-inner">
          <Link to="/" className="brand">
            <span className="brand-icon"><ScanLine size={23} aria-hidden="true" /></span>
            Soul Knight Editor
          </Link>
          <span className="header-note">Copias locales</span>
        </div>
      </header>
      <div className="nav-shell">
        <nav className="shell navigation" aria-label="Flujo de edición">
          {navigation.map(({ path, label, icon: Icon }) => (
            <NavLink key={path} to={path} end className="nav-link">
              <Icon size={17} aria-hidden="true" />{label}
            </NavLink>
          ))}
        </nav>
      </div>
      <main id="content" ref={main} tabIndex={-1} className="shell main-content">
        <Routes>
          <Route path="/" element={<HomePage {...service} />} />
          <Route path="/importar" element={<ImportPage {...service} token={token} setToken={setToken}
            currentName={session?.name} onImport={importSession} />} />
          <Route path="/editor" element={<EditorPage session={session} draft={draft} update={updateDraft} />} />
          <Route path="/partida" element={<CloudAccountsPage />} />
          <Route path="/partida/laboratorio" element={<LabEditorPage token={token} setToken={setToken}
            adminToken={adminToken} setAdminToken={setAdminToken} health={service.health}
            loading={service.loading} />} />
          <Route path="/exportar" element={<ExportPage session={session} draft={draft} token={token.trim()} />} />
          <Route path="*" element={<>
            <PageTitle title="Página no encontrada">Usa la navegación para volver al flujo de edición.</PageTitle>
            <Link className="button primary" to="/">Volver a inicio</Link>
          </>} />
        </Routes>
      </main>
    </>
  )
}
