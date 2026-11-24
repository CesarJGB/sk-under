import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router'
import { api, type FormatInfo, type Health } from '../../src/api'
import { EditorPage } from '../../src/pages/EditorPage'
import { ExportPage } from '../../src/pages/ExportPage'
import { ImportPage } from '../../src/pages/ImportPage'
import type { Draft, Session } from '../../src/session'
import '../../src/styles.css'

function FileTools() {
  const navigate = useNavigate()
  const [service, setService] = useState({ health: null as Health | null, formats: [] as FormatInfo[], loading: true })
  const [token, setToken] = useState('')
  const [session, setSession] = useState<Session | null>(null)
  const [draft, setDraft] = useState<Draft>({})

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([api.health(controller.signal), api.formats(controller.signal)]).then(([health, { formats }]) => {
      if (!controller.signal.aborted) setService({ health, formats, loading: false })
    }).catch(() => {
      if (!controller.signal.aborted) setService({ health: null, formats: [], loading: false })
    })
    return () => controller.abort()
  }, [])

  function updateDraft(fieldId?: string, value?: string) {
    if (fieldId === undefined) {
      setDraft({})
      return
    }
    setDraft((previous) => {
      const next = { ...previous }
      if (value === undefined) delete next[fieldId]
      else next[fieldId] = value
      return next
    })
  }

  return <main className="shell main-content">
    <Routes>
      <Route path="/importar" element={<ImportPage {...service} retry={() => window.location.reload()}
        token={token} setToken={setToken} currentName={session?.name} onImport={(next) => {
          setSession(next)
          setDraft({})
          void navigate('/editor')
        }} />} />
      <Route path="/editor" element={<EditorPage session={session} draft={draft} update={updateDraft} />} />
      <Route path="/exportar" element={<ExportPage session={session} draft={draft} token={token.trim()} />} />
    </Routes>
  </main>
}

createRoot(document.getElementById('root')!).render(
  <MemoryRouter initialEntries={['/importar']}>
    <FileTools />
  </MemoryRouter>,
)
