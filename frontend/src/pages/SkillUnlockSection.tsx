import { useState } from 'react'
import {
  ApiProblem, nativeAuth,
  type LabSkillPrepared, type LabSkillRef, type LabWriteResult, type SaveCharacter,
  type SaveCharacterReport,
} from '../api'
import { Loading, Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'
import { skillKey } from '../unlockSelections'

const amountFormat = new Intl.NumberFormat('es-MX')

type SkillFilter = 'pending' | 'all' | 'available' | 'locked' | 'incomplete'
type SkillState = 'available' | 'pending' | 'unknown'

type SkillOptionView = {
  index: number
  name: string
  state: SkillState
}

type CharacterSkills = {
  character: SaveCharacter
  options: SkillOptionView[]
  available: number
  pending: number
  unknown: number
  hasData: boolean
}

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
}

export function SkillUnlockSection({
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
  onApplied: (keys: string[]) => void
  formatProblem: (error: ApiProblem, fallback: string) => ApiProblem
  onExpired: () => void
  onPrepared?: () => void
}) {
  const [prepared, setPrepared] = useState<LabSkillPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [action, setAction] = useState<'prepare' | 'upload' | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<SkillFilter>('pending')
  const operation = useOperation()

  const summary = characters.skills ?? {
    total: 0,
    unlocked: 0,
    locked: 0,
    selected: 0,
    characters_with_data: 0,
    status: 'read_only' as const,
  }
  const characterViews: CharacterSkills[] = characters.items.map((character) => {
    const options = character.skill_options.map((option) => {
      const observed = character.skills.find((entry) => entry.key === option.index)
      const key = skillKey(character.code, option.index)
      const state: SkillState = observed?.unlocked === true || applied.has(key)
        ? 'available'
        : observed?.unlocked === false
          ? 'pending'
          : 'unknown'
      return { index: option.index, name: option.name, state }
    })
    return {
      character,
      options,
      available: options.filter((option) => option.state === 'available').length,
      pending: options.filter((option) => option.state === 'pending').length,
      unknown: options.filter((option) => option.state === 'unknown').length,
      hasData: options.length > 0,
    }
  })
  const pendingKeys = characterViews.flatMap((view) => view.options
    .filter((option) => option.state === 'pending')
    .map((option) => skillKey(view.character.code, option.index)))
  const selectedRefs: LabSkillRef[] = characterViews.flatMap((view) => view.options
    .filter((option) => option.state === 'pending'
      && selected.has(skillKey(view.character.code, option.index)))
    .map((option) => ({ code: view.character.code, index: option.index })))
  const total = summary.total
  const catalogUnavailable = characters.catalog.available === false
    || characters.catalog.characters === 0
    || total === 0
  const busy = disabled || operation.pending || catalogUnavailable
  const unlockedCount = result?.persisted
    ? result.remote_skills ?? summary.unlocked
    : Math.min(total, summary.unlocked + applied.size)
  const lockedCount = Math.max(0, total - unlockedCount)
  const names = new Map(characters.items.map((character) => [character.code, character.name]))
  const skillNames = new Map(characterViews.flatMap((view) => view.options.map((option) => [
    skillKey(view.character.code, option.index), option.name,
  ] as const)))
  const affectedNames = (prepared?.affected_codes ?? [])
    .map((code) => names.get(code) ?? code)
    .join(', ')
  const selectedCharacterCodes = new Set(selectedRefs.map((skill) => skill.code))
  const selectedLockedCharacters = characterViews.filter((view) => (
    selectedCharacterCodes.has(view.character.code) && view.character.unlocked !== true
  ))

  const normalizedQuery = query.trim().toLowerCase()
  const visibleViews = characterViews.filter((view) => {
    const matchesQuery = !normalizedQuery
      || view.character.name.toLowerCase().includes(normalizedQuery)
      || view.character.code.toLowerCase().includes(normalizedQuery)
    if (!matchesQuery) return false
    if (filter === 'pending') return view.pending > 0
    if (filter === 'available') return view.available > 0
    if (filter === 'locked') return view.character.unlocked !== true
    if (filter === 'incomplete') return view.unknown > 0 || !view.hasData
    return true
  })

  function clearPreview() {
    setPrepared(null)
    setConfirm(false)
    setResult(null)
  }

  function toggle(code: string, index: number) {
    const key = skillKey(code, index)
    const next = new Set(selected)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    onSelectedChange(next)
    clearPreview()
  }

  function addKeys(keys: string[]) {
    onSelectedChange(new Set([...selected, ...keys]))
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

  return <section className="cloud-section panel cloud-editor skill-unlock-editor"
    aria-labelledby="edit-skills-title" data-testid="skill-unlock-section">
    <div className="cloud-section-head">
      <div>
        <span className="cloud-kicker">Confirmado por el propietario · E3</span>
        <h2 id="edit-skills-title">Habilidades</h2>
        <p className="cloud-state">{amountFormat.format(total)} en el catálogo · {accountLabel}</p>
      </div>
      <div className="editor-current">
        <span>Desbloqueadas</span>
        <strong data-testid="skill-unlocked-count">
          {amountFormat.format(unlockedCount)} / {amountFormat.format(total)}
        </strong>
      </div>
    </div>

    <div className="skill-summary" aria-label="Resumen de habilidades">
      <div><span>Conocidas</span><strong>{amountFormat.format(total)}</strong></div>
      <div><span>Desbloqueadas</span><strong>{amountFormat.format(unlockedCount)}</strong></div>
      <div><span>Bloqueadas</span><strong>{amountFormat.format(lockedCount)}</strong></div>
    </div>

    {!writeReady && <Notice tone="warning">
      Puedes preparar el cambio y su respaldo. La subida está deshabilitada.
    </Notice>}
    {catalogUnavailable && <Notice tone="warning">
      <span data-testid="skill-catalog-unavailable">
        Catálogo de habilidades no disponible. La preparación está bloqueada.
      </span>
    </Notice>}
    {summary.characters_with_data < characters.items.length && !catalogUnavailable && <Notice tone="info">
      Algunos personajes no tienen datos de habilidades; sus posiciones no se modifican.
    </Notice>}

    <div className="skill-filters">
      <label className="cloud-field">
        <span>Buscar personaje</span>
        <input type="search" value={query} disabled={busy} placeholder="Nombre o código"
          onChange={(event) => setQuery(event.target.value)} />
      </label>
      <label className="cloud-field">
        <span>Filtro</span>
        <select value={filter} disabled={busy}
          onChange={(event) => setFilter(event.target.value as SkillFilter)}>
          <option value="pending">Con pendientes</option>
          <option value="available">Con disponibles</option>
          <option value="locked">Personajes bloqueados</option>
          <option value="incomplete">Con datos incompletos</option>
          <option value="all">Todos</option>
        </select>
      </label>
    </div>

    <div className="character-unlock-toolbar">
      <span>{selected.size === 0
        ? 'Selecciona habilidades bloqueadas.'
        : `${amountFormat.format(selectedRefs.length)} de ${amountFormat.format(pendingKeys.length)} seleccionadas.`}</span>
      <div className="cloud-actions">
        <button type="button" className="button quiet" disabled={busy || pendingKeys.length === 0}
          onClick={() => addKeys(pendingKeys)}>Seleccionar bloqueadas</button>
        <button type="button" className="button quiet" disabled={busy || selected.size === 0}
          onClick={() => {
            onSelectedChange(new Set())
            clearPreview()
          }}>Limpiar selección</button>
      </div>
    </div>

    {selectedLockedCharacters.length > 0 && <Notice tone="warning">
      <span data-testid="skill-locked-character-warning">
        La selección incluye personajes bloqueados ({selectedLockedCharacters
          .map((view) => view.character.name).join(', ')}). Esta sección no modifica
        <code> heroUnlock</code>.
      </span>
    </Notice>}

    {visibleViews.length === 0 ? <p className="cloud-note" data-testid="skill-empty-filter">
      No hay personajes que coincidan con la búsqueda o el filtro.
    </p> : <div className="skill-character-list">
      {visibleViews.map((view) => {
        const { character, options } = view
        const pendingKeysForCharacter = options
          .filter((option) => option.state === 'pending')
          .map((option) => skillKey(character.code, option.index))
        const unlocked = character.unlocked === true
        return <details className="skill-character" key={character.code}
          data-testid={`skill-character-${character.code}`}>
          <summary>
            <span className="skill-character-title">
              <strong>{character.name}</strong>
              <small>{character.code} · {amountFormat.format(view.available)} / {amountFormat.format(options.length)} disponibles</small>
            </span>
            <span className={`report-state ${unlocked ? 'available' : 'locked'}`}>
              {unlocked ? 'Personaje disponible' : character.unlocked === '<missing>' ? 'Sin dato' : 'Personaje bloqueado'}
            </span>
          </summary>
          <div className="skill-character-body">
            {!unlocked && <p className="skill-requirement">
              Personaje bloqueado. Las habilidades se preparan, pero <code>heroUnlock</code> no se modifica.
            </p>}
            {options.length === 0 ? <p className="cloud-note">
              Sin datos de habilidades para este personaje.
            </p> : <ul className="skill-list">
              {options.map((option) => {
                const key = skillKey(character.code, option.index)
                const checked = selected.has(key)
                return <li key={option.index} className={`skill-row ${option.state}`}
                  data-testid={`skill-option-${character.code}-${option.index}`}>
                  {option.state === 'pending' ? <input type="checkbox" checked={checked}
                    aria-label={`Seleccionar ${option.name} de ${character.name}`} disabled={busy}
                    onChange={() => toggle(character.code, option.index)} />
                    : <span className="character-unlock-mark" aria-hidden="true">
                      {option.state === 'available' ? '✓' : '?'}
                    </span>}
                  <span className="skill-name">
                    <strong>{option.name}</strong>
                    <small>índice {option.index} · {option.state === 'available'
                      ? 'desbloqueada' : option.state === 'pending' ? 'bloqueada' : 'sin dato'}</small>
                  </span>
                  <span className={`report-state ${option.state === 'available' ? 'available' : 'locked'}`}>
                    {option.state === 'available' ? 'Disponible' : option.state === 'pending' ? 'Bloqueada' : 'Sin dato'}
                  </span>
                </li>
              })}
            </ul>}
            {view.unknown > 0 && <p className="cloud-note">
              {amountFormat.format(view.unknown)} posiciones sin dato; no se modifican.
            </p>}
            <div className="cloud-actions">
              <button type="button" className="button quiet"
                aria-label={`Seleccionar bloqueadas de ${character.name}`}
                disabled={busy || pendingKeysForCharacter.length === 0}
                onClick={() => addKeys(pendingKeysForCharacter)}>
                Seleccionar bloqueadas
              </button>
            </div>
          </div>
        </details>
      })}
    </div>}

    <div className="cloud-actions">
      <button type="button" className="button primary"
        disabled={busy || selectedRefs.length === 0}
        onClick={() => {
          setAction('prepare')
          run(async (signal) => {
            clearPreview()
            const next = await nativeAuth.prepareSkills(selectedRefs, saveSha, signal)
            setPrepared(next)
            onPrepared?.()
          })
        }}>Preparar desbloqueo</button>
    </div>

    {prepared && <div className="cloud-preview" data-testid="skill-unlock-preview">
      <h3>Revisar desbloqueo</h3>
      <dl className="cloud-preview-data">
        <div><dt>Habilidades nuevas</dt><dd>{amountFormat.format(prepared.new_unlocked_count)} / {amountFormat.format(prepared.total_skills)}</dd></div>
        <div><dt>Se desbloquean</dt><dd>{amountFormat.format(prepared.newly_unlocked_skills.length)}</dd></div>
      </dl>
      <p className="cloud-note" data-testid="skill-unlock-summary">
        {prepared.newly_unlocked_skills.map((skill) => (
          `${names.get(skill.code) ?? skill.code}: ${skillNames.get(skillKey(skill.code, skill.index)) ?? `índice ${skill.index}`}`
        )).join(' · ')}
      </p>
      <p className="cloud-note">
        Respaldo cifrado creado. Personajes: {affectedNames || 'ninguno'}. <code>heroSkill</code>,
        personajes, niveles, skins y recursos no cambian.
      </p>
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
              onApplied(prepared.newly_unlocked_skills.map((skill) => skillKey(skill.code, skill.index)))
              onPrepared?.()
            })
          }}>Desbloquear y verificar</button>
      </>}
    </div>}
    {result && <div role="status" className={`cloud-feedback ${result.persisted ? 'verified' : 'uncertain'}`}
      data-testid="skill-unlock-result">
      {result.persisted
        ? `Desbloqueo verificado en la nube. ${amountFormat.format(result.remote_skills ?? prepared?.new_unlocked_count ?? 0)} de ${amountFormat.format(total)} disponibles.`
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