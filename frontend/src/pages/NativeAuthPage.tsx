import {
  ChevronDown, CloudDownload, Eye, EyeOff, LogOut,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import {
  ApiProblem, nativeAuth,
  type LabBackup, type LabVerification, type LabWriteResult,
  type NativeConfig, type NativeSaveSummary, type NativeSession,
} from '../api'
import { formatSize } from '../session'
import { Loading, Notice, PageTitle, Problem } from '../ui'
import { HomePage } from './HomePage'
import { EditorWorkspace } from './EditorWorkspace'
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
  network_error: 'No se pudo conectar con la API de SK-Under. Revisa tu conexión.',
  cloud_provider_unavailable: 'ChillyRoom no respondió al consultar la partida. Inténtalo más tarde.',
  cloud_provider_protocol: 'La respuesta de ChillyRoom tiene un formato inesperado.',
  invalid_aggregate: 'La partida descargada tiene un esquema de guardado incompatible.',
  unsupported_gems_structure: 'La versión o los tipos de los campos de gemas son incompatibles con el editor.',
  gems_field_missing: 'La partida descargada no contiene el saldo de gemas.',
  unsupported_serialization: 'La copia usa una serialización incompatible con la edición granular.',
  unknown_gems_dependencies: 'El saldo depende de contadores ausentes o fuera del intervalo compatible.',
  invalid_gems_value: 'Introduce un número entero dentro del intervalo de gemas indicado.',
  gems_verification_failed: 'La copia editada no superó la comprobación de integridad.',
  outdated_gems_draft: 'El borrador usa una edición anterior. Prepara de nuevo la edición antes de subirla.',
  invalid_fish_chip_value: 'Introduce un número entero no negativo dentro del intervalo de fichas de pesca.',
  invalid_fish_material_value: 'itemData.materials.material_fish no es un entero; no se sobrescribe automáticamente.',
  invalid_fish_progress_value: 'Introduce un número entero no negativo para el progreso acumulado de fichas.',
  fish_progress_field_missing: 'La partida no contiene itemData.cumulativeFishCount; el progreso acumulado no está disponible.',
  fish_progress_verification_failed: 'La copia editada del progreso acumulado no superó la comprobación de integridad.',
  fish_progress_edit: 'No se pudo preparar la edición del progreso acumulado de fichas.',
  unsupported_fish_progress_serialization: 'La partida no usa el formato JSON canónico admitido para editar el progreso acumulado.',
  outdated_fish_progress_draft: 'El borrador del progreso acumulado usa una edición anterior. Prepara de nuevo la edición antes de subirla.',
  fish_chip_field_missing: 'La partida no contiene gameData.fishChip; la edición de fichas no está disponible.',
  fish_material_field_missing: 'La partida no contiene itemData.materials; la edición de fichas no está disponible.',
  fish_chip_verification_failed: 'La copia editada de fichas no superó la comprobación de integridad.',
  fish_chip_edit: 'No se pudo preparar la edición de fichas de pesca.',
  outdated_fish_chip_draft: 'El borrador de fichas usa una edición anterior. Prepara de nuevo la edición antes de subirla.',
  characters_edit: 'No se pudo preparar el desbloqueo de personajes.',
  invalid_character_selection: 'Selecciona entre 1 y 42 personajes bloqueados, sin repetirlos.',
  unknown_character: 'La selección contiene un personaje que no pertenece al catálogo.',
  character_field_missing: 'La partida no contiene gameData.heroUnlock; el desbloqueo no está disponible.',
  unsupported_characters_structure: 'gameData.heroUnlock no tiene la estructura booleana esperada; no se sobrescribe.',
  character_catalog_missing: 'No está disponible el catálogo local de personajes.',
  character_verification_failed: 'La copia editada de personajes no superó la comprobación de integridad.',
  outdated_character_draft: 'El borrador de personajes usa una selección anterior. Prepara de nuevo el desbloqueo.',
  skills_edit: 'No se pudo preparar el desbloqueo de habilidades.',
  invalid_skill_selection: 'Selecciona entre 1 y 105 habilidades, sin repetir personaje e índice.',
  unknown_skill_character: 'La selección contiene un personaje que no pertenece al catálogo.',
  unknown_skill_index: 'La selección contiene una habilidad que no existe para ese personaje.',
  skill_field_missing: 'La partida no contiene gameData.heroSkillUnlock; el desbloqueo de habilidades no está disponible.',
  incomplete_skill_structure: 'La partida no contiene todas las posiciones de habilidad necesarias. No se crean estructuras faltantes.',
  unsupported_skills_structure: 'gameData.heroSkillUnlock no tiene la estructura esperada; no se sobrescribe.',
  skill_catalog_missing: 'No está disponible el catálogo local de habilidades.',
  skill_verification_failed: 'La copia editada de habilidades no superó la comprobación de integridad.',
  outdated_skill_draft: 'El borrador de habilidades usa una selección anterior. Prepara de nuevo el desbloqueo.',
  skins_edit: 'No se pudo preparar el desbloqueo de skins.',
  invalid_skin_selection: 'Selecciona entre 1 y 802 skins, sin repetir personaje e índice.',
  unknown_skin_character: 'La selección contiene un personaje que no pertenece al catálogo.',
  unknown_skin_index: 'La selección contiene una skin que no existe para ese personaje.',
  skin_field_missing: 'La partida no contiene gameData.skinLock; el desbloqueo de skins no está disponible.',
  incomplete_skin_structure: 'La partida no contiene la posición de skin seleccionada. No se crean entradas faltantes.',
  unsupported_skins_structure: 'gameData.skinLock no tiene la estructura esperada; no se sobrescribe.',
  skin_catalog_missing: 'No está disponible el catálogo local de skins.',
  skin_verification_failed: 'La copia editada de skins no superó la comprobación de integridad.',
  outdated_skin_draft: 'El borrador de skins usa una selección anterior. Prepara de nuevo el desbloqueo.',
  cloud_hash_mismatch: 'La huella del borrador no coincide con la del respaldo. Prepara de nuevo la edición.',
  backup_integrity: 'El respaldo no superó la comprobación de integridad.',
  backup_store: 'No se pudo guardar o leer el respaldo privado.',
}

function friendly(error: ApiProblem, fallback: string): ApiProblem {
  if (error.code === 'inconsistent_gems_balance') return error
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
  const [editorDirty, setEditorDirty] = useState(false)
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
    const message = editorDirty
      ? 'Hay cambios sin guardar. ¿Cerrar sesión y descartarlos? Se eliminará el acceso de este navegador a la cuenta.'
      : '¿Cerrar sesión? Se eliminará el acceso de este navegador a la cuenta.'
    if (!window.confirm(message)) return
    void authOperation.run(async (signal) => {
      await nativeAuth.logout(signal)
      setEditorDirty(false)
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
        onExpired={expired} onDirtyChange={setEditorDirty} /> : view === 'home' ? <HomePage account={{ label: accountLabel, platform, saveStatus: 'Configuración de acceso pendiente' }} />
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

function NativeEditor({ session, initialSave, onExpired, view, platform, accountLabel, onDirtyChange }: {
  session: NativeSession
  initialSave: NativeSaveSummary | null
  onExpired: () => void
  view: CloudView
  platform: string
  accountLabel: string
  onDirtyChange: (dirty: boolean) => void
}) {
  const [save, setSave] = useState<(NativeSaveSummary & { downloaded_at?: string }) | null>(initialSave)
  const [syncResult, setSyncResult] = useState<LabWriteResult | null>(null)
  const [action, setAction] = useState<'download' | 'upload'>('download')
  const [history, setHistory] = useState<Array<LabBackup & { confirmed: boolean }>>([])
  const [backupResult, setBackupResult] = useState<(LabWriteResult | LabVerification) | null>(null)
  const operation = useOperation()
  const historyOperation = useOperation()
  const backupOperation = useOperation()

  async function refreshHistory(signal: AbortSignal) {
    setHistory((await nativeAuth.backups(signal)).backups)
  }

  function run(task: (signal: AbortSignal) => Promise<unknown>, target = operation) {
    void target.run(async (signal) => {
      try {
        await task(signal)
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      }
    })
  }

  useEffect(() => { void historyOperation.run(refreshHistory) }, [])

  const downloading = action === 'download' && operation.pending
  const downloadProblem = action === 'download' ? operation.problem : null
  const initialProblem = !save && !downloadProblem && !syncResult && !downloading ? session.save_error : null
  const noCloudSave = initialProblem === 'native_no_cloud_save' || downloadProblem?.code === 'native_no_cloud_save'
  const waiting = initialProblem === 'native_device_binding_throttled'
    || downloadProblem?.code === 'native_device_binding_throttled'
  const waitUntil = session.binding_wait_until && formatDate(session.binding_wait_until)
  const cloudGems = syncResult?.persisted ? syncResult.remote_gems : save?.gems
  const disabled = operation.pending || backupOperation.pending
  let saveStatus = save ? 'Copia verificada' : 'Partida pendiente de descargar'
  if (downloading) saveStatus = 'Descargando partida…'
  else if (save) saveStatus = 'Editor listo'
  else if (noCloudSave) saveStatus = 'Sin partida en la nube'
  else if (waiting) saveStatus = 'En espera de ChillyRoom'

  function download() {
    setAction('download')
    run(async (signal) => {
      setSyncResult(null)
      setSave(null)
      setSave(await nativeAuth.save(signal))
    })
  }

  async function reload() {
    setAction('download')
    await new Promise<void>((resolve, reject) => {
      run(async (signal) => {
        try {
          setSave(await nativeAuth.save(signal))
          resolve()
        } catch (error) {
          reject(error)
        }
      })
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
            <dt>Gemas</dt>
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
          <span className="backup-amount">
            {gemFormat.format(backup.original_value ?? backup.original_gems)} {backupFieldLabel(backup)}
          </span></summary>
        <div className="backup-body">
          <p>{backup.confirmed ? 'Subida verificada' : 'Edición preparada'} · {formatSize(backup.original_size)}</p>
          <div className="cloud-actions">
            <button className="button quiet" disabled={disabled} onClick={() => {
              setBackupResult(null)
              run(async (signal) => setBackupResult(await nativeAuth.verify(backup.id, signal)), backupOperation)
            }}>Verificar nube</button>
            {session.write_ready && backup.changed && <button className="button quiet" disabled={disabled}
              onClick={() => {
                if (window.confirm(`¿Restaurar el respaldo de ${accountLabel}? Se reemplazará la partida en la nube.`)) {
                  setBackupResult(null)
                  run(async (signal) => {
                    const restored = await nativeAuth.restore(backup.id, signal)
                    setBackupResult(restored)
                    setSyncResult(restored)
                    setSave(null)
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

  return <EditorWorkspace save={save} session={session}
    accountLabel={accountLabel} platform={platform} onExpired={onExpired}
    onDirtyChange={onDirtyChange}
    onReload={() => { void reload() }}
    onUploaded={async () => {
      setSave(await nativeAuth.save(new AbortController().signal))
    }} />
}

function backupFieldLabel(backup: LabBackup) {
  if (backup.field === 'fish_chip') return 'fichas de pesca'
  if (backup.field === 'fish_progress') return 'progreso acumulado de fichas'
  if (backup.field === 'characters') return 'personajes disponibles'
  if (backup.field === 'skills') return 'habilidades'
  if (backup.field === 'skins') return 'skins'
  if (backup.field === 'advanced') return 'materiales, recursos, beneficios, pase y mascotas'
  if (backup.field === 'unified') return 'cambios combinados'
  return 'gemas'
}

function backupMessage(result: LabWriteResult | LabVerification) {
  if ('persisted' in result) {
    return result.persisted ? 'Respaldo restaurado y verificado en la nube.' : 'No se pudo confirmar la restauración.'
  }
  if (result.matches_original) return 'La nube coincide con el respaldo original.'
  if (result.matches_candidate) return 'La nube coincide con la edición guardada.'
  return 'La partida en la nube difiere de las dos versiones del respaldo.'
}
