import { Link } from 'react-router'
import { Loading } from '../ui'

type HomeState =
  | { loading: boolean; unavailable: boolean; retry: () => void; account?: undefined }
  | { loading?: false; unavailable?: false; retry?: undefined; account: { label: string; platform?: string; saveStatus: string } }

export function HomePage({ loading, unavailable, retry, account }: HomeState) {
  const connection = loading ? 'Comprobando conexión'
    : account ? 'Cuenta conectada'
      : unavailable ? 'Servicio temporalmente no disponible' : 'Cuenta desconectada'

  return <>
    <div className="page-title cloud-title"><h1>Inicio</h1></div>
    <section className="home-summary" aria-labelledby="home-save-title">
      <div>
        {loading ? <Loading>{connection}</Loading> : <p className="home-connection">
          <span className={account ? 'connection-dot online' : 'connection-dot'} aria-hidden="true" />
          {connection}
        </p>}
        <h2 id="home-save-title">Partida en la nube</h2>
        {account ? <div className="home-account">
          <strong>{account.label}</strong>
          {account.platform && <span>{account.platform}</span>}
        </div> : null}
        {unavailable && !loading && <p className="home-account">Vuelve a intentar la conexión en unos minutos.</p>}
      </div>
      <div className="home-action">
        {account && <p role="status">{account.saveStatus}</p>}
        {account && <Link className="button home-primary" to="/partida">Abrir partida</Link>}
        {!account && unavailable && !loading && <button className="button home-primary" onClick={retry}>Reintentar</button>}
        {!account && !unavailable && !loading && <Link className="button home-primary" to="/partida">Conectar cuenta</Link>}
      </div>
    </section>
  </>
}
