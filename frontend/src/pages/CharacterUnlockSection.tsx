import { useState } from 'react'
import {
  ApiProblem, nativeAuth,
  type LabCharacterPrepared, type LabWriteResult, type SaveCharacterReport,
} from '../api'
import { Loading, Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'

const amountFormat = new Intl.NumberFormat('es-MX')

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
}

export function CharacterUnlockSection({
  characters, saveSha, writeReady, accountLabel, disabled, formatProblem, onExpired, onPrepared,
  selected, onSelectedChange, applied, onApplied,
}: {
  characters: SaveCharacterReport
  saveSha: string
  writeReady: boolean
  accountLabel: string
  disabled: boolean
  selected: Set<string>
  onSelectedChange: (next: Set<string>) => void
  applied: Set<string>
  onApplied: (codes: string[]) => void
  formatProblem: (error: ApiProblem, fallback: string) => ApiProblem
  onExpired: () => void
  onPrepared?: () => void
}) {
  const [prepared, setPrepared] = useState<LabCharacterPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [action, setAction] = useState<'prepare' | 'upload' | null>(null)
  const operation = useOperation()

  const locked = characters.items.filter((character) => (
    character.unlocked === false && !applied.has(character.code)
  ))
  const missing = characters.items.filter((character) => character.unlocked === '<missing>')
  const unlockedCount = result?.persisted
    ? result.remote_characters ?? characters.counts.unlocked
    : Math.min(characters.counts.characters, characters.counts.unlocked + applied.size)
  const names = new Map(characters.items.map((character) => [character.code, character.name]))
  const selectedCodes = locked
    .filter((character) => selected.has(character.code))
    .map((character) => character.code)
  const total = characters.counts.characters
  const catalogUnavailable = characters.catalog.available === false
    || characters.catalog.characters === 0
  const busy = disabled || operation.pending || catalogUnavailable

  function clearPreview() {
    setPrepared(null)
    setConfirm(false)
    setResult(null)
    setAction(null)
  }

  function toggle(code: string) {
    const next = new Set(selected)
    if (next.has(code)) next.delete(code)
    else next.add(code)
    onSelectedChange(next)
    clearPreview()
  }

  function run(task: (signal: AbortSignal) => Promise<void>) {
    void operation.run(async (signal) => {
      try {
        await task(signal)
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      }
    })
  }

  return <section className="cloud-section panel cloud-editor character-unlock-editor"
    aria-labelledby="edit-characters-title" data-testid="character-unlock-section">
    <div className="cloud-section-head">
      <div>
        <span className="cloud-kicker">Confirmado por el propietario · E3</span>
        <h2 id="edit-characters-title">Personajes</h2>
        <p className="cloud-state">{amountFormat.format(total)} en el catálogo · {accountLabel}</p>
      </div>
      <div className="editor-current">
        <span>Disponibles</span>
        <strong data-testid="character-unlocked-count">
          {amountFormat.format(unlockedCount)} / {amountFormat.format(total)}
        </strong>
      </div>
    </div>
    {!writeReady && <Notice tone="warning">
      Puedes preparar el cambio y su respaldo. La subida está deshabilitada.
    </Notice>}
    {catalogUnavailable && <Notice tone="warning">
      <span data-testid="character-catalog-unavailable">
        Catálogo de personajes no disponible. La preparación está bloqueada.
      </span>
    </Notice>}

    <div className="character-unlock-toolbar">
      <span>{selected.size === 0
        ? 'Selecciona personajes bloqueados.'
        : `${amountFormat.format(selected.size)} de ${amountFormat.format(locked.length)} seleccionados.`}</span>
      <div className="cloud-actions">
        <button type="button" className="button quiet" disabled={busy || locked.length === 0}
          onClick={() => {
            onSelectedChange(new Set(locked.map((character) => character.code)))
            clearPreview()
          }}>Seleccionar bloqueados</button>
        <button type="button" className="button quiet" disabled={busy || selected.size === 0}
          onClick={() => {
            onSelectedChange(new Set())
            clearPreview()
          }}>Limpiar selección</button>
      </div>
    </div>

    <ul className="character-unlock-list" aria-label="Personajes del catálogo">
      {characters.items.map((character) => {
        const available = character.unlocked === true || applied.has(character.code)
        const unknown = character.unlocked === '<missing>'
        const level = character.level === '<missing>' ? 'sin dato' : amountFormat.format(character.level)
        return <li key={character.code}
          className={`character-unlock-row ${available ? 'available' : unknown ? 'unknown' : 'locked'}`}
          data-testid={`character-unlock-${character.code}`}>
          {available || unknown ? <span className="character-unlock-mark" aria-hidden="true">
            {available ? '✓' : '?'}
          </span> : <input type="checkbox" checked={selected.has(character.code)}
            aria-label={`Seleccionar ${character.name}`} disabled={busy}
            onChange={() => toggle(character.code)} />}
          <div className="character-unlock-copy">
            <strong>{character.name}</strong>
            <small>{character.code} · nivel {level}</small>
          </div>
          <span className={`report-state ${available ? 'available' : 'locked'}`}>
            {available ? 'Disponible' : unknown ? 'Sin dato' : 'Bloqueado'}
          </span>
        </li>
      })}
    </ul>
    {missing.length > 0 && <p className="cloud-note">
      {missing.length === 1 ? 'Un personaje no tiene dato' : `${missing.length} personajes no tienen dato`};
      no se modifican.
    </p>}

    <div className="cloud-actions">
      <button type="button" className="button primary"
        disabled={busy || selectedCodes.length === 0}
        onClick={() => {
          setAction('prepare')
          run(async (signal) => {
            clearPreview()
            const next = await nativeAuth.prepareCharacters(selectedCodes, saveSha, signal)
            setPrepared(next)
            onPrepared?.()
          })
        }}>Preparar desbloqueo</button>
    </div>

    {prepared && <div className="cloud-preview" data-testid="character-unlock-preview">
      <h3>Revisar desbloqueo</h3>
      <dl className="cloud-preview-data">
        <div><dt>Disponibles ahora</dt><dd>{amountFormat.format(prepared.new_unlocked_count)} / {amountFormat.format(prepared.total_characters)}</dd></div>
        <div><dt>Se desbloquean</dt><dd>{amountFormat.format(prepared.newly_unlocked_codes.length)}</dd></div>
      </dl>
      <p className="cloud-note">
        {prepared.newly_unlocked_codes.map((code) => names.get(code) ?? code).join(', ')}.
      </p>
      <p className="cloud-note">Respaldo cifrado creado. Niveles, habilidades, skins y recursos no cambian.</p>
      <details className="skill-changed-fields">
        <summary>Campos afectados ({amountFormat.format(prepared.changed_fields.length)})</summary>
        <code>{prepared.changed_fields.join(', ')}</code>
      </details>
      {writeReady && !result && <>
        <label className="cloud-check"><input type="checkbox" checked={confirm} disabled={busy}
          onChange={(event) => setConfirm(event.target.checked)} />
          <span>Confirmo sobrescribir la partida de {accountLabel}.</span>
        </label>
        <button type="button" className="button primary"
          disabled={busy || !confirm || !prepared.changed}
          onClick={() => {
            setAction('upload')
            run(async (signal) => {
              setConfirm(false)
              const uploaded = await nativeAuth.confirm(
                prepared.backup.id, prepared.candidate_sha256, signal,
              )
              setResult(uploaded)
              onSelectedChange(new Set())
              onApplied(prepared.newly_unlocked_codes)
              onPrepared?.()
            })
          }}>Desbloquear y verificar</button>
      </>}
    </div>}
    {result && <div role="status" className={`cloud-feedback ${result.persisted ? 'verified' : 'uncertain'}`}>
      {result.persisted
        ? `Desbloqueo verificado en la nube. ${amountFormat.format(result.remote_characters ?? prepared?.new_unlocked_count ?? 0)} de ${amountFormat.format(total)} disponibles.`
        : 'No se pudo confirmar la subida. Verifica el estado desde Partida.'}
    </div>}
    {operation.pending && <Loading>
      {action === 'prepare' ? 'Preparando desbloqueo…' : 'Subiendo y verificando…'}
    </Loading>}
    {operation.problem && <Problem problem={formatProblem(operation.problem,
      action === 'upload'
        ? 'No se pudo confirmar la subida. Verifica el estado desde Partida.'
        : 'No se pudo preparar el desbloqueo. Vuelve a intentarlo.')} />}
  </section>
}