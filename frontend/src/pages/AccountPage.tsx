import { CloudDownload } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router'
import {
  ApiProblem, nativeAuth,
  type LabVerification, type LabWriteResult, type NativeBackup, type NativeBackupHistory,
  type NativeSaveSummary, type NativeSession,
} from '../api'
import { useAccounts, accountById, findSession } from '../AccountContext'
import { accountDisplay, useEmailPrivacy } from '../accountPrivacy'
import { cacheSave, cachedSave } from '../accountCache'
import {
  BLOCKED_AUTO_SAVE_ERRORS, distributionLabel, friendly, historyProblemMessage, isExpired, platformLabel,
} from '../accountMessages'
import { Loading, Notice, PageTitle, Problem } from '../ui'
import { useOperation } from '../useOperation'
import { AccountHeader } from './AccountHeader'
import { AccountLoginForm } from './AccountLoginForm'
import { BackupHistory, CloudSaveCard, RestoreDialog, formatDate } from './PartidaPanels'
import { EditorWorkspace } from './EditorWorkspace'

type Section = 'partida' | 'editor'

function sectionOf(pathname: string, base: string) {
  const suffix = pathname.slice(base.length)
  if (suffix === '/editor' || suffix.startsWith('/editor/')) return { section: 'editor' as const, valid: true }
  if (suffix === '' || suffix === '/partida') return { section: 'partida' as const, valid: true }
  return { section: 'partida' as const, valid: false }
}

function tagsOf(session: NativeSession | null | undefined) {
  const platform = platformLabel(session?.account?.platform) || 'Android'
  const distribution = distributionLabel(session?.account?.distribution_label ?? '').replace(/^Android\s+/i, '')
  return { platform, distribution: distribution || 'Global' }
}

export function AccountPage() {
  const { pathname } = useLocation()
  const params = useParams()
  const accountId = params.accountId || pathname.match(/^\/cuentas\/([^/]+)/)?.[1] || ''
  const navigate = useNavigate()
  const { config, accounts, reload, loading: accountsLoading } = useAccounts()
  const [hideEmail] = useEmailPrivacy()
  const [session, setSession] = useState<NativeSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [problem, setProblem] = useState<ApiProblem | null>(null)
  const base = `/cuentas/${encodeURIComponent(accountId)}`
  const route = sectionOf(pathname, base)

  useEffect(() => {
    setSession(null)
    setProblem(null)
    setLoading(true)
    const controller = new AbortController()
    void nativeAuth.session(controller.signal, accountId).then((next) => {
      if (controller.signal.aborted) return
      if (next.active || next.expired || next.reason === 'expired') {
        setSession(next)
        if (!next.active) void reload()
        return
      }
      void reload()
      navigate('/', { replace: true })
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return
      if (error instanceof ApiProblem &&
        (error.code === 'native_account_denied' || error.code === 'native_session_required' || isExpired(error))) {
        void reload()
        navigate('/', { replace: true })
        return
      }
      setProblem(error instanceof ApiProblem ? error : new ApiProblem('No se pudo abrir la cuenta.'))
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [accountId, navigate, reload])

  if (!route.valid) return <Navigate to={`${base}/partida`} replace />

  const index = accounts.findIndex((account) => account.id === accountId)
  const contextAccount = accountById(accounts, accountId) ?? findSession(accounts, session)
  const display = accountDisplay(session ?? contextAccount, {
    index: index >= 0 ? index : 0,
    total: accounts.length || 1,
    hideEmail,
  })
  const tags = tagsOf(session ?? contextAccount)
  const distributionId = (session ?? contextAccount)?.account?.distribution
  const gameVersion = config?.distributions.find((item) => item.id === distributionId)?.game_version

  const header = <AccountHeader accountLabel={display.label} accountTitle={display.title}
    platform={tags.platform} distribution={tags.distribution} gameVersion={gameVersion}
    basePath={base} section={route.section} />

  if (loading && !session) return <>
    {header}
    <main id="content" className="shell main-content main-partida"><Loading>Abriendo la cuenta…</Loading></main>
  </>

  if (problem) return <>
    {header}
    <main id="content" className="shell main-content main-partida">
      <Problem problem={friendly(problem, 'No se pudo abrir la cuenta. Vuelve al dashboard.')} />
      <button className="button primary" type="button" onClick={() => navigate('/')}>Volver al inicio</button>
    </main>
  </>

  if (!session) return <>
    {header}
    <main id="content" className="shell main-content main-partida">
      {accountsLoading ? <Loading>Comprobando la cuenta…</Loading> : <Navigate to="/" replace />}
    </main>
  </>

  if (!session.active) {
    return <>
      {header}
      <main id="content" className="shell main-content main-partida">
        <PageTitle title="Renovar acceso" />
        <Notice tone="warning">La sesión de esta cuenta caducó. Solo necesitas volver a autenticarla.</Notice>
        {config ? <AccountLoginForm config={config} reauth onCancel={() => navigate('/')}
          onSuccess={(next) => {
            setSession(next)
            void reload()
            navigate(`/cuentas/${next.account_id || accountId}/partida`, { replace: true })
          }} />
          : <Loading>Cargando el formulario de acceso…</Loading>}
      </main>
    </>
  }

  return <>
    {header}
    <main id="content" className={`shell main-content ${route.section === 'editor' ? 'main-editor' : 'main-partida'}`}>
      <AccountWorkspace key={accountId} section={route.section} basePath={base} accountId={accountId}
        session={session}
        accountLabel={display.label} onSession={setSession} onExpired={() => {
          setSession((current) => current && { ...current, active: false, reason: 'expired', expired: true })
          void reload()
        }} />
    </main>
  </>
}

function AccountWorkspace({
  section, basePath, accountId, session, accountLabel, onSession, onExpired,
}: {
  section: Section
  basePath: string
  accountId: string
  session: NativeSession
  accountLabel: string
  onSession: (session: NativeSession) => void
  onExpired: () => void
}) {
  const { pathname } = useLocation()
  const inCategoryDetail = section === 'editor' && pathname.startsWith(`${basePath}/editor/categoria/`)
  const [save, setSave] = useState<NativeSaveSummary | null>(session.save ?? cachedSave(accountId))
  const [saveOutdated, setSaveOutdated] = useState(false)
  const [history, setHistory] = useState<NativeBackupHistory | null>(null)
  const [backupResult, setBackupResult] = useState<(LabWriteResult | LabVerification) | null>(null)
  const [restoreTarget, setRestoreTarget] = useState<NativeBackup | null>(null)
  const [backupNotice, setBackupNotice] = useState<string | null>(null)
  const [serverNotice, setServerNotice] = useState<string | null>(null)
  const operation = useOperation()
  const historyOperation = useOperation()
  const moreOperation = useOperation()
  const backupOperation = useOperation()
  const installOperation = useOperation()
  const historyRequest = useRef<AbortSignal | null>(null)
  const autoDownloaded = useRef(false)

  useEffect(() => {
    if (!backupNotice) return
    const timer = window.setTimeout(() => setBackupNotice(null), 4000)
    return () => window.clearTimeout(timer)
  }, [backupNotice])

  function run(task: (signal: AbortSignal) => Promise<unknown>, target = operation) {
    return target.run(async (signal) => {
      try {
        await task(signal)
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      }
    })
  }

  useEffect(() => {
    const controller = new AbortController()
    void nativeAuth.version(controller.signal).then((server) => {
      if (controller.signal.aborted) return
      if (!server.features?.includes('native_backup_history')) {
        setServerNotice('El servidor desplegado no incluye el historial de respaldos actualizado.')
      }
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return
      setServerNotice(error instanceof ApiProblem && error.status === 404
        ? 'No se pudo comprobar la versión del servidor. Si el historial falla, actualiza el backend.'
        : null)
    })
    return () => controller.abort()
  }, [])

  function refreshHistory(afterMutation = false) {
    if (!afterMutation && historyRequest.current && !historyRequest.current.aborted) return
    void run(async (signal) => {
      historyRequest.current = signal
      try {
        const next = await nativeAuth.backups(signal, undefined, accountId)
        if (!signal.aborted) setHistory(next)
      } finally {
        if (historyRequest.current === signal) historyRequest.current = null
      }
    }, historyOperation)
  }

  function loadMoreHistory() {
    const cursor = history?.next_cursor
    if (!cursor) return
    void moreOperation.run(async (signal) => {
      const next = await nativeAuth.backups(signal, cursor, accountId)
      if (signal.aborted) return
      setHistory((previous) => {
        if (!previous) return next
        const known = new Set(previous.backups.map(({ id }) => id))
        const added = next.backups.filter(({ id }) => !known.has(id))
        return { ...next, backups: [...previous.backups, ...added], listed: previous.listed + added.length }
      })
    })
  }

  useEffect(() => {
    if (section !== 'partida') return
    let active = true
    queueMicrotask(() => { if (active) refreshHistory() })
    return () => { active = false }
  }, [section])

  const downloading = operation.pending
  const downloadProblem = operation.problem
  const initialProblem = !save && !downloadProblem && !downloading ? session.save_error : null
  const noCloudSave = initialProblem === 'native_no_cloud_save' || downloadProblem?.code === 'native_no_cloud_save'
  const waiting = initialProblem === 'native_device_binding_throttled'
    || downloadProblem?.code === 'native_device_binding_throttled'
  const waitUntil = session.binding_wait_until && formatDate(session.binding_wait_until)
  const disabled = downloading || backupOperation.pending
  let saveStatus = 'Partida pendiente de descargar'
  if (downloading) saveStatus = 'Descargando partida…'
  else if (save) saveStatus = saveOutdated || downloadProblem ? 'Copia anterior · Actualización pendiente' : 'Copia descargada'
  else if (noCloudSave) saveStatus = 'Sin partida en la nube'
  else if (waiting) saveStatus = 'En espera de ChillyRoom'
  else if (downloadProblem || initialProblem) saveStatus = 'Error de descarga'

  async function reload(signal: AbortSignal) {
    const next = await nativeAuth.save(signal, accountId)
    if (!signal.aborted) {
      setSave(next)
      cacheSave(accountId, next)
      setSaveOutdated(false)
      operation.clearProblem()
    }
    return next
  }

  function download() {
    void run(reload)
  }

  useEffect(() => {
    if (!session.installation_ready) return
    const needsSave = !save
    const needsReport = section === 'editor' && Boolean(save && !save.report)
    if (!needsSave && !needsReport) return
    if (needsSave && session.save_error && BLOCKED_AUTO_SAVE_ERRORS.has(session.save_error)) return
    if (autoDownloaded.current) return

    autoDownloaded.current = true
    let fired = false
    // Espera un turno: StrictMode cancela este efecto antes de lanzar la descarga duplicada.
    const timer = window.setTimeout(() => {
      fired = true
      download()
    }, 0)
    return () => {
      window.clearTimeout(timer)
      if (!fired) autoDownloaded.current = false
    }
  }, [session.installation_ready, session.save_error, save?.sha256, save?.report, section])

  function verify(backup: NativeBackup) {
    setBackupResult(null)
    setBackupNotice(null)
    void run(async (signal) => {
      const result = await nativeAuth.verify(backup.id, signal, accountId)
      if (!signal.aborted) setBackupResult(result)
    }, backupOperation)
  }

  function requestRestore(backup: NativeBackup) {
    setBackupResult(null)
    setBackupNotice(null)
    setRestoreTarget(backup)
  }

  function restore() {
    const target = restoreTarget
    if (!target) return
    void run(async (signal) => {
      try {
        const restored = await nativeAuth.restoreHistory(target.id, save?.sha256 ?? null, signal, accountId)
        if (signal.aborted) return
        setRestoreTarget(null)
        setBackupResult(restored)
        setSaveOutdated(true)
        refreshHistory(true)
        download()
      } catch (error) {
        if (!signal.aborted) setRestoreTarget(null)
        throw error
      }
    }, backupOperation)
  }

  function createBackup() {
    setBackupResult(null)
    setBackupNotice(null)
    void run(async (signal) => {
      const result = await nativeAuth.createBackup(signal, accountId)
      if (signal.aborted) return
      setBackupNotice(result.message.includes('manual') ? 'Respaldo creado' : result.message)
      refreshHistory(true)
    }, backupOperation)
  }

  function install(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const uniqueId = String(new FormData(form).get('unique_id') ?? '').trim()
    if (!uniqueId) return
    void installOperation.run(async (signal) => {
      const next = await nativeAuth.installation(uniqueId, signal, accountId)
      if (signal.aborted) return
      onSession(next)
      form.reset()
    })
  }

  const downloadFeedback = noCloudSave ? <p className="cloud-note">
    Guarda una copia desde Soul Knight y vuelve a intentar la descarga.
  </p> : waiting ? <Notice tone="warning">
    ChillyRoom está aplicando una espera para este dispositivo.
    {waitUntil && waitUntil !== '—' ? ` Vuelve a intentarlo después de ${waitUntil}.` : ' Espera antes de volver a intentarlo.'}
  </Notice> : downloadProblem ? <Problem problem={friendly(downloadProblem, 'No se pudo descargar la partida. Vuelve a intentarlo.')} />
    : initialProblem ? <Notice tone="warning">No se pudo comprobar la partida. Intenta descargarla de nuevo.</Notice> : null

  const installationPanel = !session.installation_ready && <section className="panel partida-card">
    <h2>Configuración de acceso pendiente</h2>
    <p className="partida-muted">Contacta con el administrador para completar el acceso a la partida.</p>
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
  </section>

  if (section === 'partida') return <>
    <PageTitle title="Partida" />
    {installationPanel || <CloudSaveCard save={save} status={saveStatus} downloading={downloading}
      disabled={disabled} onDownload={download} editorHref={`${basePath}/editor`} feedback={<>
        {downloadFeedback}
        {!session.write_ready && <p className="partida-muted">
          {session.account?.platform === 'ios'
            ? 'iOS: descarga, respaldos y preparación de cambios disponibles. La subida remota está pendiente de validación; no se envía nada a la nube.'
            : 'Acceso a la nube de solo lectura.'}
        </p>}
      </>} />}
    <BackupHistory history={history} pending={historyOperation.pending} loadingMore={moreOperation.pending}
      result={backupResult}
      problem={(serverNotice || historyOperation.problem || moreOperation.problem) ? <>
        {serverNotice && <Notice tone="warning">{serverNotice}</Notice>}
        {historyOperation.problem && <Problem problem={historyProblemMessage(historyOperation.problem)} />}
        {moreOperation.problem && <Problem problem={historyProblemMessage(moreOperation.problem)} />}
      </> : null}
      feedback={<>
        {backupOperation.pending && <Loading>Consultando la nube…</Loading>}
        {backupOperation.problem && <Problem problem={friendly(backupOperation.problem, 'No se pudo completar la operación del respaldo.')} />}
      </>}
      canVerify={Boolean(session.installation_ready)} canRestore={Boolean(session.write_ready)}
      canBackup={Boolean(session.installation_ready)} creatingBackup={backupOperation.pending}
      disabled={disabled} onRefresh={() => refreshHistory(true)} onLoadMore={loadMoreHistory}
      onVerify={verify} onRestore={requestRestore} onCreateBackup={createBackup} />
    {restoreTarget && <RestoreDialog backup={restoreTarget} accountLabel={accountLabel}
      pending={backupOperation.pending} onCancel={() => setRestoreTarget(null)} onConfirm={restore} />}
    {backupNotice && <p className="partida-toast" role="status">{backupNotice}</p>}
  </>

  return <>
    {!inCategoryDetail && <PageTitle title="Editor" />}
    {!save ? <>
      {installationPanel || <section className="cloud-empty panel">
        {downloadFeedback}
        <button className="button primary" disabled={disabled} onClick={download}>
          <CloudDownload size={18} aria-hidden="true" />
          {downloading ? 'Descargando…' : 'Descargar partida'}
        </button>
      </section>}
    </> : installationPanel || <EditorWorkspace save={save} session={session}
      accountId={accountId} basePath={basePath}
      accountLabel={accountLabel} onExpired={onExpired}
      loadingSave={downloading} loadProblem={downloadProblem} onReload={reload}
      onBackupChanged={() => refreshHistory(true)} onCloudWrite={() => setSaveOutdated(true)} />}
  </>
}