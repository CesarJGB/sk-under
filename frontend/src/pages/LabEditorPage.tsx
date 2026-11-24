import {
  CircleCheck, CloudDownload, DatabaseBackup, Gem, KeyRound, LoaderCircle,
  LockKeyhole, RefreshCw, RotateCcw, Server, ShieldCheck, TriangleAlert, UploadCloud,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api, type Health, type LabBackup, type LabPrepared, type LabSave, type LabStatus, type LabVerification, type LabWriteResult } from '../api'
import { formatSize } from '../session'
import { Notice, PageTitle, Problem } from '../ui'
import { SaveReportSections } from './SaveReportSections'
import { useOperation } from '../useOperation'

const TEST_VALUE = 1001

function shortHash(value: string) {
  return `${value.slice(0, 12)}…${value.slice(-8)}`
}

function formatDate(value: string) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' }).format(parsed)
}

function statusLabel(status: LabStatus) {
  if (status.mode === 'live') return 'Laboratorio real · escritura habilitada'
  if (status.mode === 'read_only') return 'Laboratorio real · solo lectura'
  return 'Laboratorio no configurado'
}

function sourceLabel(source: string) {
  return source === 'modern-cloud' ? 'ChillyRoom Cloud' : source
}

export function LabEditorPage({ token, setToken, adminToken, setAdminToken, health, loading }: {
  token: string
  setToken: (value: string) => void
  adminToken: string
  setAdminToken: (value: string) => void
  health: Health | null
  loading: boolean
}) {
  const needsToken = health?.access_mode === 'token'
  const canCall = !loading && health !== null && health.access_mode !== 'disabled' &&
    (!needsToken || token.trim().length > 0)
  const [status, setStatus] = useState<LabStatus | null>(null)
  const [backups, setBackups] = useState<LabBackup[]>([])
  const [loaded, setLoaded] = useState<LabSave | null>(null)
  const [prepared, setPrepared] = useState<LabPrepared | null>(null)
  const [writeResult, setWriteResult] = useState<LabWriteResult | null>(null)
  const [verification, setVerification] = useState<LabVerification | null>(null)
  const [restoreResult, setRestoreResult] = useState<LabWriteResult | null>(null)
  const [newGems, setNewGems] = useState(String(TEST_VALUE))
  const [confirmPhrase, setConfirmPhrase] = useState('')
  const [overwriteChecked, setOverwriteChecked] = useState(false)
  const [restorePhrase, setRestorePhrase] = useState('')
  const [selectedBackup, setSelectedBackup] = useState('')

  const statusOperation = useOperation()
  const uncheckedLabel = loading || statusOperation.pending ? 'Comprobando laboratorio'
    : !health ? 'API sin conexión'
    : health.access_mode === 'disabled' ? 'Acceso privado deshabilitado'
    : needsToken && !token.trim() ? 'Autorización requerida'
    : statusOperation.problem ? 'Consulta fallida' : 'Estado sin consultar'
  const loadOperation = useOperation()
  const prepareOperation = useOperation()
  const confirmOperation = useOperation()
  const verifyOperation = useOperation()
  const restoreOperation = useOperation()

  const minGems = status?.min_gems ?? 0
  const maxGems = status?.max_gems ?? 2_147_483_647
  const parsedGems = /^\d+$/.test(newGems) ? Number(newGems) : Number.NaN
  const inputValid = Number.isSafeInteger(parsedGems) && parsedGems >= minGems && parsedGems <= maxGems
  const changed = Boolean(loaded && inputValid && parsedGems !== loaded.gems)
  const preparedStale = Boolean(prepared && (!inputValid || prepared.new_gems !== parsedGems))
  const selected = useMemo(
    () => backups.find((backup) => backup.id === selectedBackup) ?? null,
    [backups, selectedBackup],
  )
  const canConfirm = Boolean(
    prepared &&
    prepared.changed &&
    !preparedStale &&
    status?.write_ready &&
    adminToken.trim() &&
    confirmPhrase.trim().toUpperCase() === 'SUBIR' &&
    overwriteChecked,
  )
  const canRestore = Boolean(
    selected &&
    selected.changed &&
    status?.write_ready &&
    adminToken.trim() &&
    restorePhrase.trim().toUpperCase() === 'RESTAURAR',
  )

  async function refreshLab(signal: AbortSignal) {
    const [statusResult, backupsResult] = await Promise.allSettled([
      api.labStatus(token.trim(), signal),
      api.labBackups(token.trim(), signal),
    ])
    if (statusResult.status === 'rejected') throw statusResult.reason
    const nextBackups = backupsResult.status === 'fulfilled' ? backupsResult.value.backups : []
    setStatus(statusResult.value)
    setBackups(nextBackups)
    setSelectedBackup((current) => nextBackups.some((backup) => backup.id === current)
      ? current
      : nextBackups[0]?.id ?? '')
    return statusResult.value
  }

  useEffect(() => {
    setStatus(null)
    if (!canCall) {
      setBackups([])
      return
    }
    void statusOperation.run(refreshLab)
  }, [canCall, token, loading])

  async function loadSave() {
    setWriteResult(null)
    setVerification(null)
    setRestoreResult(null)
    setPrepared(null)
    const result = await loadOperation.run((signal) => api.labSave(token.trim(), signal))
    if (result) {
      setLoaded(result)
      setNewGems(String(TEST_VALUE))
      await statusOperation.run(refreshLab)
    }
  }

  async function prepareEdit() {
    if (!inputValid) return
    setWriteResult(null)
    setVerification(null)
    setRestoreResult(null)
    setPrepared(null)
    const result = await prepareOperation.run((signal) => api.labPrepare(parsedGems, token.trim(), signal))
    if (result) {
      setPrepared(result)
      setSelectedBackup(result.backup.id)
      setConfirmPhrase('')
      setOverwriteChecked(false)
      await statusOperation.run(refreshLab)
    }
  }

  async function confirmUpload() {
    if (!prepared || !canConfirm) return
    setVerification(null)
    const result = await confirmOperation.run((signal) => api.labConfirm(
      prepared.backup.id, prepared.candidate_sha256, 'SUBIR', token.trim(), adminToken.trim(), signal,
    ))
    if (result) {
      setWriteResult(result)
      setConfirmPhrase('')
      setOverwriteChecked(false)
      await statusOperation.run(refreshLab)
    }
  }

  async function verifyPersistence() {
    const backupId = prepared?.backup.id ?? selected?.id
    if (!backupId) return
    const result = await verifyOperation.run((signal) => api.labVerify(backupId, token.trim(), signal))
    if (result) setVerification(result)
  }

  async function restoreOriginal() {
    if (!selected || !canRestore) return
    setRestoreResult(null)
    const result = await restoreOperation.run((signal) => api.labRestore(
      selected.id, 'RESTAURAR', token.trim(), adminToken.trim(), signal,
    ))
    if (result) {
      setRestoreResult(result)
      setRestorePhrase('')
      await statusOperation.run(refreshLab)
    }
  }

  return (
    <>
      <PageTitle title="Editor de partida">
        Modifica únicamente <code>gameData.gems</code> de la partida auténtica de laboratorio. El resto de los datos se conserva y se verifica antes de cualquier escritura.
      </PageTitle>

      <div className="lab-shell">
        <section className={`lab-hero ${status?.mode === 'live' ? 'is-live' : ''}`} aria-labelledby="lab-hero-title">
          <div className="lab-hero-main">
            <span className="lab-hero-icon"><Gem size={26} aria-hidden="true" /></span>
            <div>
              <h2 id="lab-hero-title">Gemas · laboratorio</h2>
              <p>{status ? statusLabel(status) : uncheckedLabel}</p>
            </div>
          </div>
          <div className="lab-hero-meta">
            {status && <span className={`lab-pill ${status.mode === 'live' ? 'live' : status.mode === 'read_only' ? 'read' : ''}`}>
              <span className="lab-dot" aria-hidden="true" />
              {status.mode === 'live' ? 'Escritura protegida' : status.mode === 'read_only' ? 'Solo lectura' : 'Sin configurar'}
            </span>}
            {status && <span className="lab-mono">{status.backup_count} respaldo{status.backup_count === 1 ? '' : 's'}</span>}
          </div>
        </section>

        {loading && <Notice>Consultando el estado del servicio…</Notice>}
        {!loading && !health && (
          <Notice tone="warning">La API no está disponible. Revisa la conexión y vuelve a cargar la página.</Notice>
        )}
        {!loading && health?.access_mode === 'disabled' && (
          <Notice tone="warning">El administrador debe configurar el acceso privado para usar el laboratorio.</Notice>
        )}
        {!loading && needsToken && (
          <div className="lab-card lab-token-card">
            <div className="lab-card-head">
              <span className="lab-icon"><KeyRound size={20} aria-hidden="true" /></span>
              <div><h3>Acceso al servicio</h3><p>El laboratorio usa el mismo token privado de la API.</p></div>
            </div>
            <label className="lab-field" htmlFor="lab-access-token">
              <span>Token de acceso</span>
              <input id="lab-access-token" className="lab-input" type="password" value={token}
                autoComplete="off" spellCheck={false} onChange={(event) => setToken(event.target.value)} />
            </label>
          </div>
        )}

        {status && (
          <section className="lab-grid" aria-label="Estado del laboratorio">
            <article className="lab-card">
              <div className="lab-card-head">
                <span className="lab-icon"><Server size={20} aria-hidden="true" /></span>
                <div><h3>Estado del laboratorio</h3><p>{status.message}</p></div>
              </div>
              <dl className="lab-facts">
                <div><dt>Modo</dt><dd>{status.mode === 'live' ? 'Real con escritura' : status.mode === 'read_only' ? 'Real de solo lectura' : 'Deshabilitado'}</dd></div>
                <div><dt>Lectura</dt><dd>{status.read_ready ? 'Configurada' : 'Sin configurar'}</dd></div>
                <div><dt>ChillyRoom Cloud</dt><dd>{loadOperation.pending ? 'Consultando'
                  : loadOperation.problem ? 'Última descarga fallida' : loaded ? 'Última descarga verificada' : 'Sin consultar'}</dd></div>
                <div><dt>Escritura</dt><dd>{status.write_ready ? 'Habilitada' : 'Deshabilitada'}</dd></div>
                <div><dt>Autorización administrativa</dt><dd>{status.admin_configured ? 'Configurada en el servidor' : 'No configurada'}</dd></div>
              </dl>
            </article>
            <article className="lab-card">
              <div className="lab-card-head">
                <span className="lab-icon"><ShieldCheck size={20} aria-hidden="true" /></span>
                <div><h3>Límites y seguridad</h3><p>La escritura no se puede activar desde el navegador.</p></div>
              </div>
              <dl className="lab-facts">
                <div><dt>Rango de gemas</dt><dd className="lab-mono">{status.min_gems} – {status.max_gems}</dd></div>
                <div><dt>Respaldo</dt><dd>Privado en el servidor</dd></div>
                <div><dt>Verificación</dt><dd>Descarga posterior por SHA-256</dd></div>
                <div><dt>Contenido expuesto</dt><dd>Gemas, informe saneado y huellas</dd></div>
              </dl>
            </article>
          </section>
        )}

        <section className="lab-card" aria-labelledby="lab-load-title">
          <div className="lab-card-head">
            <span className="lab-icon"><CloudDownload size={20} aria-hidden="true" /></span>
            <div>
              <h3 id="lab-load-title">Partida de laboratorio</h3>
              <p>Descarga autenticada desde la nube. Esta lectura no modifica nada.</p>
            </div>
          </div>
          <div className="lab-load-row">
            <button className="button lab-button" type="button" onClick={loadSave}
              disabled={!canCall || !status?.read_ready || loadOperation.pending}>
              {loadOperation.pending ? <LoaderCircle size={18} className="lab-spin" aria-hidden="true" /> : <RefreshCw size={18} aria-hidden="true" />}
              {loaded ? 'Volver a cargar partida' : 'Cargar partida de laboratorio'}
            </button>
            {loaded && (
              <span className="lab-pill read">
                <span className="lab-dot" aria-hidden="true" />
                {sourceLabel(loaded.remote.source)} · {formatSize(loaded.size)}
              </span>
            )}
          </div>
          {loadOperation.problem && <Problem problem={loadOperation.problem} />}
          {loaded && (
            <div className="lab-save">
              <div className="lab-metric">
                <span className="lab-caption">Gemas actuales</span>
                <strong data-testid="lab-current-gems">{loaded.gems.toLocaleString('es-MX')}</strong>
                <span className="lab-caption">serialzedVersion {loaded.serialzed_version}</span>
              </div>
              <dl className="lab-facts compact">
                <div><dt>Origen</dt><dd>{sourceLabel(loaded.remote.source)}</dd></div>
                <div><dt>Tamaño</dt><dd>{formatSize(loaded.size)}</dd></div>
                <div><dt>SHA-256</dt><dd className="lab-mono" title={loaded.sha256}>{shortHash(loaded.sha256)}</dd></div>
              </dl>
            </div>
          )}
        </section>

        {loaded?.report && <SaveReportSections report={loaded.report} />}

        {loaded && (
          <section className="lab-grid" aria-label="Edición y vista previa">
            <article className="lab-card" aria-labelledby="lab-edit-title">
              <div className="lab-card-head">
                <span className="lab-icon"><Gem size={20} aria-hidden="true" /></span>
                <div><h3 id="lab-edit-title">Modificar gemas</h3><p>Solo se enviará este entero al preparar la copia.</p></div>
              </div>
              <label className="lab-field" htmlFor="lab-new-gems">
                <span>Nueva cantidad de gemas</span>
                <input id="lab-new-gems" className="lab-input" type="number" inputMode="numeric"
                  min={minGems} max={maxGems} step={1} value={newGems} autoComplete="off"
                  aria-invalid={!inputValid} aria-describedby="lab-gems-help"
                  onChange={(event) => setNewGems(event.target.value)} />
                <small id="lab-gems-help" className={!inputValid ? 'invalid' : ''}>
                  {inputValid
                    ? `Entero entre ${minGems} y ${maxGems}. Valor de prueba: 1001.`
                    : `Introduce un entero entre ${minGems} y ${maxGems}.`}
                </small>
              </label>
              <div className="lab-change-preview">
                <div><span className="lab-caption">Actual</span><strong>{loaded.gems.toLocaleString('es-MX')}</strong></div>
                <span className="lab-arrow" aria-hidden="true">→</span>
                <div><span className="lab-caption">Nueva</span><strong>{inputValid ? parsedGems.toLocaleString('es-MX') : '—'}</strong></div>
              </div>
              {inputValid && !changed && (
                <p className="lab-hint">La partida ya tiene {loaded.gems.toLocaleString('es-MX')} gemas. Puedes preparar la operación sin cambios, pero no se subirá nada.</p>
              )}
              <button className="button lab-primary" type="button" onClick={prepareEdit}
                disabled={!inputValid || prepareOperation.pending || !status?.read_ready}>
                {prepareOperation.pending ? <LoaderCircle size={18} className="lab-spin" aria-hidden="true" /> : <DatabaseBackup size={18} aria-hidden="true" />}
                Preparar modificación y respaldo
              </button>
              {prepareOperation.problem && <Problem problem={prepareOperation.problem} />}
            </article>

            <article className="lab-card" aria-labelledby="lab-preview-title">
              <div className="lab-card-head">
                <span className="lab-icon"><ShieldCheck size={20} aria-hidden="true" /></span>
                <div><h3 id="lab-preview-title">Vista previa y respaldo</h3><p>El servidor valida que solo cambie <code>gameData.gems</code>.</p></div>
              </div>
              {!prepared ? (
                <p className="lab-empty">Prepara una modificación para revisar el candidato, su huella y el respaldo privado.</p>
              ) : (
                <div className="lab-preview">
                  <div className={`lab-banner ${prepared.changed ? 'success' : 'warn'}`} role="status">
                    {prepared.changed ? <CircleCheck size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
                    <span>{prepared.validation.message}</span>
                  </div>
                  {preparedStale && (
                    <div className="lab-banner warn" role="status">
                      <TriangleAlert size={18} aria-hidden="true" />
                      <span>La cantidad escrita ya no coincide con esta vista previa. Prepara la modificación de nuevo.</span>
                    </div>
                  )}
                  <dl className="lab-facts compact">
                    <div><dt>Gemas</dt><dd>{prepared.original_gems} → {prepared.new_gems}</dd></div>
                    <div><dt>Cambio</dt><dd>{prepared.changed ? `${prepared.byte_diff.changed_original_bytes} byte(s) distinto(s)` : 'Sin cambios'}</dd></div>
                    <div><dt>Candidato</dt><dd>{formatSize(prepared.candidate_size)}</dd></div>
                    <div><dt>SHA-256 candidato</dt><dd className="lab-mono" title={prepared.candidate_sha256}>{shortHash(prepared.candidate_sha256)}</dd></div>
                    <div><dt>Respaldo</dt><dd className="lab-mono" title={prepared.backup.id}>{prepared.backup.id}</dd></div>
                    <div><dt>Creado</dt><dd>{formatDate(prepared.backup.created_at)}</dd></div>
                    <div><dt>Original</dt><dd className="lab-mono" title={prepared.backup.original_sha256}>{shortHash(prepared.backup.original_sha256)}</dd></div>
                    <div><dt>Estado</dt><dd>{prepared.changed ? 'Listo para confirmar' : 'No se subirá'}</dd></div>
                  </dl>
                  <p className="lab-hint"><LockKeyhole size={15} aria-hidden="true" />El respaldo original y el candidato permanecen en el servidor, fuera del repositorio y sin exponer su contenido al navegador.</p>
                </div>
              )}
            </article>
          </section>
        )}

        {prepared?.changed && (
          <section className="lab-card lab-write-card" aria-labelledby="lab-write-title">
            <div className="lab-card-head">
              <span className="lab-icon"><UploadCloud size={20} aria-hidden="true" /></span>
              <div>
                <h3 id="lab-write-title">Confirmar subida administrativa</h3>
                <p>La API exige autorización administrativa del servidor. No se puede habilitar desde esta página.</p>
              </div>
            </div>
            <div className="lab-admin-row">
              <label className="lab-field" htmlFor="lab-admin-token">
                <span>Token administrativo</span>
                <input id="lab-admin-token" className="lab-input" type="password" value={adminToken}
                  autoComplete="off" spellCheck={false} onChange={(event) => setAdminToken(event.target.value)}
                  aria-describedby="lab-admin-help" />
                <small id="lab-admin-help">Se conserva solo en la memoria de esta pestaña. El servidor lo compara con <code>SK_CLOUD_ADMIN_TOKEN</code>.</small>
              </label>
              <label className="lab-field" htmlFor="lab-confirm-phrase">
                <span>Escribe SUBIR para confirmar</span>
                <input id="lab-confirm-phrase" className="lab-input" type="text" value={confirmPhrase}
                  autoComplete="off" spellCheck={false} onChange={(event) => setConfirmPhrase(event.target.value)}
                  placeholder="SUBIR" />
              </label>
            </div>
            <label className="lab-check">
              <input type="checkbox" checked={overwriteChecked}
                onChange={(event) => setOverwriteChecked(event.target.checked)} />
              <span>Entiendo que esta operación sobrescribe la partida remota de laboratorio.</span>
            </label>
            {!status?.write_ready && (
              <Notice tone="warning">
                El servidor tiene la escritura deshabilitada o le falta la autorización administrativa. La confirmación no está disponible.
              </Notice>
            )}
            <button className="button lab-primary" type="button" onClick={confirmUpload}
              disabled={!canConfirm || confirmOperation.pending}>
              {confirmOperation.pending ? <LoaderCircle size={18} className="lab-spin" aria-hidden="true" /> : <UploadCloud size={18} aria-hidden="true" />}
              Subir partida modificada y verificar
            </button>
            {confirmOperation.problem && <Problem problem={confirmOperation.problem} />}
          </section>
        )}

        {(prepared || writeResult || verification) && (
          <section className="lab-card" aria-labelledby="lab-result-title">
            <div className="lab-card-head">
              <span className="lab-icon"><CircleCheck size={20} aria-hidden="true" /></span>
              <div><h3 id="lab-result-title">Subida y verificación</h3><p>Un 200 no basta: la persistencia se comprueba con una descarga posterior.</p></div>
            </div>
            {writeResult && (
              <div className={`lab-banner ${writeResult.persisted ? 'success' : 'error'}`} role="status">
                {writeResult.persisted ? <CircleCheck size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
                <span>{writeResult.message} {writeResult.remote_gems !== null ? `Gemas remotas: ${writeResult.remote_gems}.` : ''}</span>
              </div>
            )}
            {writeResult && (
              <dl className="lab-facts compact">
                <div><dt>Estado HTTP</dt><dd>{writeResult.status ?? '—'}</dd></div>
                <div><dt>Aceptada</dt><dd>{writeResult.accepted ? 'Sí' : 'No'}</dd></div>
                <div><dt>Persistencia</dt><dd>{writeResult.persisted ? 'Confirmada' : 'No confirmada'}</dd></div>
                <div><dt>SHA-256 remoto</dt><dd className="lab-mono" title={writeResult.remote_sha256 ?? ''}>{writeResult.remote_sha256 ? shortHash(writeResult.remote_sha256) : '—'}</dd></div>
              </dl>
            )}
            {verification && (
              <div className={`lab-banner ${verification.matches_candidate ? 'success' : 'warn'}`} role="status">
                {verification.matches_candidate ? <CircleCheck size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
                <span>{verification.message} {verification.remote_gems !== null ? `Gemas remotas: ${verification.remote_gems}.` : ''}</span>
              </div>
            )}
            <div className="lab-actions">
              <button className="button lab-quiet" type="button" onClick={verifyPersistence}
                disabled={verifyOperation.pending || (!prepared && !selected)}>
                {verifyOperation.pending ? <LoaderCircle size={17} className="lab-spin" aria-hidden="true" /> : <RefreshCw size={17} aria-hidden="true" />}
                Verificar persistencia
              </button>
            </div>
            {verifyOperation.problem && <Problem problem={verifyOperation.problem} />}
          </section>
        )}

        <section className="lab-card" aria-labelledby="lab-backups-title">
          <div className="lab-card-head">
            <span className="lab-icon"><DatabaseBackup size={20} aria-hidden="true" /></span>
            <div><h3 id="lab-backups-title">Respaldos y restauración</h3><p>Los respaldos se guardan en el servidor y se verifican antes de restaurar.</p></div>
          </div>
          {backups.length === 0 ? (
            <p className="lab-empty">Todavía no hay respaldos en este laboratorio.</p>
          ) : (
            <>
              <div className="lab-table-wrap">
                <table className="lab-table">
                  <thead><tr><th scope="col">Creado</th><th scope="col">Gemas</th><th scope="col">Estado</th><th scope="col">Huella</th></tr></thead>
                  <tbody>
                    {backups.map((backup) => (
                      <tr key={backup.id} className={backup.id === selectedBackup ? 'selected' : ''}
                        onClick={() => setSelectedBackup(backup.id)}>
                        <td><button className="lab-row-button" type="button" onClick={() => setSelectedBackup(backup.id)}>{formatDate(backup.created_at)}</button></td>
                        <td className="lab-mono">{backup.original_gems} → {backup.candidate_gems}</td>
                        <td>{backup.changed ? 'Modificado' : 'Sin cambios'}</td>
                        <td className="lab-mono" title={backup.candidate_sha256}>{shortHash(backup.candidate_sha256)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selected && (
                <div className="lab-restore">
                  <p className="lab-hint">Respaldo <span className="lab-mono">{selected.id}</span>. Restaurar reenvía el original solo si la nube contiene exactamente el candidato de este respaldo.</p>
                  <label className="lab-field" htmlFor="lab-restore-phrase">
                    <span>Escribe RESTAURAR para confirmar</span>
                    <input id="lab-restore-phrase" className="lab-input" type="text" value={restorePhrase}
                      autoComplete="off" spellCheck={false} onChange={(event) => setRestorePhrase(event.target.value)}
                      placeholder="RESTAURAR" />
                  </label>
                  <button className="button lab-quiet" type="button" onClick={restoreOriginal}
                    disabled={!canRestore || restoreOperation.pending}>
                    {restoreOperation.pending ? <LoaderCircle size={17} className="lab-spin" aria-hidden="true" /> : <RotateCcw size={17} aria-hidden="true" />}
                    Restaurar original de este respaldo
                  </button>
                  {restoreOperation.problem && <Problem problem={restoreOperation.problem} />}
                  {restoreResult && (
                    <div className={`lab-banner ${restoreResult.persisted ? 'success' : 'error'}`} role="status">
                      {restoreResult.persisted ? <CircleCheck size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
                      <span>{restoreResult.message} {restoreResult.remote_gems !== null ? `Gemas remotas: ${restoreResult.remote_gems}.` : ''}</span>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </section>

        <p className="lab-footnote">
          <LockKeyhole size={17} aria-hidden="true" />
          Esta sección no muestra el contenido privado de la partida ni credenciales de nube. El navegador recibe gemas, el informe saneado de recursos y personajes, hashes y metadatos del respaldo.
        </p>
      </div>
    </>
  )
}
