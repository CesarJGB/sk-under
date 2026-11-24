import {
  ChevronDown, CloudDownload, Eye, EyeOff, LogOut,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import {
  ApiProblem, nativeAuth,
  type LabBackup, type LabPrepared, type LabVerification, type LabWriteResult,
  type NativeConfig, type NativeSaveSummary, type NativeSession,
} from '../api'
import { formatSize } from '../session'
import { Loading, Notice, PageTitle, Problem } from '../ui'
import { HomePage } from './HomePage'
import { useOperation } from '../useOperation'

const gemFormat = new Intl.NumberFormat('es-MX')
const dateFormat = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' })

const FRIENDLY: Record<string, string> = {
  invalid_request: 'Revisa los datos del formulario y vuelve a intentarlo.',
  native_https_required: 'Abre SK-Under mediante HTTPS para iniciar sesión.',
  native_credentials_rejected: 'El correo o la contraseña no son correctos.',
  native_login_throttled: 'Demasiados intentos. Espera antes de volver a intentarlo.',
  native_auth_throttled: 'ChillyRoom limitó los intentos. Espera antes de reintentar.',
  native_auth_unavailable: 'ChillyRoom no está disponible. Inténtalo más tarde.',
  native_auth_protocol: 'No se pudo comprobar la respuesta de ChillyRoom.',
  native_distribution_rejected: 'ChillyRoom rechazó la plataforma seleccionada.',
  native_identity_mismatch: 'No se pudo verificar la cuenta solicitada.',
  native_profile_identity_mismatch: 'Elige el perfil que corresponde a tu cuenta.',
  native_profile_required: 'Selecciona el perfil que corresponde a tu cuenta.',
  native_profile_missing: 'Pide al administrador que habilite el acceso para esta cuenta.',
  native_installation_required: 'Completa la configuración de acceso para consultar la partida.',
  native_portal_rejected: 'El correo o la contraseña no son correctos.',
  native_portal_identity_mismatch: 'No se pudo verificar la cuenta solicitada.',
  native_portal_challenge_required: 'ChillyRoom pidió una verificación adicional. Completa el acceso en su portal y vuelve a intentarlo.',
  native_portal_unavailable: 'El portal de ChillyRoom no está disponible. Inténtalo más tarde.',
  native_no_cloud_save: 'Sin partida en la nube. Guarda una copia desde Soul Knight y vuelve a intentarlo.',
  native_device_binding_throttled: 'ChillyRoom está aplicando una espera para este dispositivo.',
  native_save_error: 'No se pudo descargar la partida. Vuelve a intentarlo.',
  native_session_expired: 'La sesión caducó. Inicia sesión de nuevo.',
  native_session_required: 'Inicia sesión de nuevo para continuar.',
  native_session_rejected: 'ChillyRoom rechazó el acceso a la partida. Vuelve a intentarlo.',
  native_store_unavailable: 'El acceso a la cuenta no está disponible. Inténtalo más tarde.',
  native_auth_disabled: 'El inicio de sesión está temporalmente deshabilitado.',
  native_write_disabled: 'La subida a la nube está deshabilitada.',
  native_write_denied: 'Esta cuenta tiene acceso de solo lectura.',
  cloud_write_disabled: 'La subida a la nube está deshabilitada.',
  cloud_session_rejected: 'ChillyRoom rechazó el acceso a la partida. Vuelve a iniciar sesión.',
  cloud_already_confirmed: 'Esta edición ya se subió. Verifica su respaldo en Partida.',
  native_save_identity_mismatch: 'No se pudo verificar que la partida pertenezca a tu cuenta.',
  cloud_remote_changed: 'La partida cambió en la nube. Descárgala de nuevo antes de editar.',
}

function friendly(error: ApiProblem, fallback: string): ApiProblem {
  return new ApiProblem(
    FRIENDLY[error.code] ?? (error.message === 'El inicio de sesión requiere HTTPS en el editor y en la API.'
      ? FRIENDLY.native_https_required : fallback),
    [],
    error.code,
  )
}

type CloudView = 'home' | 'save' | 'editor'

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
}

function distributionLabel(label: string) {
  return label.replace(/ \((?:GP(?:_VNM)?|IOS(?:_VNM|_CN)?)\)$/, '')
}

function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateFormat.format(date)
}

export function NativeAuthPage({ view }: { view: CloudView }) {
  const [config, setConfig] = useState<NativeConfig | null>(null)
  const [session, setSession] = useState<NativeSession | null>(null)
  const [profileId, setProfileId] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [accountHint, setAccountHint] = useState('')
  const [revision, setRevision] = useState(0)
  const configOperation = useOperation()
  const authOperation = useOperation()
  const installOperation = useOperation()

  useEffect(() => {
    void configOperation.run(async (signal) => {
      const next = await nativeAuth.config(signal)
      setConfig(next)
      setSession(next.session)
      if (!next.session.active) setAccountHint('')
      setProfileId((current) => {
        if (!next.requires_profile_selection) return ''
        if (next.profiles.some((profile) => profile.id === current)) return current
        return next.profiles.length === 1 ? next.profiles[0].id : ''
      })
    })
  }, [revision])

  useEffect(() => {
    if (view !== 'save') setShowPassword(false)
  }, [view])

  function refresh() {
    setRevision((value) => value + 1)
  }

  function expired() {
    setAccountHint('')
    setSession({ active: false, reason: 'expired' })
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
      const [name, domain] = email.split('@')
      setAccountHint(domain ? `${Array.from(name).slice(0, 2).join('')}…@${domain}` : '')
      form.reset()
      setShowPassword(false)
    })
  }

  function logout() {
    if (!window.confirm('¿Cerrar sesión? Se eliminará el acceso de este navegador a la cuenta.')) return
    void authOperation.run(async (signal) => {
      await nativeAuth.logout(signal)
      setAccountHint('')
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
  const loading = (!config && !configOperation.problem) || (configOperation.pending && !active)
  const unavailable = Boolean(configOperation.problem) || Boolean(config && !config.login_available)
  const account = session?.account
  const version = config?.distributions.find(({ id }) => id === account?.distribution)?.game_version
  const platform = [distributionLabel(account?.distribution_label ?? ''), version].filter(Boolean).join(' · ')

  if (view === 'home' && !active) {
    return <HomePage loading={loading} unavailable={unavailable} retry={refresh} />
  }

  const accountLabel = account?.label && !/^Cuenta [a-f0-9]{12}$/i.test(account.label)
    ? account.label : accountHint || 'Cuenta ChillyRoom'
  const accountBar = active && <section className="account-bar" aria-label="Cuenta conectada">
    <div className="account-identity">
      <div>
        <span className="cloud-kicker">Cuenta conectada</span>
        <strong>{accountLabel}</strong>
      </div>
      {platform && <span className="account-platform">{platform}</span>}
    </div>
    <button className="button account-logout" type="button" disabled={authOperation.pending} onClick={logout}>
      <LogOut size={16} aria-hidden="true" />
      {authOperation.pending ? 'Cerrando sesión…' : 'Cerrar sesión'}
    </button>
    {authOperation.problem && <Problem problem={friendly(authOperation.problem, 'No se pudo cerrar sesión. Vuelve a intentarlo.')} />}
  </section>

  return <>
    {view !== 'home' && <div className="cloud-title"><PageTitle title={view === 'editor' ? 'Editor' : 'Partida'} /></div>}
    {!active && view === 'editor' && <section className="cloud-empty panel">
      {loading ? <Loading>Comprobando conexión…</Loading> : <>
        <h2>{unavailable ? 'Servicio temporalmente no disponible' : 'Conecta tu cuenta'}</h2>
        {!unavailable && <p>Abre tu partida en la nube para editarla.</p>}
        <Link className="button primary" to="/partida">{unavailable ? 'Ir a Partida' : 'Conectar cuenta'}</Link>
      </>}
    </section>}
    {!active && view === 'save' && <>
      {session?.reason === 'expired' && <Notice tone="warning">{FRIENDLY.native_session_expired}</Notice>}
      {loading ? <Loading>Comprobando el acceso…</Loading> : configOperation.problem || !available ? (
        <section className="cloud-empty panel">
          <h2>Servicio temporalmente no disponible</h2>
          <button className="button quiet" type="button" onClick={refresh}>Reintentar</button>
        </section>
      ) : config && <section className="cloud-login panel" aria-labelledby="login-title">
        <h2 id="login-title">Iniciar sesión en ChillyRoom</h2>
        {!config.login_available && <Notice tone="warning">El acceso aún no está habilitado. Contacta con el administrador.</Notice>}
        {config.auto_identity !== false && config.portal_enabled === false &&
          <Notice tone="warning">La recuperación del progreso anterior puede estar limitada temporalmente.</Notice>}
        <form className="cloud-form" onSubmit={login} aria-busy={authOperation.pending}>
          <label className="cloud-field"><span>Correo electrónico</span>
            <input name="email" type="email" inputMode="email" autoComplete="username" required disabled={!config.login_available} />
          </label>
          <div className="cloud-field">
            <label htmlFor="native-password">Contraseña</label>
            <span className="password-control">
              <input id="native-password" name="password" type={showPassword ? 'text' : 'password'}
                autoComplete="current-password" required disabled={!config.login_available} />
              <button className="button quiet password-toggle" type="button"
                aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                aria-pressed={showPassword} disabled={!config.login_available}
                onClick={() => setShowPassword((value) => !value)}>
                {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
              </button>
            </span>
          </div>
          <label className="cloud-field"><span>Distribución</span>
            <span className="cloud-select">
              <select name="distribution" defaultValue="android-global" disabled={!config.login_available}>
                {config.distributions.map((distribution) => <option key={distribution.id}
                  value={distribution.id} disabled={!distribution.enabled}>
                  {distributionLabel(distribution.label)}{distribution.enabled ? '' : ' · No disponible'}
                </option>)}
              </select>
              <ChevronDown size={16} aria-hidden="true" />
            </span>
          </label>
          {config.requires_profile_selection && config.profiles.length > 1 &&
            <label className="cloud-field"><span>Perfil de instalación</span>
              <span className="cloud-select">
                <select name="profile_id" value={profileId} onChange={(event) => setProfileId(event.target.value)}
                  disabled={!config.login_available}>
                  <option value="">Selecciona un perfil</option>
                  {config.profiles.map((profile) => <option key={profile.id} value={profile.id}>
                    {profile.label}{profile.installation_ready ? '' : ' · Instalación pendiente'}
                  </option>)}
                </select>
                <ChevronDown size={16} aria-hidden="true" />
              </span>
            </label>}
          <button className="button primary" disabled={authOperation.pending || !config.login_available}>
            {authOperation.pending ? 'Iniciando sesión…' : 'Iniciar sesión'}
          </button>
          {authOperation.pending && <Loading>Conectando con ChillyRoom…</Loading>}
          {authOperation.problem && <Problem problem={friendly(authOperation.problem, 'No se pudo iniciar sesión. Vuelve a intentarlo.')} />}
        </form>
      </section>}
    </>}

    {active && session && <>
      {view === 'save' && accountBar}
      {session.installation_ready ? <NativeEditor key={`${session.account?.label}-${session.session_expires_at}`}
        session={session} initialSave={session.save ?? null} view={view} platform={platform} accountLabel={accountLabel}
        onExpired={expired} /> : view === 'home' ? <HomePage account={{ label: accountLabel, platform, saveStatus: 'Configuración de acceso pendiente' }} />
          : view === 'editor' ? <section className="cloud-empty panel">
            <h2>Configuración de acceso pendiente</h2>
            <Link className="button primary" to="/partida">Ir a Partida</Link>
          </section> : <section className="cloud-empty panel">
            <h2>Configuración de acceso pendiente</h2>
            <p>Contacta con el administrador para completar el acceso a la partida.</p>
            {session.auto_identity === false && <details className="cloud-details">
              <summary>Configuración de instalación</summary>
              <form className="cloud-form" onSubmit={install}>
                <label className="cloud-field"><span>Identificador de instalación</span>
                  <input name="unique_id" required maxLength={512} autoComplete="off" spellCheck={false} />
                </label>
                <button className="button primary" disabled={installOperation.pending}>
                  {installOperation.pending ? 'Comprobando instalación…' : 'Completar instalación'}
                </button>
              </form>
              {installOperation.problem && <Problem problem={friendly(installOperation.problem, 'No se pudo completar la instalación.')} />}
            </details>}
          </section>}
    </>}
    {view === 'save' && <div className="cloud-secondary">
      <Link className="cloud-text-link" to="/partida/vinculadas">Acceso por enlace privado</Link>
    </div>}
  </>
}

function NativeEditor({ session, initialSave, onExpired, view, platform, accountLabel }: {
  session: NativeSession
  initialSave: NativeSaveSummary | null
  onExpired: () => void
  view: CloudView
  platform: string
  accountLabel: string
}) {
  const [save, setSave] = useState<(NativeSaveSummary & { downloaded_at?: string }) | null>(initialSave)
  const [syncResult, setSyncResult] = useState<LabWriteResult | null>(null)
  const [action, setAction] = useState<'download' | 'prepare' | 'upload'>('download')
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

  const downloading = action === 'download' && operation.pending
  const downloadProblem = action === 'download' ? operation.problem : null
  const initialProblem = !save && !downloadProblem && !syncResult && !downloading ? session.save_error : null
  const noCloudSave = initialProblem === 'native_no_cloud_save' || downloadProblem?.code === 'native_no_cloud_save'
  const waiting = initialProblem === 'native_device_binding_throttled'
    || downloadProblem?.code === 'native_device_binding_throttled'
  const waitUntil = session.binding_wait_until && formatDate(session.binding_wait_until)
  const cloudGems = syncResult?.persisted ? syncResult.remote_gems : save?.gems
  const uploadPending = action === 'upload' && operation.pending
  const uploadFailed = action === 'upload' && Boolean(operation.problem)
  const syncUnconfirmed = uploadFailed || (syncResult !== null && !syncResult.persisted)
  let saveStatus = 'Partida pendiente de descargar'
  if (downloading) saveStatus = 'Descargando partida…'
  else if (uploadPending) saveStatus = 'Subiendo y verificando…'
  else if (syncUnconfirmed) saveStatus = 'Sincronización sin confirmar'
  else if (syncResult?.persisted) saveStatus = syncResult.action === 'restore' ? 'Respaldo restaurado' : 'Subida verificada'
  else if (save) saveStatus = 'Copia verificada'
  else if (noCloudSave) saveStatus = 'Sin partida en la nube'
  else if (waiting) saveStatus = 'En espera de ChillyRoom'
  else if (downloadProblem || initialProblem) saveStatus = 'Descarga pendiente'

  function download() {
    setAction('download')
    run(async (signal) => {
      clearPreview()
      setSyncResult(null)
      setSave(null)
      const downloaded = await nativeAuth.save(signal)
      setSave(downloaded)
      setNewGems(String(downloaded.gems))
    })
  }

  const downloadButton = <button className={`button ${save ? 'quiet' : 'primary'}`} disabled={disabled} onClick={download}>
    <CloudDownload size={18} aria-hidden="true" />
    {downloading ? 'Descargando…' : 'Descargar partida'}
  </button>

  const downloadFeedback = noCloudSave ? <p className="cloud-note">
    Guarda una copia desde Soul Knight y vuelve a intentar la descarga.
  </p> : waiting ? <Notice tone="warning">
    ChillyRoom está aplicando una espera para este dispositivo.
    {waitUntil && waitUntil !== '—' ? ` Vuelve a intentarlo después de ${waitUntil}.` : ' Espera antes de volver a intentarlo.'}
  </Notice> : downloadProblem ? <Problem problem={friendly(downloadProblem, 'No se pudo descargar la partida. Vuelve a intentarlo.')} />
    : initialProblem ? <Notice tone="warning">No se pudo comprobar la partida. Intenta descargarla de nuevo.</Notice> : null

  if (view === 'home') return <HomePage account={{ label: accountLabel, platform, saveStatus }} />

  if (view === 'save') return <>
    <section className="cloud-section panel" aria-labelledby="save-title">
      <div className="cloud-save-overview">
        <div>
          <h2 id="save-title">Partida en la nube</h2>
          <p className="cloud-state" role="status">{saveStatus}</p>
        </div>
        {cloudGems != null && <dl className="cloud-save-data">
          <div className="cloud-gems">
            <dt>{uploadPending || syncUnconfirmed ? 'Últimas gemas verificadas' : 'Gemas'}</dt>
            <dd data-testid="native-current-gems">{gemFormat.format(cloudGems)}</dd>
          </div>
          {save?.downloaded_at && !syncResult && <div>
            <dt>Última descarga</dt><dd>{formatDate(save.downloaded_at)}</dd>
          </div>}
        </dl>}
        <div className="cloud-actions">
          {save && <Link className="button primary" to="/editor">Abrir Editor</Link>}
          {downloadButton}
        </div>
      </div>
      {downloadFeedback}
      {uploadFailed && operation.problem && <Problem problem={friendly(operation.problem, 'No se pudo confirmar la subida. Puedes verificar el respaldo.')} />}
      {!session.write_ready && <p className="cloud-note">Acceso a la nube de solo lectura.</p>}
    </section>

    <section className="cloud-section cloud-backups" aria-labelledby="backups-title">
      <h2 id="backups-title">Respaldos</h2>
      {historyOperation.pending && <Loading>Cargando respaldos…</Loading>}
      {historyOperation.problem && <>
        <Problem problem={friendly(historyOperation.problem, 'No se pudieron cargar los respaldos.')} />
        <button className="button quiet" onClick={() => void historyOperation.run(refreshHistory)}>
          Actualizar respaldos
        </button>
      </>}
      {history.length === 0 && !historyOperation.pending && !historyOperation.problem &&
        <p className="cloud-note">Esta cuenta todavía no tiene respaldos.</p>}
      {history.map((backup) => <details className="cloud-details backup-row" key={backup.id}>
        <summary><span>{formatDate(backup.created_at)}</span>
          <span className="backup-amount">{gemFormat.format(backup.original_gems)} gemas</span></summary>
        <div className="backup-body">
          <p>{backup.confirmed ? 'Subida verificada' : 'Edición preparada'} · {formatSize(backup.original_size)}</p>
          <div className="cloud-actions">
            <button className="button quiet" disabled={disabled} onClick={() => {
              setBackupResult(null)
              run(async (signal) => setBackupResult(await nativeAuth.verify(backup.id, signal)), backupOperation)
            }}>Verificar nube</button>
            {session.write_ready && backup.changed && <button className="button quiet" disabled={disabled}
              onClick={() => {
                if (window.confirm(`¿Restaurar el respaldo de ${accountLabel} con ${gemFormat.format(backup.original_gems)} gemas? Se reemplazará la partida en la nube.`)) {
                  setBackupResult(null)
                  run(async (signal) => {
                    const restored = await nativeAuth.restore(backup.id, signal)
                    setBackupResult(restored)
                    setSyncResult(restored)
                    setSave(null)
                    clearPreview()
                  }, backupOperation)
                }
              }}>Restaurar respaldo</button>}
          </div>
          {backupResult?.backup_id === backup.id && <p role="status">{backupMessage(backupResult)}</p>}
        </div>
      </details>)}
      {backupOperation.pending && <Loading>Consultando la nube…</Loading>}
      {backupOperation.problem && <Problem problem={friendly(backupOperation.problem, 'No se pudo completar la operación del respaldo.')} />}
    </section>
  </>

  if (!save) return <section className="cloud-empty panel">
    <h2>{noCloudSave ? 'Sin partida en la nube' : 'Descarga tu partida'}</h2>
    {downloading && <Loading>Descargando partida…</Loading>}
    {downloadFeedback}
    {downloadButton}
  </section>

  return <section className="cloud-section panel cloud-editor" aria-labelledby="edit-gems-title">
    <div className="cloud-section-head">
      <div><h2 id="edit-gems-title">Gemas</h2><p className="cloud-state">{accountLabel}</p></div>
      <div className="editor-current">
        <span>Gemas de la copia descargada</span>
        <strong>{gemFormat.format(save.gems)}</strong>
      </div>
    </div>
    {!session.write_ready && <Notice tone="warning">
      Puedes preparar una edición y su respaldo. La subida a la nube está deshabilitada.
    </Notice>}
    <form className="cloud-form" onSubmit={(event) => {
      event.preventDefault()
      if (!valid) return
      setAction('prepare')
      run(async (signal) => {
        clearPreview()
        setCandidate(await nativeAuth.prepare(amount, save.sha256, signal))
        void historyOperation.run(refreshHistory)
      })
    }}>
      <label className="cloud-field"><span>Nueva cantidad de gemas</span>
        <input inputMode="numeric" value={newGems} disabled={disabled}
          aria-invalid={!valid} aria-describedby="gem-limits" onChange={(event) => {
            setNewGems(event.target.value)
            clearPreview()
          }} />
        <small id="gem-limits">Entero entre {gemFormat.format(limits.min_gems)} y {gemFormat.format(limits.max_gems)}.</small>
      </label>
      <button className="button primary" disabled={disabled || !valid || amount === save.gems}>Preparar edición</button>
    </form>
    {candidate && <div className="cloud-preview">
      <h3>Revisar cambios</h3>
      <dl className="cloud-preview-data">
        <div><dt>Gemas originales</dt><dd>{gemFormat.format(candidate.original_gems)}</dd></div>
        <div><dt>Gemas nuevas</dt><dd>{gemFormat.format(candidate.new_gems)}</dd></div>
        <div><dt>Cambio</dt><dd>{new Intl.NumberFormat('es-MX', { signDisplay: 'exceptZero' })
          .format(candidate.new_gems - candidate.original_gems)}</dd></div>
      </dl>
      <p className="cloud-note">Se guardó un respaldo de la partida original.</p>
      {session.write_ready && !result && <>
        <label className="cloud-check"><input type="checkbox" checked={confirm} disabled={disabled}
          onChange={(event) => setConfirm(event.target.checked)} />
          <span>Confirmo que quiero sobrescribir la partida en la nube de {accountLabel}.</span>
        </label>
        <button className="button primary" disabled={disabled || !confirm || !candidate.changed}
          onClick={() => {
            setAction('upload')
            run(async (signal) => {
              setConfirm(false)
              const uploaded = await nativeAuth.confirm(candidate.backup.id, candidate.candidate_sha256, signal)
              setResult(uploaded)
              setSyncResult(uploaded)
              void historyOperation.run(refreshHistory)
            })
          }}>Subir y verificar</button>
      </>}
    </div>}
    {result && <div role="status" className={`cloud-feedback ${result.persisted ? 'verified' : 'uncertain'}`}>
      {result.persisted ? 'Cambios guardados y verificados en la nube.' : 'No se pudo confirmar la subida. Verifica el estado desde Partida.'}
    </div>}
    {operation.pending && <Loading>{action === 'prepare' ? 'Preparando edición…' : 'Subiendo y verificando…'}</Loading>}
    {operation.problem && <Problem problem={friendly(operation.problem, action === 'upload'
      ? 'No se pudo confirmar la subida. Verifica el estado desde Partida.'
      : 'No se pudo preparar la edición. Vuelve a intentarlo.')} />}
  </section>
}

function backupMessage(result: LabWriteResult | LabVerification) {
  if ('persisted' in result) {
    return result.persisted ? 'Respaldo restaurado y verificado en la nube.' : 'No se pudo confirmar la restauración.'
  }
  if (result.matches_original) return 'La nube coincide con el respaldo original.'
  if (result.matches_candidate) return 'La nube coincide con la edición guardada.'
  return 'La partida en la nube difiere de las dos versiones del respaldo.'
}
