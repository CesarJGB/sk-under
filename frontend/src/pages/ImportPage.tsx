import { Download, FileUp, KeyRound, Upload } from 'lucide-react'
import type { ChangeEvent } from 'react'
import { Link } from 'react-router'
import { api, ApiProblem, encodeFile, type FormatInfo, type Health } from '../api'
import { formatSize, type Session } from '../session'
import { Loading, Notice, PageTitle, Problem } from '../ui'
import { useOperation } from '../useOperation'

export function ImportPage({ health, formats, loading, retry, token, setToken, currentName, onImport }: {
  health: Health | null
  formats: FormatInfo[]
  loading: boolean
  retry: () => void
  token: string
  setToken: (token: string) => void
  currentName?: string
  onImport: (session: Session) => void
}) {
  const operation = useOperation()
  const extensions = [...new Set(formats.flatMap((format) => format.extensions))]
  const needsToken = health?.access_mode === 'token'
  const ready = !loading && health && health.access_mode !== 'disabled' && extensions.length > 0
  const allowSelection = ready && (!needsToken || token.trim()) && !operation.pending
  const rules = [extensions.join(' · '), health && `máximo ${formatSize(health.max_file_bytes)}`].filter(Boolean).join(' · ')
  const hasDemo = formats.some((format) => format.id === 'sk-editor-demo-v1')

  async function inspect(file: File, signal: AbortSignal): Promise<Session> {
    if (!extensions.some((extension) => file.name.toLowerCase().endsWith(extension))) {
      throw new ApiProblem(`Extensión no admitida. Selecciona un archivo ${extensions.join(' o ')}.`)
    }
    if (file.size === 0) throw new ApiProblem('El archivo está vacío.')
    if (!health || file.size > health.max_file_bytes) {
      throw new ApiProblem(`El archivo supera el límite de ${formatSize(health?.max_file_bytes ?? 0)}.`)
    }
    const content = await encodeFile(file)
    const inspection = await api.inspect(content, token.trim(), signal)
    return { name: file.name, content, inspection }
  }

  async function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return
    const session = await operation.run((signal) => inspect(file, signal))
    if (session) onImport(session)
  }

  async function tryDemo() {
    const session = await operation.run(async (signal) => {
      const response = await fetch('/ejemplo.skdemo', { signal })
      if (!response.ok) throw new ApiProblem('No se pudo cargar la muestra sintética.')
      return inspect(new File([await response.blob()], 'ejemplo.skdemo'), signal)
    })
    if (session) onImport(session)
  }

  return (
    <>
      <PageTitle title="Importar archivo">Selecciona una copia local para identificar su formato y revisar los campos admitidos.</PageTitle>
      {loading && <Loading>Consultando la API…</Loading>}
      {!loading && (!health || extensions.length === 0) && (
        <Notice tone="warning">
          <p>Se requiere conexión con la API y un formato admitido para importar.</p>
          <button className="text-button" type="button" onClick={retry}>Volver a comprobar</button>
        </Notice>
      )}
      {health?.access_mode === 'disabled' && (
        <Notice tone="warning">El administrador debe configurar el acceso privado para habilitar la importación.</Notice>
      )}
      {needsToken && (
        <div className="panel token-panel">
          <label htmlFor="access-token"><KeyRound size={17} aria-hidden="true" />Token de acceso</label>
          <input id="access-token" className="input" type="password" value={token} autoComplete="off"
            spellCheck={false} onChange={(event) => setToken(event.target.value)} disabled={operation.pending}
            aria-describedby="token-help" />
          <p id="token-help">El token se conserva en la memoria de esta pestaña.</p>
        </div>
      )}
      <section className="panel import-panel" aria-label="Selección de archivo">
        <div className="icon-tile"><Upload size={25} aria-hidden="true" /></div>
        <h2>Cargar copia local</h2>
        <p id="file-rules">{extensions.length > 0
          ? rules
          : 'Los formatos disponibles se consultan en la API.'}</p>
        <div className="file-picker">
          <input id="local-file" type="file" accept={extensions.join(',')} disabled={!allowSelection}
            onChange={selectFile} aria-describedby="file-rules" />
          <label className="button primary" htmlFor="local-file"><FileUp size={18} />Seleccionar archivo</label>
        </div>
        {operation.pending && <Loading>Inspeccionando el archivo…</Loading>}
      </section>
      {operation.problem && <Problem problem={operation.problem} />}
      {hasDemo && (
        <section className="panel demo-panel">
          <div className="min-w-0">
            <h2>Muestra sintética</h2>
            <p>Prueba el flujo completo con un archivo de demostración.</p>
          </div>
          <div className="actions">
            <button className="button secondary" type="button" disabled={!allowSelection} onClick={tryDemo}>Usar muestra</button>
            <a className="button quiet" href="/ejemplo.skdemo" download><Download size={17} />Descargar muestra</a>
          </div>
        </section>
      )}
      {currentName && (
        <p className="privacy-note">Copia abierta <strong className="wrap-anywhere">{currentName}</strong> <Link className="text-button" to="/editor">Volver al editor</Link></p>
      )}
    </>
  )
}
