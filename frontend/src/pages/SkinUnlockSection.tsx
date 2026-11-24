import { useState } from 'react'
import {
  ApiProblem, nativeAuth,
  type LabSkinPrepared, type LabSkinRef, type LabWriteResult, type SaveCharacter,
  type SaveCharacterReport, type SaveSkinOption,
} from '../api'
import { Loading, Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'

const amountFormat = new Intl.NumberFormat('es-MX')
const previewLimit = 60

type SkinFilter = 'pending' | 'all' | 'unlocked' | 'locked_character' | 'incompatible'
type SkinState = 'unlocked' | 'pending' | 'unknown'

type SkinOptionView = Omit<SaveSkinOption, 'state'> & { state: SkinState }

type CharacterSkins = {
  character: SaveCharacter
  options: SkinOptionView[]
  unlocked: number
  pending: number
  unknown: number
  incompatible: number
  hasData: boolean
}

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
}

function skinKey(code: string, index: number) {
  return `${code}:${index}`
}

function skinLabel(option: { name: string; key: string }) {
  return option.name.trim() || option.key
}

export function SkinUnlockSection({
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
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [prepared, setPrepared] = useState<LabSkinPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [action, setAction] = useState<'prepare' | 'upload' | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<SkinFilter>('pending')
  const operation = useOperation()

  const justUnlocked = new Set(
    result?.persisted
      ? (prepared?.newly_unlocked_skins ?? []).map((skin) => skinKey(skin.code, skin.index))
      : [],
  )
  const summary = characters.skins ?? {
    total: 0,
    unlocked: 0,
    pending: 0,
    selected: 0,
    incompatible: 0,
    characters_with_data: 0,
    status: 'experimental' as const,
  }
  const characterViews: CharacterSkins[] = characters.items.map((character) => {
    const options: SkinOptionView[] = character.skin_options.map((option) => {
      const state: SkinState = justUnlocked.has(skinKey(character.code, option.index))
        ? 'unlocked'
        : option.state === 'unlocked'
          ? 'unlocked'
          : option.state === 'locked'
            ? 'pending'
            : 'unknown'
      return { ...option, state }
    })
    return {
      character,
      options,
      unlocked: options.filter((option) => option.state === 'unlocked').length,
      pending: options.filter((option) => option.state === 'pending').length,
      unknown: options.filter((option) => option.state === 'unknown').length,
      incompatible: options.filter((option) => !option.compatible).length,
      hasData: options.length > 0,
    }
  })
  const pendingKeys = characterViews.flatMap((view) => view.options
    .filter((option) => option.state === 'pending' && option.compatible)
    .map((option) => skinKey(view.character.code, option.index)))
  const selectedRefs: LabSkinRef[] = characterViews.flatMap((view) => view.options
    .filter((option) => selected.has(skinKey(view.character.code, option.index)))
    .map((option) => ({ code: view.character.code, index: option.index })))
  const total = summary.total
  const catalogUnavailable = characters.catalog.available === false
    || characters.catalog.characters === 0
    || total === 0
  const busy = disabled || operation.pending || catalogUnavailable
  const unlockedCount = characterViews.reduce((sum, view) => sum + view.unlocked, 0)
  const pendingCount = characterViews.reduce((sum, view) => sum + view.pending, 0)
  const incompatibleCount = characterViews.reduce((sum, view) => sum + view.incompatible, 0)
  const names = new Map(characters.items.map((character) => [character.code, character.name]))
  const skinNames = new Map(characterViews.flatMap((view) => view.options.map((option) => [
    skinKey(view.character.code, option.index), skinLabel(option),
  ] as const)))
  const affectedNames = (prepared?.affected_codes ?? [])
    .map((code) => names.get(code) ?? code)
  const selectedCharacterCodes = new Set(selectedRefs.map((skin) => skin.code))
  const selectedLockedCharacters = characterViews.filter((view) => (
    selectedCharacterCodes.has(view.character.code) && view.character.unlocked !== true
  ))
  const preparedNames = (prepared?.newly_unlocked_skins ?? []).map((skin) => (
    `${names.get(skin.code) ?? skin.code}: ${skinNames.get(skinKey(skin.code, skin.index))
      ?? `índice ${skin.index}`}`
  ))

  const normalizedQuery = query.trim().toLowerCase()
  const visibleViews = characterViews.map((view) => {
    const matchesCharacter = !normalizedQuery
      || view.character.name.toLowerCase().includes(normalizedQuery)
      || view.character.code.toLowerCase().includes(normalizedQuery)
    const matchingOptions = !normalizedQuery || matchesCharacter
      ? view.options
      : view.options.filter((option) => (
        skinLabel(option).toLowerCase().includes(normalizedQuery)
        || option.key.toLowerCase().includes(normalizedQuery)
        || String(option.index) === normalizedQuery
      ))
    return { view, matchingOptions, matches: matchesCharacter || matchingOptions.length > 0 }
  }).filter(({ view, matches }) => {
    if (!matches) return false
    if (filter === 'pending') return view.pending > 0
    if (filter === 'unlocked') return view.unlocked > 0
    if (filter === 'locked_character') return view.character.unlocked !== true
    if (filter === 'incompatible') return view.incompatible > 0
    return true
  })

  function clearPreview() {
    setPrepared(null)
    setConfirm(false)
    setResult(null)
  }

  function toggle(code: string, index: number) {
    const key = skinKey(code, index)
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

  function toggleCard(code: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
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

  return <section className="cloud-section panel cloud-editor skin-unlock-editor"
    aria-labelledby="edit-skins-title" data-testid="skin-unlock-section">
    <div className="cloud-section-head">
      <div>
        <span className="cloud-kicker">Experimental · E2</span>
        <h2 id="edit-skins-title">Skins</h2>
        <p className="cloud-state">
          gameData.skinLock · {amountFormat.format(total)} skins del catálogo · {accountLabel}
        </p>
      </div>
      <div className="editor-current">
        <span>Desbloqueadas</span>
        <strong data-testid="skin-unlocked-count">
          {amountFormat.format(unlockedCount)} / {amountFormat.format(total)}
        </strong>
      </div>
    </div>

    <div className="skin-summary" aria-label="Resumen de skins">
      <div><span>Identificadas</span><strong>{amountFormat.format(total)}</strong></div>
      <div><span>Desbloqueadas</span><strong>{amountFormat.format(unlockedCount)}</strong></div>
      <div><span>Pendientes</span><strong>{amountFormat.format(pendingCount)}</strong></div>
      <div><span>Selección registrada</span><strong>{amountFormat.format(summary.selected)}</strong></div>
      {incompatibleCount > 0 && <div>
        <span>Incompatibles</span>
        <strong data-testid="skin-incompatible-count">{amountFormat.format(incompatibleCount)}</strong>
      </div>}
      <div><span>Personajes con datos</span><strong>{amountFormat.format(summary.characters_with_data)}</strong></div>
    </div>

    <Notice tone="warning">
      <span data-testid="skin-experimental-notice">
        El desbloqueo de skins es una función <strong>experimental E2</strong>. Solo cambia a
        <code> 1 </code> posiciones existentes de <code>gameData.skinLock</code>; no crea
        entradas, no modifica <code>gameData.currentSkinDatas</code>, personajes, habilidades,
        niveles ni el resto de la partida. Todavía no está validado en el cliente oficial ni
        en un dispositivo físico.
      </span>
    </Notice>
    <Notice tone="info">
      El valor <code>1</code> se interpreta como skin desbloqueada a partir de las 42 skins
      iniciales y de la única skin adicional observada con ese valor. Es una hipótesis E2:
      las skins con condiciones especiales de evento, compra o logro no se pueden garantizar
      hasta la comprobación manual.
    </Notice>
    {!writeReady && <Notice tone="warning">
      Puedes preparar el desbloqueo y su respaldo. La subida a la nube está deshabilitada.
    </Notice>}
    {catalogUnavailable && <Notice tone="warning">
      <span data-testid="skin-catalog-unavailable">
        No está disponible el catálogo local de skins. La preparación queda bloqueada hasta
        que el backend pueda leer el catálogo empaquetado.
      </span>
    </Notice>}
    {summary.characters_with_data < characters.items.length && !catalogUnavailable && <Notice tone="info">
      Algunos personajes no tienen datos de skins en esta copia. Sus posiciones no se crean
      ni se modifican.
    </Notice>}

    <div className="skin-filters">
      <label className="cloud-field">
        <span>Buscar skin o personaje</span>
        <input type="search" value={query} disabled={busy}
          placeholder="Nombre, código o clave" onChange={(event) => setQuery(event.target.value)} />
      </label>
      <label className="cloud-field">
        <span>Mostrar skins</span>
        <select value={filter} disabled={busy}
          onChange={(event) => setFilter(event.target.value as SkinFilter)}>
          <option value="pending">Con skins pendientes</option>
          <option value="unlocked">Con skins desbloqueadas</option>
          <option value="locked_character">Personajes bloqueados</option>
          <option value="incompatible">Con posiciones incompatibles</option>
          <option value="all">Todos</option>
        </select>
      </label>
    </div>

    <div className="character-unlock-toolbar">
      <span>{selected.size === 0
        ? 'Selecciona skins pendientes para preparar su desbloqueo.'
        : `${amountFormat.format(selected.size)} seleccionadas de ${amountFormat.format(pendingKeys.length)} pendientes compatibles.`}</span>
      <div className="cloud-actions">
        <button type="button" className="button quiet" disabled={busy || pendingKeys.length === 0}
          onClick={() => addKeys(pendingKeys)}>Seleccionar todas las pendientes</button>
        <button type="button" className="button quiet" disabled={busy || selected.size === 0}
          onClick={() => {
            setSelected(new Set())
            clearPreview()
          }}>Deseleccionar skins</button>
      </div>
    </div>

    {selectedLockedCharacters.length > 0 && <Notice tone="warning">
      <span data-testid="skin-locked-character-warning">
        La selección incluye skins de personajes que aún aparecen bloqueados
        ({selectedLockedCharacters.map((view) => view.character.name).join(', ')}).
        Esta sección no modifica <code>gameData.heroUnlock</code>; desbloquea esos personajes
        en la sección Personajes si quieres usarlos en el juego.
      </span>
    </Notice>}

    {visibleViews.length === 0 ? <p className="cloud-note" data-testid="skin-empty-filter">
      No hay personajes o skins que coincidan con la búsqueda o el filtro.
    </p> : <div className="skin-character-list">
      {visibleViews.map(({ view, matchingOptions }) => {
        const { character, options } = view
        const pendingKeysForCharacter = options
          .filter((option) => option.state === 'pending' && option.compatible)
          .map((option) => skinKey(character.code, option.index))
        const isOpen = expanded.has(character.code)
        const unlocked = character.unlocked === true
        const matchingCount = query.trim() ? matchingOptions.length : options.length
        return <details className="skin-character" key={character.code}
          data-testid={`skin-character-${character.code}`}
          open={isOpen}
          onToggle={(event) => {
            const open = event.currentTarget.open
            if (open !== isOpen) toggleCard(character.code)
          }}>
          <summary>
            <span className="skin-character-title">
              <strong>{character.name}</strong>
              <small>
                {character.code} · {amountFormat.format(view.unlocked)} / {amountFormat.format(options.length)} desbloqueadas
                {query.trim() && matchingCount !== options.length
                  ? ` · ${amountFormat.format(matchingCount)} coincidencias`
                  : ''}
              </small>
            </span>
            <span className={`report-state ${unlocked ? 'available' : 'locked'}`}>
              {unlocked ? 'Personaje disponible' : character.unlocked === '<missing>' ? 'Personaje sin dato' : 'Personaje bloqueado'}
            </span>
          </summary>
          {isOpen && <div className="skin-character-body">
            {!unlocked && <p className="skin-requirement">
              <strong>Requisito pendiente:</strong> el personaje no está desbloqueado en esta copia.
              Las skins se pueden preparar, pero no se modificará <code>gameData.heroUnlock</code>.
            </p>}
            {matchingOptions.length === 0 ? <p className="cloud-note">
              No hay skins que coincidan con la búsqueda en este personaje.
            </p> : <ul className="skin-list">
              {matchingOptions.map((option) => {
                const key = skinKey(character.code, option.index)
                const checked = selected.has(key)
                const selectable = option.state === 'pending' && option.compatible && !busy
                const isRecorded = character.selected_skin === option.index
                return <li key={option.index} className={`skin-row ${option.state}`}
                  data-testid={`skin-option-${character.code}-${option.index}`}>
                  <span className="skin-thumb" aria-hidden="true">◇</span>
                  {option.state === 'pending' && option.compatible
                    ? <input type="checkbox" checked={checked}
                      aria-label={`Seleccionar ${skinLabel(option)} de ${character.name}`}
                      disabled={!selectable}
                      onChange={() => toggle(character.code, option.index)} />
                    : <span className="character-unlock-mark" aria-hidden="true">
                      {option.state === 'unlocked' ? '✓' : '?'}
                    </span>}
                  <span className="skin-name">
                    <strong>{skinLabel(option)}</strong>
                    <small>
                      {character.name} · índice {option.index} · {option.key}
                      {option.value !== null ? ` · valor ${amountFormat.format(option.value)}` : ''}
                      {isRecorded ? ' · selección registrada' : ''}
                    </small>
                    {!option.name.trim() && <small>El catálogo no trae un nombre para esta skin; se muestra su clave.</small>}
                  </span>
                  <span className="skin-state">
                    <span className={`report-state ${option.state === 'unlocked' ? 'available' : 'locked'}`}>
                      {option.state === 'unlocked' ? 'Desbloqueada'
                        : option.state === 'pending' ? 'Pendiente' : 'Sin dato'}
                    </span>
                    <small className={option.compatible ? 'skin-compatible' : 'skin-incompatible'}>
                      {option.compatible ? 'Compatible' : 'No compatible'}
                    </small>
                  </span>
                </li>
              })}
            </ul>}
            {view.unknown > 0 && <p className="cloud-note">
              {amountFormat.format(view.unknown)} posiciones no tienen un valor entero reconocible
              y no se pueden seleccionar ni modificar.
            </p>}
            <div className="cloud-actions">
              <button type="button" className="button quiet"
                disabled={busy || pendingKeysForCharacter.length === 0}
                onClick={() => addKeys(pendingKeysForCharacter)}>
                Seleccionar pendientes de {character.name}
              </button>
            </div>
          </div>}
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
            const next = await nativeAuth.prepareSkins(selectedRefs, saveSha, signal)
            setPrepared(next)
            onPrepared?.()
          })
        }}>Preparar desbloqueo de skins seleccionadas</button>
    </div>

    {prepared && <div className="cloud-preview" data-testid="skin-unlock-preview">
      <h3>Revisar desbloqueo de skins</h3>
      <dl className="cloud-preview-data">
        <div><dt>Skins originales</dt><dd>{amountFormat.format(prepared.original_unlocked_count)}</dd></div>
        <div><dt>Skins nuevas</dt><dd>{amountFormat.format(prepared.new_unlocked_count)} / {amountFormat.format(prepared.total_skins)}</dd></div>
        <div><dt>Skins que se desbloquean</dt><dd>{amountFormat.format(prepared.newly_unlocked_skins.length)}</dd></div>
        <div><dt>Personajes afectados</dt><dd>{amountFormat.format(prepared.affected_codes.length)}</dd></div>
      </dl>
      <p className="cloud-note">
        Personajes: {affectedNames.slice(0, 20).join(', ') || 'ninguno'}
        {affectedNames.length > 20 ? ` y ${amountFormat.format(affectedNames.length - 20)} más` : ''}.
      </p>
      <p className="cloud-note" data-testid="skin-unlock-summary">
        {preparedNames.slice(0, previewLimit).join(' · ')}
        {preparedNames.length > previewLimit
          ? ` · … y ${amountFormat.format(preparedNames.length - previewLimit)} más`
          : ''}
      </p>
      {prepared.locked_character_codes.length > 0 && <Notice tone="warning">
        <span data-testid="skin-locked-character-preview">
          La selección incluye personajes bloqueados ({prepared.locked_character_codes
            .map((code) => names.get(code) ?? code).join(', ')}). Sus skins se desbloquean en
          <code> skinLock</code>, pero <code>heroUnlock</code> no se modifica.
        </span>
      </Notice>}
      <p className="cloud-note">
        Se guardó un respaldo cifrado de la partida original. La selección registrada
        (<code>gameData.currentSkinDatas</code>), los personajes, las habilidades, los niveles y
        el resto de los campos permanecen intactos.
      </p>
      <details className="skin-changed-fields">
        <summary>Campos afectados ({amountFormat.format(prepared.changed_fields.length)})</summary>
        <code>{prepared.changed_fields.slice(0, 30).join(', ')}
          {prepared.changed_fields.length > 30
            ? `, … y ${amountFormat.format(prepared.changed_fields.length - 30)} más`
            : ''}</code>
      </details>
      <Notice tone="warning">
        Evidencia experimental E2. La subida solo confirma que la nube conserva la copia
        modificada; falta comprobar el desbloqueo dentro del juego en Android físico.
      </Notice>
      {writeReady && !result && <>
        <label className="cloud-check"><input type="checkbox" checked={confirm} disabled={busy}
          onChange={(event) => setConfirm(event.target.checked)} />
          <span>Confirmo que quiero desbloquear estas skins y sobrescribir la partida
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
          }}>Desbloquear skins y verificar</button>
      </>}
    </div>}
    {result && <div role="status" className={`cloud-feedback ${result.persisted ? 'verified' : 'uncertain'}`}
      data-testid="skin-unlock-result">
      {result.persisted
        ? `Skins subidas y verificadas en la nube. Quedan ${amountFormat.format(result.remote_skins ?? prepared?.new_unlocked_count ?? 0)} de ${amountFormat.format(total)} desbloqueadas. Falta la comprobación manual dentro del juego.`
        : 'No se pudo confirmar la subida de skins. Verifica el estado desde Partida.'}
    </div>}
    {operation.pending && <Loading>
      {action === 'prepare' ? 'Preparando desbloqueo de skins y respaldo…' : 'Subiendo y verificando skins…'}
    </Loading>}
    {operation.problem && <Problem problem={formatProblem(operation.problem,
      action === 'upload'
        ? 'No se pudo confirmar la subida de skins. Verifica el estado desde Partida.'
        : 'No se pudo preparar el desbloqueo de skins. Vuelve a intentarlo.')} />}
  </section>
}