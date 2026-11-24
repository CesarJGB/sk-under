import { CloudDownload } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import {
  ApiProblem, cloudAccounts,
  type AccountBackup, type AccountSave, type CloudAccount, type CloudAccounts,
  type LabPrepared, type LabVerification, type LabWriteResult,
} from '../api'
import { formatSize } from '../session'
import { Notice, PageTitle, Problem } from '../ui'
import { useOperation } from '../useOperation'

const gemFormat = new Intl.NumberFormat('es-MX')
const dateFormat = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' })

const accountProblems: Record<string, string> = {
  cloud_grant_invalid: 'El enlace ya se usó o caducó. Solicita uno nuevo.',
  cloud_account_linked: 'Abre el enlace en el navegador donde vinculaste esta cuenta.',
  cloud_account_missing: 'La cuenta vinculada ya no está disponible.',
  cloud_browser_required: 'Vincula una cuenta en este navegador.',
  cloud_session_expired: 'La sesión caducó. Solicita un nuevo enlace para reconectar.',
  cloud_remote_changed: 'La partida cambió en la nube. Descárgala de nuevo.',
  cloud_write_disabled: 'La subida a la nube está deshabilitada.',
  cloud_already_confirmed: 'Esta edición ya se subió. Verifica su respaldo.',
}

function accountProblem(error: ApiProblem, fallback: string) {
  const message = accountProblems[error.code] ?? (error.message === 'El inicio de sesión requiere HTTPS en el editor y en la API.'
    ? error.message : fallback)
  return new ApiProblem(message, [], error.code)
}

export function CloudAccountsPage() {
  const [state, setState] = useState<CloudAccounts | null>(null)
  const [selected, setSelected] = useState('')
  const [ticket, setTicket] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('vincular'))
  const [managing, setManaging] = useState(false)
  const [authAction, setAuthAction] = useState<'login' | 'logout'>('login')
  const operation = useOperation()
  const authentication = useOperation()

  function refresh() {
    void operation.run(async (signal) => setState(await cloudAccounts.list(signal)))
  }

  useEffect(() => {
    if (ticket !== null) window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
    refresh()
  }, [])

  const account = state?.accounts.find(({ id }) => id === selected) ?? state?.accounts[0]

  function updateAccounts(next: { accounts: CloudAccount[]; session_active?: boolean }) {
    setState((previous) => previous && {
      ...previous, accounts: next.accounts, session_active: next.session_active ?? previous.session_active,
    })
  }

  function linkAccount() {
    if (!ticket) return
    void operation.run(async (signal) => {
      updateAccounts(await cloudAccounts.claim(ticket, signal))
      setTicket(null)
    })
  }

  function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!state?.password_login_available) return
    const fields = new FormData(event.currentTarget)
    event.currentTarget.reset()
    setAuthAction('login')
    void authentication.run(async (signal) => {
      updateAccounts(await cloudAccounts.login(String(fields.get('email')), String(fields.get('password')), signal))
    })
  }

  function logout() {
    if (!window.confirm('¿Cerrar sesión? Necesitarás un nuevo enlace para volver a acceder a las cuentas vinculadas.')) return
    setAuthAction('logout')
    void authentication.run(async (signal) => {
      await cloudAccounts.logout(signal)
      updateAccounts({ accounts: [], session_active: false })
      setSelected('')
      setManaging(false)
      setTicket(null)
    })
  }

  const pending = operation.pending || authentication.pending

  return <>
    <PageTitle title="Cuentas vinculadas" />
    <div className="lab-shell account-shell linked-shell">
      <section className="lab-card" aria-labelledby="accounts-title">
        <div className="lab-card-head">
          <div><h2 id="accounts-title">Mis cuentas</h2>{account && <p>Android Global · {account.connected ? 'Sesión vigente' : 'Reconexión necesaria'}</p>}</div>
        </div>
        {state?.message && <Notice tone="warning">El acceso a cuentas vinculadas no está disponible en este momento.</Notice>}
        {operation.pending && <p role="status">Consultando cuentas…</p>}
        {operation.problem && <><Problem problem={accountProblem(operation.problem, 'No se pudo completar la operación de la cuenta.')} />
          <button className="button lab-quiet" type="button" onClick={refresh}>Actualizar cuentas</button></>}
        {ticket && <div className="lab-actions">
          <button className="button lab-primary" type="button" onClick={linkAccount}
            disabled={!state?.configured || pending}>Vincular cuenta del enlace</button>
          <button className="button lab-quiet" type="button" onClick={() => setTicket(null)}>Cancelar</button>
        </div>}
        {(state?.session_active ?? Boolean(account)) && <div className="lab-actions">
          <button className="button lab-quiet" type="button" disabled={pending} onClick={logout}>
            {authentication.pending && authAction === 'logout' ? 'Cerrando sesión…' : 'Cerrar sesión'}
          </button>
        </div>}
        {authentication.problem && <Problem problem={accountProblem(authentication.problem, 'No se pudo completar el acceso a la cuenta.')} />}
        {account && <>
          <label className="lab-field"><span>Cuenta seleccionada</span>
            <select className="lab-input" value={account.id} onChange={(event) => {
              setSelected(event.target.value)
              setManaging(false)
            }}>
              {state?.accounts.map((choice) => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
            </select>
          </label>
          <div className="lab-actions">
            <button className="button lab-quiet" type="button" aria-expanded={managing}
              onClick={() => setManaging(!managing)}>Administrar cuenta</button>
          </div>
          {managing && <div className="account-management" key={account.id}>
            <form onSubmit={(event) => {
              event.preventDefault()
              const label = String(new FormData(event.currentTarget).get('label')).trim()
              if (label) void operation.run(async (signal) => updateAccounts(await cloudAccounts.account(account.id).rename(label, signal)))
            }}>
              <label className="lab-field"><span>Nombre local</span>
                <input className="lab-input" name="label" defaultValue={account.label} required maxLength={80} />
              </label>
              <button className="button lab-quiet" disabled={pending}>Guardar nombre</button>
            </form>
            <p className="lab-hint">Para reconectar, abre un nuevo enlace de esta cuenta en el mismo navegador.</p>
            <button className="button lab-quiet" type="button" disabled={pending} onClick={() => {
              if (window.confirm(`¿Desvincular ${account.label} de este navegador?`)) {
                void operation.run(async (signal) => {
                  updateAccounts(await cloudAccounts.account(account.id).unlink(signal))
                  setManaging(false)
                })
              }
            }}>Desvincular</button>
          </div>}
        </>}
        <details className="account-details" open={!account || undefined}>
          <summary>Agregar cuenta</summary>
          <form onSubmit={login}>
            <label className="lab-field"><span>Plataforma</span>
              <select className="lab-input" defaultValue="android-global" name="platform">
                <option value="android-global">Android Global</option>
                <option value="ios" disabled>iOS · No disponible</option>
              </select>
            </label>
            <p className="lab-hint" role="status">{state?.login_message ?? (operation.problem
              ? 'El estado del inicio de sesión no se pudo consultar.'
              : 'Comprobando el inicio de sesión…')}</p>
            <fieldset className="account-credentials" disabled={!state?.password_login_available || pending}>
              <label className="lab-field"><span>Correo electrónico de ChillyRoom</span>
                <input className="lab-input" name="email" type="email" inputMode="email" autoComplete="username" required />
              </label>
              <label className="lab-field"><span>Contraseña</span>
                <input className="lab-input" name="password" type="password" autoComplete="current-password" required />
              </label>
              <button className="button lab-primary">
                {authentication.pending && authAction === 'login' ? 'Iniciando sesión…' : 'Iniciar sesión'}
              </button>
            </fieldset>
            {state?.configured && !state.password_login_available && <p className="lab-hint">
              Si recibiste un enlace privado de vinculación, ábrelo en el navegador donde usarás el editor.
            </p>}
          </form>
        </details>
      </section>

      {state && account ? <AccountEditor key={account.id} account={account} limits={state}
        serverWriteEnabled={state.write_enabled} onExpired={refresh} /> : null}
    </div>
    <Link className="cloud-text-link justify-self-start" to="/partida">Volver a Partida</Link>
  </>
}

function AccountEditor({ account, limits, serverWriteEnabled, onExpired }: {
  account: CloudAccount
  limits: Pick<CloudAccounts, 'min_gems' | 'max_gems'>
  serverWriteEnabled?: boolean
  onExpired: () => void
}) {
  const [save, setSave] = useState<AccountSave | null>(null)
  const [newGems, setNewGems] = useState('')
  const [candidate, setCandidate] = useState<LabPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [history, setHistory] = useState<AccountBackup[]>([])
  const [backupResult, setBackupResult] = useState<(LabWriteResult | LabVerification) | null>(null)
  const operation = useOperation()
  const historyOperation = useOperation()
  const backupOperation = useOperation()
  const editor = cloudAccounts.account(account.id)

  async function refreshHistory(signal: AbortSignal) {
    setHistory((await editor.backups(signal)).backups)
  }

  function run(task: (signal: AbortSignal) => Promise<unknown>, action = operation) {
    void action.run(async (signal) => {
      try {
        await task(signal)
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem &&
          ['cloud_session_expired', 'cloud_browser_required'].includes(error.code ?? '')) onExpired()
        throw error
      }
    })
  }

  useEffect(() => { void historyOperation.run(refreshHistory) }, [])

  const amount = /^\d+$/.test(newGems) ? Number(newGems) : Number.NaN
  const valid = Number.isSafeInteger(amount) && amount >= limits.min_gems && amount <= limits.max_gems
  const disabled = operation.pending || backupOperation.pending || !account.connected

  function clearPreview() {
    setCandidate(null)
    setConfirm(false)
    setResult(null)
  }

  return <>
    <section className="lab-card" aria-labelledby="save-title">
      <div className="lab-card-head">
        <h2 id="save-title">Partida en la nube</h2>
      </div>
      {!account.connected && <Notice tone="warning">La sesión caducó. Solicita un nuevo enlace privado para reconectar.</Notice>}
      {account.connected && !account.write_ready && <Notice tone="warning">{serverWriteEnabled === false
        ? 'La escritura está deshabilitada en el servidor.'
        : 'Esta cuenta está autorizada para lectura.'}</Notice>}
      <button className="button lab-primary" disabled={disabled} onClick={() => run(async (signal) => {
        clearPreview()
        setSave(null)
        const downloaded = await editor.save(signal)
        setSave(downloaded)
        setNewGems(String(downloaded.gems))
      })}><CloudDownload size={18} aria-hidden="true" /> Descargar partida</button>
      {save && <>
        <div className="lab-save">
          <div className="lab-metric"><span>Gemas descargadas</span><strong data-testid="cloud-current-gems">{gemFormat.format(save.gems)}</strong></div>
          <dl className="lab-facts">
            <div><dt>Descarga</dt><dd>{dateFormat.format(new Date(save.downloaded_at))}</dd></div>
            <div><dt>Verificación</dt><dd>Copia validada</dd></div>
          </dl>
        </div>
        <form onSubmit={(event) => {
          event.preventDefault()
          if (!valid) return
          run(async (signal) => {
            clearPreview()
            setCandidate(await editor.prepare(amount, save.sha256, signal))
            void historyOperation.run(refreshHistory)
          })
        }}>
          <label className="lab-field"><span>Nueva cantidad de gemas</span>
            <input className="lab-input" inputMode="numeric" value={newGems} disabled={disabled}
              aria-invalid={!valid} onChange={(event) => {
                setNewGems(event.target.value)
                clearPreview()
              }} />
            <small>Entero entre {gemFormat.format(limits.min_gems)} y {gemFormat.format(limits.max_gems)}.</small>
          </label>
          <button className="button lab-quiet" disabled={disabled || !valid || amount === save.gems}>Preparar edición</button>
        </form>
      </>}
      {candidate && <div className="account-preview">
        <dl className="lab-facts">
          <div><dt>Gemas actuales</dt><dd>{gemFormat.format(candidate.original_gems)}</dd></div>
          <div><dt>Gemas nuevas</dt><dd>{gemFormat.format(candidate.new_gems)}</dd></div>
          <div><dt>Cambio</dt><dd>{new Intl.NumberFormat('es-MX', { signDisplay: 'exceptZero' }).format(candidate.new_gems - candidate.original_gems)}</dd></div>
          <div><dt>Respaldo original</dt><dd>{formatSize(candidate.backup.original_size)}</dd></div>
        </dl>
        <p className="lab-hint">La edición solo cambia las gemas.</p>
        {account.write_ready && !result && <>
          <label className="lab-check"><input type="checkbox" checked={confirm} disabled={disabled}
            onChange={(event) => setConfirm(event.target.checked)} />
            <span>Confirmo que quiero sobrescribir la partida de {account.label}.</span>
          </label>
          <button className="button lab-primary" disabled={disabled || !confirm || !candidate.changed} onClick={() => run(async (signal) => {
            setConfirm(false)
            setResult(await editor.confirm(candidate.backup.id, candidate.candidate_sha256, signal))
            void historyOperation.run(refreshHistory)
          })}>Subir y verificar</button>
        </>}
      </div>}
      {result && <div role="status" className={`lab-banner ${result.persisted ? 'success' : 'warn'}`}>
        {result.persisted ? 'Cambios guardados y verificados en la nube.' : 'No se pudo confirmar la subida. Verifica el respaldo.'}
      </div>}
      {operation.pending && <p role="status">Operación en curso…</p>}
      {operation.problem && <Problem problem={accountProblem(operation.problem, 'No se pudo completar la operación de la partida.')} />}
    </section>

    <section className="lab-card" aria-labelledby="backups-title">
      <div className="lab-card-head">
        <h2 id="backups-title">Respaldos</h2>
      </div>
      {historyOperation.pending && <p role="status">Cargando respaldos…</p>}
      {historyOperation.problem && <><Problem problem={accountProblem(historyOperation.problem, 'No se pudieron cargar los respaldos.')} />
        <button className="button lab-quiet" onClick={() => void historyOperation.run(refreshHistory)}>Actualizar respaldos</button>
      </>}
      {history.length === 0 && !historyOperation.pending && !historyOperation.problem && <p>No hay respaldos de esta cuenta.</p>}
      {history.map((backup) => <details className="account-details" key={backup.id}>
        <summary>{dateFormat.format(new Date(backup.created_at))} · {gemFormat.format(backup.original_gems)} → {gemFormat.format(backup.candidate_gems)}</summary>
        <p>{backup.confirmed ? 'Subida verificada' : 'Copia preparada'} · {formatSize(backup.original_size)}</p>
        <div className="lab-actions">
          <button className="button lab-quiet" disabled={disabled} onClick={() => {
            setBackupResult(null)
            run(async (signal) => setBackupResult(await editor.verify(backup.id, signal)), backupOperation)
          }}>Verificar nube</button>
          {account.write_ready && backup.changed && <button className="button lab-quiet" disabled={disabled} onClick={() => {
            if (window.confirm(`¿Restaurar el respaldo de ${account.label} con ${gemFormat.format(backup.original_gems)} gemas?`)) {
              setBackupResult(null)
              run(async (signal) => {
                setBackupResult(await editor.restore(backup.id, signal))
                setSave(null)
                clearPreview()
              }, backupOperation)
            }
          }}>Restaurar respaldo</button>}
        </div>
        {backupResult?.backup_id === backup.id && <p role="status">{backupResult.message}</p>}
      </details>)}
      {backupOperation.pending && <p role="status">Consultando la nube…</p>}
      {backupOperation.problem && <Problem problem={accountProblem(backupOperation.problem, 'No se pudo completar la operación del respaldo.')} />}
    </section>
  </>
}
