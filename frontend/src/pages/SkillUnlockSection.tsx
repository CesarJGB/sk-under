import { useState } from 'react'
import {
  ApiProblem, nativeAuth,
  type LabSkillPrepared, type LabSkillRef, type LabWriteResult, type SaveCharacter,
  type SaveCharacterReport,
} from '../api'
import { Loading, Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'

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

function skillKey(code: string, index: number) {
  return `${code}:${index}`
}

export function SkillUnlockSection({
  characters, saveSha, writeReady, accountLabel, disabled, formatProblem, onExpired, onPrepared,
}: {
  characters: SaveCharacterReport
  saveSha: string
  writeReady: boolean
  accountLabel: string
  disabled: boolean
  formatProblem: (error: ApiProblem, fallback: string) => ApiProblem
  onExpired: () => void
  onPrepared?: () => void
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [prepared, setPrepared] = useState<LabSkillPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [action, setAction] = useState<'prepare' | 'upload' | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<SkillFilter>('pending')
  const operation = useOperation()

  const justUnlocked = new Set(
    result?.persisted
      ? (prepared?.newly_unlocked_skills ?? []).map((skill) => skillKey(skill.code, skill.index))
      : [],
  )
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
      const state: SkillState = justUnlocked.has(skillKey(character.code, option.index))
        ? 'available'
        : observed?.unlocked === true
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
    .filter((option) => selected.has(skillKey(view.character.code, option.index)))
    .map((option) => ({ code: view.character.code, index: option.index })))
  const total = summary.total
  const catalogUnavailable = characters.catalog.available === false
    || characters.catalog.characters === 0
    || total === 0
  const busy = disabled || operation.pending || catalogUnavailable
  const unlockedCount = result?.persisted ? result.remote_skills ?? summary.unlocked : summary.unlocked
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
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
    clearPreview()
  }

  function addKeys(keys: string[]) {
    setSelected((current) => new Set([...current, ...keys]))
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
        <span className="cloud-kicker">Experimental · E2</span>
        <h2 id="edit-skills-title">Habilidades</h2>
        <p className="cloud-state">
          gameData.heroSkillUnlock · {amountFormat.format(total)} habilidades del catálogo · {accountLabel}
        </p>
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
      <div><span>Equipadas</span><strong>{amountFormat.format(summary.selected)}</strong></div>
      <div><span>Personajes con datos</span><strong>{amountFormat.format(summary.characters_with_data)}</strong></div>
    </div>

    <Notice tone="warning">
      <span data-testid="skill-experimental-notice">
        El desbloqueo de habilidades es una función <strong>experimental E2</strong>. Solo activa
        posiciones existentes de <code>gameData.heroSkillUnlock</code>; no cambia
        <code> gameData.heroSkill</code>, personajes, niveles, skins ni el resto de la partida.
        Todavía no está validado en el cliente oficial ni en un dispositivo físico.
      </span>
    </Notice>
    {!writeReady && <Notice tone="warning">
      Puedes preparar el desbloqueo y su respaldo. La subida a la nube está deshabilitada.
    </Notice>}
    {catalogUnavailable && <Notice tone="warning">
      <span data-testid="skill-catalog-unavailable">
        No está disponible el catálogo local de habilidades. La preparación queda bloqueada
        hasta que el backend pueda leer el catálogo empaquetado.
      </span>
    </Notice>}
    {summary.characters_with_data < characters.items.length && !catalogUnavailable && <Notice tone="info">
      Algunos personajes no tienen datos de habilidades en esta copia. Sus posiciones no se
      crean ni se modifican.
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
          <option value="pending">Con habilidades pendientes</option>
          <option value="available">Con habilidades disponibles</option>
          <option value="locked">Personajes bloqueados</option>
          <option value="incomplete">Con datos incompletos</option>
          <option value="all">Todos</option>
        </select>
      </label>
    </div>

    <div className="character-unlock-toolbar">
      <span>{selected.size === 0
        ? 'Selecciona habilidades bloqueadas para preparar su desbloqueo.'
        : `${amountFormat.format(selected.size)} seleccionadas de ${amountFormat.format(pendingKeys.length)} bloqueadas.`}</span>
      <div className="cloud-actions">
        <button type="button" className="button quiet" disabled={busy || pendingKeys.length === 0}
          onClick={() => addKeys(pendingKeys)}>Seleccionar todas las bloqueadas</button>
        <button type="button" className="button quiet" disabled={busy || selected.size === 0}
          onClick={() => {
            setSelected(new Set())
            clearPreview()
          }}>Deseleccionar todas</button>
      </div>
    </div>

    {selectedLockedCharacters.length > 0 && <Notice tone="warning">
      <span data-testid="skill-locked-character-warning">
        La selección incluye habilidades de personajes que aún aparecen bloqueados
        ({selectedLockedCharacters.map((view) => view.character.name).join(', ')}).
        Esta sección no modifica <code>gameData.heroUnlock</code>; desbloquea esos personajes
        en la sección Personajes si quieres usarlos en el juego.
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
          data-testid={`skill-character-${character.code}`}
          open={view.pending > 0 && visibleViews.length <= 3 ? true : undefined}>
          <summary>
            <span className="skill-character-title">
              <strong>{character.name}</strong>
              <small>{character.code} · {amountFormat.format(view.available)} / {amountFormat.format(options.length)} disponibles</small>
            </span>
            <span className={`report-state ${unlocked ? 'available' : 'locked'}`}>
              {unlocked ? 'Personaje disponible' : character.unlocked === '<missing>' ? 'Personaje sin dato' : 'Personaje bloqueado'}
            </span>
          </summary>
          <div className="skill-character-body">
            {!unlocked && <p className="skill-requirement">
              <strong>Requisito pendiente:</strong> el personaje no está desbloqueado en esta copia.
              Las habilidades se pueden preparar, pero no se modificará <code>gameData.heroUnlock</code>.
            </p>}
            {options.length === 0 ? <p className="cloud-note">
              No hay datos de habilidades para este personaje en el catálogo.
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
              {amountFormat.format(view.unknown)} posiciones no tienen dato observado y no se modifican.
            </p>}
            <div className="cloud-actions">
              <button type="button" className="button quiet"
                disabled={busy || pendingKeysForCharacter.length === 0}
                onClick={() => addKeys(pendingKeysForCharacter)}>
                Seleccionar bloqueadas de {character.name}
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
        }}>Preparar desbloqueo de seleccionadas</button>
    </div>

    {prepared && <div className="cloud-preview" data-testid="skill-unlock-preview">
      <h3>Revisar desbloqueo de habilidades</h3>
      <dl className="cloud-preview-data">
        <div><dt>Habilidades originales</dt><dd>{amountFormat.format(prepared.original_unlocked_count)}</dd></div>
        <div><dt>Habilidades nuevas</dt><dd>{amountFormat.format(prepared.new_unlocked_count)} / {amountFormat.format(prepared.total_skills)}</dd></div>
        <div><dt>Habilidades que se desbloquean</dt><dd>{amountFormat.format(prepared.newly_unlocked_skills.length)}</dd></div>
        <div><dt>Personajes afectados</dt><dd>{amountFormat.format(prepared.affected_codes.length)}</dd></div>
      </dl>
      <p className="cloud-note">
        Personajes: {affectedNames || 'ninguno'}.
      </p>
      <p className="cloud-note" data-testid="skill-unlock-summary">
        {prepared.newly_unlocked_skills.map((skill) => (
          `${names.get(skill.code) ?? skill.code}: ${skillNames.get(skillKey(skill.code, skill.index)) ?? `índice ${skill.index}`}`
        )).join(' · ')}
      </p>
      <p className="cloud-note">
        Se guardó un respaldo cifrado de la partida original. La habilidad equipada
        (<code>gameData.heroSkill</code>), los personajes, los niveles, las skins y el resto
        de los campos permanecen intactos.
      </p>
      <details className="skill-changed-fields">
        <summary>Campos afectados ({amountFormat.format(prepared.changed_fields.length)})</summary>
        <code>{prepared.changed_fields.join(', ')}</code>
      </details>
      <Notice tone="warning">
        Evidencia experimental E2. La subida solo confirma que la nube conserva la copia
        modificada; falta comprobar el desbloqueo dentro del juego en Android.
      </Notice>
      {writeReady && !result && <>
        <label className="cloud-check"><input type="checkbox" checked={confirm} disabled={busy}
          onChange={(event) => setConfirm(event.target.checked)} />
          <span>Confirmo que quiero desbloquear estas habilidades y sobrescribir la partida
            en la nube de {accountLabel}.</span>
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
              setSelected(new Set())
              onPrepared?.()
            })
          }}>Desbloquear habilidades y verificar</button>
      </>}
    </div>}
    {result && <div role="status" className={`cloud-feedback ${result.persisted ? 'verified' : 'uncertain'}`}
      data-testid="skill-unlock-result">
      {result.persisted
        ? `Habilidades subidas y verificadas en la nube. Quedan ${amountFormat.format(result.remote_skills ?? prepared?.new_unlocked_count ?? 0)} de ${amountFormat.format(total)} desbloqueadas. Falta la comprobación manual dentro del juego.`
        : 'No se pudo confirmar la subida de habilidades. Verifica el estado desde Partida.'}
    </div>}
    {operation.pending && <Loading>
      {action === 'prepare' ? 'Preparando desbloqueo de habilidades y respaldo…' : 'Subiendo y verificando habilidades…'}
    </Loading>}
    {operation.problem && <Problem problem={formatProblem(operation.problem,
      action === 'upload'
        ? 'No se pudo confirmar la subida de habilidades. Verifica el estado desde Partida.'
        : 'No se pudo preparar el desbloqueo de habilidades. Vuelve a intentarlo.')} />}
  </section>
}