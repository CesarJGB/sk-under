import { Activity, FileUp, FlaskConical, RotateCw, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'
import type { FormatInfo, Health } from '../api'
import { formatSize } from '../session'
import { Notice } from '../ui'

export function HomePage({ health, formats, loading, retry }: {
  health: Health | null
  formats: FormatInfo[]
  loading: boolean
  retry: () => void
}) {
  const status = loading ? 'Comprobando conexión' : health ? 'API en línea' : 'API sin conexión'
  const access = health?.access_mode === 'token' ? 'Acceso con token'
    : health?.access_mode === 'local' ? 'Modo de pruebas local' : 'Importación deshabilitada'

  return (
    <>
      <section className="hero">
        <div className="hero-content">
          <h1>Editor de partidas</h1>
          <p>Importa una copia local, revisa los campos que reconoce el editor y descarga el archivo resultante.</p>
          <Link className="button hero-button" to="/importar"><FileUp size={19} />Importar archivo</Link>
        </div>
        <section className="service-card" aria-label="Estado de la API">
          <div className="service-heading"><Activity size={17} aria-hidden="true" />Estado del servicio</div>
          <div className="service-status" role="status">
            <span className={`status-dot ${health && !loading ? 'online' : ''}`} aria-hidden="true" />
            {status}
          </div>
          {health && !loading && (
            <div className="service-meta">
              <span>{access}</span>
              <span>Hasta {formatSize(health.max_file_bytes)} por archivo</span>
            </div>
          )}
          {!loading && (!health || formats.length === 0) && (
            <button className="retry" type="button" onClick={retry}><RotateCw size={15} />Actualizar</button>
          )}
        </section>
      </section>

      <section className="formats-section" aria-labelledby="formats-title">
        <h2 id="formats-title">Formatos admitidos</h2>
        {formats.length > 0 ? (
          <div className="grid gap-3">
            {formats.map((format) => (
              <article className="panel format-card" key={format.id}>
                <div className="icon-tile"><FlaskConical size={22} aria-hidden="true" /></div>
                <div className="min-w-0 flex-1">
                  <h3>{format.name}</h3>
                  <p>{format.description}</p>
                </div>
                <span className="format-tag">{format.extensions.join(' · ')} / {format.compatibility === 'synthetic' ? `v${format.version}` : format.version}</span>
              </article>
            ))}
          </div>
        ) : (
          <Notice>{loading ? 'Consultando formatos admitidos…' : 'La lista de formatos no está disponible.'}</Notice>
        )}
        {!formats.some((format) => format.compatibility !== 'synthetic') && (
          <Notice tone="warning">Este servicio solo tiene habilitada la muestra sintética.</Notice>
        )}
      </section>
      <p className="privacy-note home-privacy">
        <ShieldCheck size={19} aria-hidden="true" />
        <span>La API procesa las copias en memoria y el archivo original queda intacto.</span>
      </p>
    </>
  )
}
