import {
  CloudDownload, DatabaseBackup, Eye, EyeOff, Gem, LoaderCircle, LogOut,
  RefreshCw, ServerOff, ShieldCheck, UserRound,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import {
  ApiProblem, nativeAuth,
  type LabBackup, type LabPrepared, type LabVerification, type LabWriteResult,
  type NativeConfig, type NativeSaveSummary, type NativeSession,
} from '../api'
import { formatSize } from '../session'
import { Notice, PageTitle, Problem } from '../ui'
import { useOperation } from '../useOperation'

const gemFormat = new Intl.NumberFormat('es-MX')
const dateFormat = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' })

const FRIENDLY: Record<string, string> = {
  native_https_required: 'El inicio de sesión requiere HTTPS en el editor y en la API.',
  native_credentials_rejected: 'El correo o la contraseña no son correctos. No se reintenta automáticamente.',
  native_login_throttled: 'Demasiados intentos en poco tiempo. Espera antes de volver a intentarlo.',
  native_auth_throttled: 'El proveedor limitó temporalmente los intentos. Espera antes de reintentar.',
  native_auth_unavailable: 'El servicio de ChillyRoom no está disponible en este momento. Inténtalo más tarde.',
  native_auth_protocol: 'ChillyRoom devolvió una respuesta que no se pudo verificar.',
  native_distribution_rejected: 'El proveedor rechazó la distribución aprovisionada. Revisa el perfil de instalación.',
  native_identity_mismatch: 'La respuesta no corresponde a la cuenta solicitada. No se creó ninguna sesión.',
  native_profile_identity_mismatch: 'Ese perfil de instalación pertenece a otra cuenta y no se reutiliza.',
  native_profile_required: 'Selecciona el perfil de instalación que corresponde a esta cuenta.',
  native_profile_missing: 'La configuración de instalación está pendiente: el propietario debe aprovisionar un perfil.',
  native_installation_required: 'Completa el identificador de instalación para acceder a la partida.',
  native_portal_rejected: 'El portal de ChillyRoom rechazó las credenciales de la cuenta. Revisa el correo y la contraseña.',
  native_portal_identity_mismatch: 'El portal devolvió una cuenta o un jugador distinto. No se creó ninguna sesión.',
  native_portal_challenge_required: 'ChillyRoom pidió una verificación adicional en el portal. Inicia sesión manualmente en el portal y vuelve a intentarlo.',
  native_portal_unavailable: 'El portal de ChillyRoom no está disponible en este momento. Inténtalo más tarde.',
  native_no_cloud_save: 'No hay una partida en la nube para este jugador. No se creó ni se sobrescribió ninguna copia.',
  native_device_binding_throttled: 'ChillyRoom limita la vinculación de dispositivos nuevos. La identificación generada se conserva; espera antes de reintentar.',
  native_save_error: 'No se pudo comprobar la partida en este intento. Puedes reintentar la descarga.',
  native_session_expired: 'La sesión caducó. Inicia sesión de nuevo.',
  native_session_required: 'La sesión no está activa. Inicia sesión de nuevo.',
  native_session_rejected: 'ChillyRoom rechazó la sesión emitida para el servicio de guardado. Inténtalo de nuevo.',
  native_store_unavailable: 'El almacén privado de sesiones no está disponible. Inténtalo más tarde.',
  native_auth_disabled: 'La autenticación nativa está deshabilitada en este servidor.',
  native_write_disabled: 'La escritura remota está deshabilitada en este entorno experimental.',
  native_write_denied: 'Esta cuenta está autorizada solo para lectura.',
  native_save_identity_mismatch: 'La partida devuelta no corresponde a la cuenta autenticada.',
}

function friendly(error: ApiProblem): ApiProblem {
  const message = FRIENDLY[error.code]
  return message ? new ApiProblem(message, [], error.code) : error
}

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
}

function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateFormat.format(date)
}

export function NativeAuthPage() {
  const [config, setConfig] = useState<NativeConfig | null>(null)
  const [session, setSession] = useState<NativeSession | null>(null)
  const [profileId, setProfileId] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [revision, setRevision] = useState(0)
  const configOperation = useOperation()
  const authOperation = useOperation()
  const installOperation = useOperation()

  useEffect(() => {
    void configOperation.run(async (signal) => {
      const next = await nativeAuth.config(signal)
      setConfig(next)
      setSession(next.session)
      setProfileId((current) => {
        if (!next.requires_profile_selection) return ''
        if (next.profiles.some((profile) => profile.id === current)) return current
        return next.profiles.length === 1 ? next.profiles[0].id : ''
      })
    })
  }, [revision])

  function refresh() {
    setRevision((value) => value + 1)
  }

  function expired() {
    setSession({ active: false, reason: 'expired', message: FRIENDLY.native_session_expired })
    refresh()
  }

  function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const email = String(data.get('email') ?? '').trim()
    const password = String(data.get('password') ?? '')
    const passwordField = form.elements.namedItem('password')
    if (passwordField instanceof HTMLInputElement) passwordField.value = ''
    const selected = config?.requires_profile_selection
      ? String(data.get('profile_id') ?? profileId)
      : ''
    void authOperation.run(async (signal) => {
      const next = await nativeAuth.login({
        distribution: String(data.get('distribution') ?? 'android-global'),
        email,
        password,
        ...(selected ? { profile_id: selected } : {}),
      }, signal)
      setSession(next)
      form.reset()
      setShowPassword(false)
    })
  }

  function logout() {
    if (!window.confirm('¿Cerrar sesión? Se eliminará el acceso de este navegador a la cuenta.')) return
    void authOperation.run(async (signal) => {
      await nativeAuth.logout(signal)
      setSession({ active: false, reason: 'none' })
      setConfig((current) => current && { ...current, session: { active: false, reason: 'none' } })
    })
  }

  function install(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const uniqueId = String(new FormData(form).get('unique_id') ?? '').trim()
    if (!uniqueId) return
    void installOperation.run(async (signal) => {
      const next = await nativeAuth.installation(uniqueId, signal)
      setSession(next)
      form.reset()
      refresh()
    })
  }

  const active = session?.active === true
  const available = config?.available === true
  const profiles = config?.profiles ?? []
  const pendingNotice = config !== null && config.available && !config.login_available
  const sessionMessage = session?.reason === 'expired'
    ? session.message ?? FRIENDLY.native_session_expired
    : null

  return <>
    <PageTitle title="Cuenta y partida">
      Inicia sesión con tu cuenta autorizada de ChillyRoom usando solo correo, contraseña y
      distribución. El servidor genera y cifra la identificación de instalación; no necesitas
      extraerla de Android ni pedirla al administrador. Solo Android Global está validado.
    </PageTitle>

    <div className="lab-shell account-shell">
      {configOperation.pending && !config && <p role="status">Consultando el servicio de autenticación…</p>}
      {configOperation.problem && <>
        <section className="lab-card">
          <div className="lab-card-head">
            <span className="lab-icon"><ServerOff size={20} aria-hidden="true" /></span>
            <div><h2>Servicio temporalmente no disponible</h2><p>No se pudo consultar la autenticación nativa.</p></div>
          </div>
          <Problem problem={configOperation.problem} />
          <button className="button lab-quiet" type="button" onClick={refresh}>
            <RefreshCw size={16} aria-hidden="true" /> Reintentar
          </button>
        </section>
      </>}

      {config && !available && !active && <>
        <section className="lab-card" aria-labelledby="unavailable-title">
          <div className="lab-card-head">
            <span className="lab-icon"><ServerOff size={20} aria-hidden="true" /></span>
            <div>
              <h2 id="unavailable-title">Servicio temporalmente no disponible</h2>
              <p>{config.message ?? 'La autenticación nativa no está habilitada en este servidor.'}</p>
            </div>
          </div>
          <Notice tone="warning">
            El propietario debe habilitar el servicio y aprovisionar un perfil de instalación
            Android Global. No se solicitan credenciales mientras el servicio esté deshabilitado.
          </Notice>
          <button className="button lab-quiet" type="button" onClick={refresh}>
            <RefreshCw size={16} aria-hidden="true" /> Reintentar
          </button>
        </section>
      </>}

      {!active && available && <>
        {sessionMessage && <Notice tone="warning">{sessionMessage}</Notice>}
        <section className="lab-card" aria-labelledby="login-title">
          <div className="lab-card-head">
            <span className="lab-icon"><UserRound size={20} aria-hidden="true" /></span>
            <div>
              <h2 id="login-title">Iniciar sesión en ChillyRoom</h2>
              <p>La contraseña solo se usa en memoria y nunca se guarda ni se devuelve al navegador.</p>
            </div>
          </div>
          {pendingNotice && <Notice tone="warning">
            <strong>Configuración pendiente.</strong> El servicio no tiene habilitada la generación
            automática de instalación ni un perfil administrativo utilizable. El propietario debe
            revisar la configuración del servidor.
          </Notice>}
          {config.problem_code && <Notice tone="warning">
            {config.message ?? 'El servicio de autenticación no está configurado por completo.'}
          </Notice>}
          {config.auto_identity !== false && <Notice tone="info">
            <strong>No necesitas configurar identificadores.</strong>{' '}
            {config.portal_enabled === false
              ? 'El servidor generará y cifrará un perfil de instalación propio, pero la consulta al portal está deshabilitada: una cuenta con progreso anterior podría no recuperar su jugador.'
              : 'El servidor consultará el portal oficial para localizar tu jugador, generará y cifrará un perfil de instalación propio y conservará el mismo par en los siguientes accesos.'}
            {' '}ChillyRoom puede aplicar su espera de vinculación de dispositivos nuevos.
          </Notice>}
          <form onSubmit={login}>
            <label className="lab-field"><span>Distribución</span>
              <select className="lab-input" name="distribution" defaultValue="android-global"
                disabled={!config.login_available}>
                {config.distributions.map((distribution) => <option key={distribution.id}
                  value={distribution.id} disabled={!distribution.enabled}>
                  {distribution.label}{distribution.enabled ? '' : ' — no validada'}
                </option>)}
              </select>
            </label>
            {config.requires_profile_selection && profiles.length > 1 && <label className="lab-field"><span>Perfil de instalación</span>
              <select className="lab-input" name="profile_id" value={profileId}
                onChange={(event) => setProfileId(event.target.value)} disabled={!config.login_available}>
                <option value="">Selecciona un perfil</option>
                {profiles.map((profile) => <option key={profile.id} value={profile.id}>
                  {profile.label}{profile.installation_ready ? '' : ' — instalación pendiente'}
                </option>)}
              </select>
            </label>}
            {config.requires_profile_selection && profiles.length === 1 && <p className="lab-hint">
              Perfil de instalación: {profiles[0].label}
              {profiles[0].installation_ready ? '' : ' — instalación pendiente'}
            </p>}
            <label className="lab-field"><span>Correo electrónico de ChillyRoom</span>
              <input className="lab-input" name="email" type="email" inputMode="email"
                autoComplete="username" required disabled={!config.login_available} />
            </label>
            <div className="lab-field">
              <label htmlFor="native-password">Contraseña</label>
              <span className="password-control">
                <input id="native-password" className="lab-input" name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password" required disabled={!config.login_available} />
                <button className="button lab-quiet password-toggle" type="button"
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  aria-pressed={showPassword} disabled={!config.login_available}
                  onClick={() => setShowPassword((value) => !value)}>
                  {showPassword ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
                </button>
              </span>
            </div>
            <button className="button lab-primary" disabled={authOperation.pending || !config.login_available}>
              {authOperation.pending && <LoaderCircle className="lab-spin" size={17} aria-hidden="true" />}
              {authOperation.pending ? 'Iniciando sesión…' : 'Iniciar sesión'}
            </button>
          </form>
          {authOperation.problem && <Problem problem={friendly(authOperation.problem)} />}
          <p className="lab-hint">
            Solo usa cuentas propias y autorizadas. No se reintenta automáticamente ante límites
            o desafíos del proveedor.
          </p>
        </section>
      </>}

      {active && session && <>
        <section className="lab-card" aria-labelledby="session-title">
          <div className="lab-card-head">
            <span className="lab-icon"><ShieldCheck size={20} aria-hidden="true" /></span>
            <div>
              <h2 id="session-title">Sesión activa</h2>
              <p>{session.account?.label ?? 'Cuenta autorizada'} · {session.account?.distribution_label ?? 'Android Global'}</p>
            </div>
          </div>
          <div className="lab-actions">
            <span className="lab-pill live"><span className="lab-dot" />Identidad verificada</span>
            {session.installation_ready
              ? <span className="lab-pill read"><span className="lab-dot" />
                {session.auto_identity ? 'Instalación generada por el servidor' : 'Instalación lista'}</span>
              : <span className="lab-pill read"><span className="lab-dot" />Instalación pendiente</span>}
          </div>
          <dl className="lab-facts">
            <div><dt>Caducidad de sesión</dt><dd>{formatDate(session.session_expires_at)}</dd></div>
            <div><dt>Inactividad</dt><dd>{formatDate(session.idle_expires_at)}</dd></div>
          </dl>
          {session.save_error === 'native_no_cloud_save' && <Notice tone="info">
            <strong>Sin partida en la nube.</strong> La cuenta se autenticó correctamente y el
            servidor no encontró una copia para este jugador. No se creó ni se sobrescribió nada.
          </Notice>}
          {session.save_error === 'native_device_binding_throttled' && <Notice tone="warning">
            <strong>Vinculación de dispositivo en espera.</strong> ChillyRoom limitó la vinculación
            de una instalación nueva para esta cuenta. El servidor conserva la identificación
            generada; no se crea otra. Vuelve a intentar la descarga cuando termine la espera
            {session.binding_wait_until ? ` (${formatDate(session.binding_wait_until)})` : ''}.
          </Notice>}
          {session.save_error && session.save_error !== 'native_device_binding_throttled'
            && session.save_error !== 'native_installation_required' && <Notice tone="warning">
            La comprobación inicial de la partida no se completó ({session.save_error}). Puedes
            reintentar la descarga desde el editor.
          </Notice>}
          <div className="lab-actions">
            <button className="button lab-quiet" type="button" disabled={authOperation.pending} onClick={logout}>
              {authOperation.pending ? <LoaderCircle className="lab-spin" size={16} aria-hidden="true" />
                : <LogOut size={16} aria-hidden="true" />}
              Cerrar sesión
            </button>
          </div>
          {authOperation.problem && <Problem problem={friendly(authOperation.problem)} />}
        </section>

        {session.installation_ready && <NativeEditor key={`${session.account?.label}-${session.session_expires_at}`}
          session={session} initialSave={session.save ?? null} onExpired={expired} />}

        {!session.installation_ready && session.auto_identity === false && <section className="lab-card"
          aria-labelledby="installation-title">
          <div className="lab-card-head">
            <span className="lab-icon"><ShieldCheck size={20} aria-hidden="true" /></span>
            <div>
              <h2 id="installation-title">Configuración administrativa de la instalación</h2>
              <p>Este perfil fue aprovisionado manualmente y aún no tiene identificador de instalación.</p>
            </div>
          </div>
          <Notice tone="warning">
            La generación automática está deshabilitada en este servidor. Un administrador debe
            completar la identificación por un canal autorizado; no se solicita en el flujo normal.
          </Notice>
          <form onSubmit={install}>
            <label className="lab-field"><span>Identificador de instalación</span>
              <input className="lab-input" name="unique_id" required maxLength={512}
                autoComplete="off" spellCheck={false} />
              <small>Se cifra en el servidor y no se devuelve al navegador.</small>
            </label>
            <button className="button lab-primary" disabled={installOperation.pending}>
              {installOperation.pending && <LoaderCircle className="lab-spin" size={17} aria-hidden="true" />}
              {installOperation.pending ? 'Comprobando instalación…' : 'Completar instalación'}
            </button>
          </form>
          {installOperation.problem && <Problem problem={friendly(installOperation.problem)} />}
        </section>}
      </>}

      <details className="account-details">
        <summary>Cuentas vinculadas de la Fase 6.3</summary>
        <p className="lab-hint">El flujo anterior por enlace privado sigue disponible sin cambios.</p>
        <Link className="button lab-quiet" to="/partida/vinculadas">Abrir cuentas vinculadas</Link>
      </details>
    </div>
  </>
}

function NativeEditor({ session, initialSave, onExpired }: {
  session: NativeSession
  initialSave: NativeSaveSummary | null
  onExpired: () => void
}) {
  const [save, setSave] = useState<(NativeSaveSummary & { downloaded_at: string }) | null>(
    initialSave ? { ...initialSave, downloaded_at: new Date().toISOString() } : null,
  )
  const [newGems, setNewGems] = useState(initialSave ? String(initialSave.gems) : '')
  const [candidate, setCandidate] = useState<LabPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [history, setHistory] = useState<Array<LabBackup & { confirmed: boolean }>>([])
  const [backupResult, setBackupResult] = useState<(LabWriteResult | LabVerification) | null>(null)
  const operation = useOperation()
  const historyOperation = useOperation()
  const backupOperation = useOperation()

  async function refreshHistory(signal: AbortSignal) {
    setHistory((await nativeAuth.backups(signal)).backups)
  }

  function run(task: (signal: AbortSignal) => Promise<unknown>, action = operation) {
    void action.run(async (signal) => {
      try {
        await task(signal)
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      }
    })
  }

  useEffect(() => { void historyOperation.run(refreshHistory) }, [])

  const limits = {
    min_gems: session.min_gems ?? 0,
    max_gems: session.max_gems ?? 2_147_483_647,
  }
  const amount = /^\d+$/.test(newGems) ? Number(newGems) : Number.NaN
  const valid = Number.isSafeInteger(amount) && amount >= limits.min_gems && amount <= limits.max_gems
  const disabled = operation.pending || backupOperation.pending

  function clearPreview() {
    setCandidate(null)
    setConfirm(false)
    setResult(null)
  }

  return <>
    <section className="lab-card" aria-labelledby="save-title">
      <div className="lab-card-head">
        <span className="lab-icon"><Gem size={20} aria-hidden="true" /></span>
        <div><h2 id="save-title">Mi partida</h2><p>{session.account?.label} · {session.account?.distribution_label}</p></div>
      </div>
      {!session.write_ready && <Notice tone="warning">
        {session.write_enabled === false
          ? 'La escritura está deshabilitada en el servidor. Puedes descargar y preparar la edición, pero no subirla.'
          : 'Esta cuenta está autorizada solo para lectura. No se enviará ninguna escritura.'}
      </Notice>}
      {session.save_error === 'native_no_cloud_save' && !save && <Notice tone="info">
        La cuenta no tiene una partida en la nube para este jugador. No se creó ni se sobrescribió
        ninguna copia; puedes reintentar la descarga más adelante.
      </Notice>}
      {session.save_error === 'native_device_binding_throttled' && !save && <Notice tone="warning">
        <strong>Vinculación en espera.</strong> ChillyRoom limitó la vinculación de esta instalación
        nueva. El servidor conserva la identificación generada; espera antes de reintentar la descarga.
      </Notice>}
      {session.save_error && session.save_error !== 'native_device_binding_throttled'
        && session.save_error !== 'native_installation_required' && !save && <Notice tone="warning">
        La descarga de verificación no se completó. Puedes reintentarla manualmente.
      </Notice>}
      <button className="button lab-primary" disabled={disabled} onClick={() => run(async (signal) => {
        clearPreview()
        setSave(null)
        const downloaded = await nativeAuth.save(signal)
        setSave(downloaded)
        setNewGems(String(downloaded.gems))
      })}>
        <CloudDownload size={18} aria-hidden="true" />
        {operation.pending ? 'Descargando…' : 'Descargar partida'}
      </button>
      {save && <>
        <div className="lab-save">
          <div className="lab-metric"><span>Gemas descargadas</span>
            <strong data-testid="native-current-gems">{gemFormat.format(save.gems)}</strong></div>
          <dl className="lab-facts">
            <div><dt>Tamaño</dt><dd>{formatSize(save.bytes)}</dd></div>
            <div><dt>Descarga</dt><dd>{formatDate(save.downloaded_at)}</dd></div>
            <div><dt>Verificación</dt><dd>Copia validada</dd></div>
            <div><dt>Origen</dt><dd>{save.remote_source}</dd></div>
          </dl>
        </div>
        <form onSubmit={(event) => {
          event.preventDefault()
          if (!valid) return
          run(async (signal) => {
            clearPreview()
            setCandidate(await nativeAuth.prepare(amount, save.sha256, signal))
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
          <button className="button lab-quiet" disabled={disabled || !valid || amount === save.gems}>
            Preparar edición
          </button>
        </form>
        <details className="account-details">
          <summary>Detalles de descarga</summary>
          <p className="lab-mono">SHA-256 {save.sha256}</p>
        </details>
      </>}
      {candidate && <div className="account-preview">
        <dl className="lab-facts">
          <div><dt>Gemas actuales</dt><dd>{gemFormat.format(candidate.original_gems)}</dd></div>
          <div><dt>Gemas nuevas</dt><dd>{gemFormat.format(candidate.new_gems)}</dd></div>
          <div><dt>Cambio</dt><dd>{new Intl.NumberFormat('es-MX', { signDisplay: 'exceptZero' })
            .format(candidate.new_gems - candidate.original_gems)}</dd></div>
          <div><dt>Respaldo original</dt><dd>{formatSize(candidate.backup.original_size)}</dd></div>
        </dl>
        <p className="lab-hint">La edición solo cambia las gemas y conserva un respaldo privado.</p>
        {session.write_ready && !result && <>
          <label className="lab-check"><input type="checkbox" checked={confirm} disabled={disabled}
            onChange={(event) => setConfirm(event.target.checked)} />
            <span>Confirmo que quiero sobrescribir la partida de {session.account?.label}.</span>
          </label>
          <button className="button lab-primary" disabled={disabled || !confirm || !candidate.changed}
            onClick={() => run(async (signal) => {
              setConfirm(false)
              setResult(await nativeAuth.confirm(candidate.backup.id, candidate.candidate_sha256, signal))
              void historyOperation.run(refreshHistory)
            })}>
            Subir y verificar
          </button>
        </>}
      </div>}
      {result && <div role="status" className={`lab-banner ${result.persisted ? 'success' : 'warn'}`}>
        {result.message}
      </div>}
      {operation.pending && <p role="status">Operación en curso…</p>}
      {operation.problem && <Problem problem={friendly(operation.problem)} />}
    </section>

    <section className="lab-card" aria-labelledby="backups-title">
      <div className="lab-card-head">
        <span className="lab-icon"><DatabaseBackup size={20} aria-hidden="true" /></span>
        <div><h2 id="backups-title">Respaldos</h2><p>{session.account?.label}</p></div>
      </div>
      {historyOperation.pending && <p role="status">Cargando respaldos…</p>}
      {historyOperation.problem && <>
        <Problem problem={friendly(historyOperation.problem)} />
        <button className="button lab-quiet" onClick={() => void historyOperation.run(refreshHistory)}>
          Actualizar respaldos
        </button>
      </>}
      {history.length === 0 && !historyOperation.pending && !historyOperation.problem
        && <p>No hay respaldos de esta cuenta.</p>}
      {history.map((backup) => <details className="account-details" key={backup.id}>
        <summary>{formatDate(backup.created_at)} · {gemFormat.format(backup.original_gems)} → {gemFormat.format(backup.candidate_gems)}</summary>
        <p>{backup.confirmed ? 'Subida verificada' : 'Copia preparada'} · {formatSize(backup.original_size)}</p>
        <div className="lab-actions">
          <button className="button lab-quiet" disabled={disabled} onClick={() => {
            setBackupResult(null)
            run(async (signal) => setBackupResult(await nativeAuth.verify(backup.id, signal)), backupOperation)
          }}>Verificar nube</button>
          {session.write_ready && backup.changed && <button className="button lab-quiet" disabled={disabled}
            onClick={() => {
              if (window.confirm(`¿Restaurar el respaldo de ${session.account?.label} con ${gemFormat.format(backup.original_gems)} gemas?`)) {
                setBackupResult(null)
                run(async (signal) => {
                  setBackupResult(await nativeAuth.restore(backup.id, signal))
                  setSave(null)
                  clearPreview()
                }, backupOperation)
              }
            }}>Restaurar respaldo</button>}
        </div>
        {backupResult?.backup_id === backup.id && <p role="status">{backupResult.message}</p>}
        <details className="account-details">
          <summary>Huellas SHA-256</summary>
          <p className="lab-mono">Original {backup.original_sha256}</p>
          <p className="lab-mono">Candidato {backup.candidate_sha256}</p>
        </details>
      </details>)}
      {backupOperation.pending && <p role="status">Consultando la nube…</p>}
      {backupOperation.problem && <Problem problem={friendly(backupOperation.problem)} />}
    </section>
  </>
}
