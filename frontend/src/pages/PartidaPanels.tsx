import { Archive, ChevronDown, Cloud, CloudDownload, Coins, Fish, Gem, RefreshCw, UsersRound } from 'lucide-react'
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
  advanced: 'Materiales y progreso', unified: 'Edición unificada',
}

const backupStatuses = {
  prepared: 'Edición preparada', verified: 'Subida verificada',
  unverified: 'Subida no verificada', unreadable: 'Respaldo ilegible',
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
    if (result.already_original) return 'La nube ya contiene el respaldo original.'
    return result.persisted ? 'Respaldo restaurado y verificado en la nube.' : 'No se pudo confirmar la restauración.'
  }
  if (result.matches_original) return 'La nube coincide con el respaldo original.'
  if (result.matches_candidate) return 'La nube coincide con la edición guardada.'
  return 'La partida en la nube difiere de las dos versiones del respaldo.'
}

export function BackupHistory({ history, pending, problem, result, feedback, disabled, canVerify, canRestore,
  onRefresh, onVerify, onRestore }: {
  history: NativeBackupHistory | null
  pending: boolean
  problem: ReactNode
  result: BackupResult | null
  feedback: ReactNode
  disabled: boolean
  canVerify: boolean
  canRestore: boolean
  onRefresh: () => void
  onVerify: (backup: NativeBackup) => void
  onRestore: (backup: NativeBackup) => void
}) {
  return <section className="panel partida-card partida-history" aria-labelledby="backups-title" aria-busy={pending}>
    <div className="partida-heading partida-history-heading">
      <span className="icon-tile"><Archive size={19} aria-hidden="true" /></span>
      <div>
        <h2 id="backups-title">Historial de respaldos</h2>
        {history && !problem && <p className="partida-muted">
          {history.listed < history.total ? `${amount(history.listed)} de ${amount(history.total)} respaldos`
            : `${amount(history.total)} ${history.total === 1 ? 'respaldo' : 'respaldos'}`}
        </p>}
      </div>
      <button className="button quiet partida-icon-button" type="button" disabled={pending}
        aria-label="Actualizar historial" title="Actualizar historial" onClick={onRefresh}>
        <RefreshCw size={17} aria-hidden="true" />
      </button>
    </div>
    {pending && <Loading>Cargando respaldos…</Loading>}
    {problem}
    {!problem && history?.unreadable ? <Notice tone="warning">
      {history.unreadable === 1 ? 'Se detectó un respaldo ilegible.' : `Se detectaron ${amount(history.unreadable)} respaldos ilegibles.`}
    </Notice> : null}
    {history?.total === 0 && !pending && !problem && <p className="partida-muted">Esta cuenta todavía no tiene respaldos.</p>}
    {!problem && history?.backups.length ? <div className="partida-backup-list">
      {history.backups.map((backup) => <details className="partida-backup" key={backup.id}>
        <summary>
          <span>
            <strong>{backup.field ? fieldLabels[backup.field] : 'Edición sin identificar'}</strong>
            <time className="partida-muted" dateTime={backup.created_at ?? undefined}>{formatDate(backup.created_at)}</time>
          </span>
          <span className="partida-backup-status" data-status={backup.status}>
            {backupStatuses[backup.status]}
            {backup.restoration && <small>{backup.restoration === 'verified' ? 'Restauración verificada' : 'Restauración no verificada'}</small>}
          </span>
          <ChevronDown size={16} aria-hidden="true" />
        </summary>
        <div className="partida-backup-body">
          {backup.status === 'unreadable' ? <p className="partida-muted">
            {backup.problem && backupProblems[backup.problem]}
          </p> : <>
            <div className="partida-backup-details">
              {backup.changes != null ? <p>
                <strong>{amount(backup.changes)} {backup.changes === 1 ? 'cambio registrado' : 'cambios registrados'}</strong>
                {backup.categories?.length ? <small>{backup.categories.map((category) => fieldLabels[category]).join(' · ')}</small> : null}
              </p> : <p><strong>{amount(backup.original_value)} → {amount(backup.candidate_value)}</strong></p>}
              {backup.original_size != null && <small>{formatSize(backup.original_size)}</small>}
            </div>
            {canVerify && <div className="partida-actions">
              <button className="button quiet" disabled={disabled} onClick={() => onVerify(backup)}>Verificar nube</button>
              {canRestore && backup.changed && <button className="button quiet" disabled={disabled}
                onClick={() => onRestore(backup)}>Restaurar respaldo</button>}
            </div>}
            {result?.backup_id === backup.id && <p role="status">{backupMessage(result)}</p>}
          </>}
        </div>
      </details>)}
    </div> : null}
    {feedback}
  </section>
}
