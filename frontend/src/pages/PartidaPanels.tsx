import { Archive, ChevronDown, Cloud, CloudDownload, Coins, Fish, Gem, Plus, RefreshCw, RotateCcw, ShieldCheck, UsersRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { LabVerification, LabWriteResult, NativeBackup, NativeBackupHistory, NativeSaveSummary } from '../api'
import { scalarQuantity } from '../draft'
import { formatSize } from '../session'
import { Loading, Notice } from '../ui'

const amountFormat = new Intl.NumberFormat('es-MX')
const dateFormat = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' })

export function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateFormat.format(date)
}

function amount(value?: number | null) {
  return value == null ? '—' : amountFormat.format(value)
}

function characters(save: NativeSaveSummary) {
  const report = save.report?.characters
  if (!report?.catalog.available || !report.counts.characters) return '—'
  const observed = report.items.filter(({ unlocked }) => typeof unlocked === 'boolean')
  if (!observed.some(({ unlocked }) => unlocked) && observed.length < report.counts.characters) return '—'
  return `${amount(report.counts.unlocked)} / ${amount(report.counts.characters)}`
}

export function CloudSaveCard({ save, status, downloading, disabled, onDownload, feedback }: {
  save: NativeSaveSummary | null
  status: string
  downloading: boolean
  disabled: boolean
  onDownload: () => void
  feedback: ReactNode
}) {
  const metrics = save && [
    { label: 'Gemas', value: amount(scalarQuantity(save, 'gems').original), icon: Gem, testId: 'native-current-gems' },
    { label: 'Fichas de pesca', value: amount(scalarQuantity(save, 'fishChip').original), icon: Fish },
    { label: 'Monedas de temporada', value: amount(scalarQuantity(save, 'seasonCoin').original), icon: Coins },
    { label: 'Personajes desbloqueados', value: characters(save), icon: UsersRound },
  ]

  return <section className="panel partida-card partida-cloud" aria-labelledby="save-title" aria-busy={downloading}>
    <div className="partida-heading">
      <span className="icon-tile"><Cloud size={21} aria-hidden="true" /></span>
      <div>
        <h2 id="save-title">Partida en la nube</h2>
        <p className="partida-muted" role="status">{status}</p>
      </div>
    </div>
    {metrics && <>
      <dl className="partida-metrics">
        {metrics.map(({ label, value, icon: Icon, testId }) => <div key={label}>
          <dt><Icon size={15} aria-hidden="true" />{label}</dt>
          <dd data-testid={testId}>{value}</dd>
        </div>)}
      </dl>
      <dl className="partida-download-date">
        <dt>Última descarga</dt>
        <dd><time dateTime={save.downloaded_at}>{formatDate(save.downloaded_at)}</time></dd>
      </dl>
    </>}
    {feedback}
    <div className="partida-actions">
      {save && <Link className="button primary" to="/editor">Abrir editor</Link>}
      <button className={`button ${save ? 'quiet' : 'primary'}`} disabled={disabled} onClick={onDownload}>
        {save ? <RefreshCw size={16} aria-hidden="true" /> : <CloudDownload size={17} aria-hidden="true" />}
        {downloading ? 'Descargando…' : save ? 'Actualizar partida' : 'Descargar partida'}
      </button>
    </div>
  </section>
}

const fieldLabels: Record<NonNullable<NativeBackup['field']>, string> = {
  gems: 'Gemas', fish_chip: 'Fichas de pesca', fish_progress: 'Recompensas de pesca',
  characters: 'Personajes', skills: 'Habilidades', skins: 'Skins',
  advanced: 'Materiales y progreso', unified: 'Edición unificada', snapshot: 'Copia completa',
}

const backupStatuses: Record<NativeBackup['status'], string> = {
  prepared: 'Edición preparada', verified: 'Subida verificada',
  unverified: 'Subida no verificada', available: 'Respaldo disponible',
  unreadable: 'Respaldo ilegible',
}

const backupKinds: Record<NonNullable<NativeBackup['kind']>, string> = {
  edit: 'Automático antes de editar',
  manual: 'Manual',
  preventive: 'Preventivo antes de restaurar',
}

const backupProblems: Record<NonNullable<NativeBackup['problem']>, string> = {
  authentication: 'No se pudo autenticar el respaldo con la clave y el formato actuales.',
  incompatible: 'El formato del registro no es compatible con este servidor.',
  file_unavailable: 'Falta un archivo del respaldo o no se pudo leer.',
  integrity: 'El respaldo no superó la comprobación de integridad.',
}

type BackupResult = LabVerification | LabWriteResult

function backupMessage(result: BackupResult) {
  if ('persisted' in result) {
    if (result.already_original) return 'La nube ya contiene esa versión; no fue necesario escribir.'
    return result.persisted
      ? 'Restauración verificada: la nube contiene exactamente la versión elegida.'
      : 'No se pudo confirmar la restauración. La nube puede contener otra versión.'
  }
  if (result.matches_original) return 'Verificación correcta: la nube coincide con esa versión.'
  if (result.matches_candidate) return 'La nube coincide con la edición guardada.'
  return 'La partida en la nube difiere de las dos versiones del respaldo.'
}

function backupTitle(backup: NativeBackup) {
  if (backup.kind === 'manual') return 'Respaldo manual'
  if (backup.kind === 'preventive') return 'Respaldo preventivo'
  return backup.field ? fieldLabels[backup.field] : 'Edición sin identificar'
}

function snapshotRows(summary: NativeBackup['summary']) {
  if (!summary) return []
  const rows: Array<[string, string]> = []
  if (summary.gems != null) rows.push(['Gemas', amount(summary.gems)])
  if (summary.fish_chip != null) rows.push(['Fichas de pesca', amount(summary.fish_chip)])
  if (summary.cumulative_fish_count != null) rows.push(['Progreso de pesca', amount(summary.cumulative_fish_count)])
  if (summary.characters != null) rows.push(['Personajes', amount(summary.characters)])
  if (summary.skills != null) rows.push(['Habilidades', amount(summary.skills)])
  if (summary.skins != null) rows.push(['Skins', amount(summary.skins)])
  if (summary.game_version) rows.push(['Versión del juego', summary.game_version])
  if (summary.save_size != null) rows.push(['Tamaño', formatSize(summary.save_size)])
  return rows
}

function BackupSummary({ backup }: { backup: NativeBackup }) {
  const rows = snapshotRows(backup.summary)
  if (backup.changed != null && rows.length) {
    return <dl className="partida-backup-summary">
      {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
    </dl>
  }
  return <>
    <div className="partida-backup-details">
      {backup.changes != null ? <p>
        <strong>{amount(backup.changes)} {backup.changes === 1 ? 'cambio registrado' : 'cambios registrados'}</strong>
        {backup.categories?.length ? <small>{backup.categories.map((category) => fieldLabels[category]).join(' · ')}</small> : null}
      </p> : backup.original_value != null || backup.candidate_value != null
        ? <p><strong>{amount(backup.original_value)} → {amount(backup.candidate_value)}</strong></p> : null}
      {backup.original_size != null && <small>{formatSize(backup.original_size)}</small>}
    </div>
    {rows.length > 0 && <dl className="partida-backup-summary">
      {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
    </dl>}
  </>
}

export function RestoreDialog({ backup, accountLabel, pending, onCancel, onConfirm }: {
  backup: NativeBackup
  accountLabel: string
  pending: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const title = backupTitle(backup)
  return <div className="partida-dialog-backdrop" role="presentation" onClick={(event) => {
    if (event.target === event.currentTarget && !pending) onCancel()
  }}>
    <section className="partida-dialog" role="dialog" aria-modal="true" aria-labelledby="restore-title">
      <div className="partida-heading">
        <span className="icon-tile"><RotateCcw size={19} aria-hidden="true" /></span>
        <div>
          <h2 id="restore-title">Restaurar {title.toLowerCase()}</h2>
          <p className="partida-muted">{formatDate(backup.created_at)}</p>
        </div>
      </div>
      <BackupSummary backup={backup} />
      <Notice tone="warning">
        Se reemplazará el progreso actual de {accountLabel} en la nube. Antes de escribir se creará
        un respaldo preventivo de la partida actual, que podrás restaurar para deshacer este cambio.
      </Notice>
      <p className="partida-muted">
        La partida en la nube se comprobará antes y después de escribir. Si cambió desde la última
        descarga, la restauración se detendrá sin modificar nada.
      </p>
      <div className="partida-actions">
        <button className="button quiet" type="button" disabled={pending} onClick={onCancel}>Cancelar</button>
        <button className="button primary" type="button" disabled={pending} onClick={onConfirm}>
          {pending ? 'Restaurando…' : 'Restaurar esta versión'}
        </button>
      </div>
    </section>
  </div>
}

export function BackupHistory({ history, pending, loadingMore, problem, result, feedback, disabled, canVerify, canRestore,
  canBackup, creatingBackup, onRefresh, onLoadMore, onVerify, onRestore, onCreateBackup }: {
  history: NativeBackupHistory | null
  pending: boolean
  loadingMore: boolean
  problem: ReactNode
  result: BackupResult | null
  feedback: ReactNode
  disabled: boolean
  canVerify: boolean
  canRestore: boolean
  canBackup: boolean
  creatingBackup: boolean
  onRefresh: () => void
  onLoadMore: () => void
  onVerify: (backup: NativeBackup) => void
  onRestore: (backup: NativeBackup) => void
  onCreateBackup: () => void
}) {
  return <section className="panel partida-card partida-history" aria-labelledby="backups-title" aria-busy={pending || loadingMore}>
    <div className="partida-heading partida-history-heading">
      <span className="icon-tile"><Archive size={19} aria-hidden="true" /></span>
      <div>
        <h2 id="backups-title">Historial de respaldos</h2>
        {history && !problem && <p className="partida-muted">
          {history.listed < history.total ? `${amount(history.listed)} de ${amount(history.total)} respaldos`
            : `${amount(history.total)} ${history.total === 1 ? 'respaldo' : 'respaldos'}`}
        </p>}
      </div>
      {canBackup && <button className="button quiet partida-create-backup" type="button" disabled={disabled || creatingBackup}
        onClick={onCreateBackup}>
        <Plus size={16} aria-hidden="true" />{creatingBackup ? 'Creando…' : 'Crear respaldo'}
      </button>}
      <button className="button quiet partida-icon-button" type="button" disabled={pending || loadingMore}
        aria-label="Actualizar historial" title="Actualizar historial" onClick={onRefresh}>
        <RefreshCw size={17} aria-hidden="true" />
      </button>
    </div>
    {pending && <Loading>Cargando respaldos…</Loading>}
    {problem}
    {!problem && history?.unreadable ? <Notice tone="warning">
      {history.unreadable === 1 ? 'Se detectó un respaldo ilegible.' : `Se detectaron ${amount(history.unreadable)} respaldos ilegibles.`}
    </Notice> : null}
    {history?.total === 0 && !pending && !problem && <p className="partida-muted">
      Esta cuenta todavía no tiene respaldos. Se creará uno automáticamente antes de cada edición.
    </p>}
    {!problem && history?.backups.length ? <div className="partida-backup-list">
      {history.backups.map((backup) => <details className="partida-backup" key={backup.id}>
        <summary>
          <span>
            <strong>{backupTitle(backup)}</strong>
            <time className="partida-muted" dateTime={backup.created_at ?? undefined}>{formatDate(backup.created_at)}</time>
            {backup.kind && <small className="partida-backup-kind">{backupKinds[backup.kind]}</small>}
          </span>
          <span className="partida-backup-status" data-status={backup.status}>
            {backupStatuses[backup.status]}
            {backup.interrupted && <small>Operación interrumpida</small>}
            {!backup.interrupted && backup.restoration && <small>
              {backup.restoration === 'verified' ? 'Restauración verificada' : 'Restauración no verificada'}
            </small>}
          </span>
          <ChevronDown size={16} aria-hidden="true" />
        </summary>
        <div className="partida-backup-body">
          {backup.status === 'unreadable' ? <>
            <p className="partida-muted">{backup.problem ? backupProblems[backup.problem] : 'No se pudo leer este respaldo.'}</p>
            <p className="partida-muted">No se restaurará porque no superó la comprobación de integridad.</p>
          </> : <>
            <BackupSummary backup={backup} />
            <p className="partida-backup-integrity">
              <ShieldCheck size={14} aria-hidden="true" />
              {backup.integrity === 'verified' ? 'Integridad del respaldo verificada' : 'Integridad comprobada'}
            </p>
            {backup.kind === 'manual' && <p className="partida-muted">
              Copia creada a voluntad; no se escribió nada en ChillyRoom.
            </p>}
            {backup.kind === 'preventive' && <p className="partida-muted">
              Se creó automáticamente antes de restaurar otra versión. Restáuralo para deshacer esa restauración.
            </p>}
            {canVerify && <div className="partida-actions">
              <button className="button quiet" disabled={disabled} onClick={() => onVerify(backup)}>Verificar contra la nube</button>
              {canRestore && backup.can_restore !== false && <button className="button quiet" disabled={disabled}
                onClick={() => onRestore(backup)}>
                {backup.kind === 'preventive' ? 'Deshacer restauración' : 'Restaurar esta versión'}
              </button>}
            </div>}
            {result?.backup_id === backup.id && <p role="status">{backupMessage(result)}</p>}
          </>}
        </div>
      </details>)}
    </div> : null}
    {!problem && history?.next_cursor && <button className="button quiet partida-load-more" type="button"
      disabled={loadingMore} onClick={onLoadMore}>
      {loadingMore ? 'Cargando…' : 'Cargar más respaldos'}
    </button>}
    {feedback}
  </section>
}
