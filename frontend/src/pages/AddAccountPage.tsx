import { useNavigate } from 'react-router'
import type { NativeSession } from '../api'
import { useAccounts } from '../AccountContext'
import { SimpleTopbar } from '../Brand'
import { Loading, PageTitle, Problem } from '../ui'
import { AccountLoginForm } from './AccountLoginForm'

export function AddAccountPage() {
  const { config, loading, problem, reload } = useAccounts()
  const navigate = useNavigate()

  function added(session: NativeSession) {
    void reload()
    navigate(`/cuentas/${session.account_id || 'primary'}/partida`, { replace: true })
  }

  return <>
    <SimpleTopbar />
    <main id="content" className="shell main-content dashboard">
      <PageTitle title="Añadir cuenta" />
      {loading && !config ? <Loading>Comprobando el acceso…</Loading>
        : problem || !config ? <>
          {problem ? <Problem problem={problem} />
            : <p className="partida-muted">No se pudo cargar la configuración. Vuelve a intentarlo.</p>}
          <button className="button quiet" type="button" onClick={() => void reload()}>Reintentar</button>
        </>
          : config.available === false
            ? <section className="cloud-empty panel">
              <h2>Servicio temporalmente no disponible</h2>
              <button className="button quiet" type="button" onClick={() => void reload()}>Reintentar</button>
            </section>
            : <AccountLoginForm config={config} onSuccess={added} onCancel={() => navigate('/')} />}
    </main>
  </>
}