import { useState } from 'react'
import {
  ApiProblem, nativeAuth,
  type LabSkinPrepared, type LabSkinRef, type LabWriteResult, type SaveCharacter,
  type SaveCharacterReport, type SaveSkinOption,
} from '../api'
import { Loading, Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'
import { skinKey } from '../unlockSelections'

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

function skinLabel(option: { name: string; key: string }) {
  return option.name.trim() || option.key
}

export function SkinUnlockSection({
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
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [prepared, setPrepared] = useState<LabSkinPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [action, setAction] = useState<'prepare' | 'upload' | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<SkinFilter>('pending')
  const operation = useOperation()

  const summary = characters.skins ?? {
    total: 0,
    unlocked: 0,
    pending: 0,
    selected: 0,
    incompatible: 0,
    characters_with_data: 0,
    status: 'confirmed_by_owner' as const,
  }
  const characterViews: CharacterSkins[] = characters.items.map((character) => {
    const options: SkinOptionView[] = character.skin_options.map((option) => {
      const key = skinKey(character.code, option.index)
      const state: SkinState = option.state === 'unlocked' || applied.has(key)
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
    .filter((option) => option.state === 'pending' && option.compatible
      && selected.has(skinKey(view.character.code, option.index)))
    .map((option) => ({ code: view.character.code, index: option.index })))
  const total = summary.total
  const catalogUnavailable = characters.catalog.available === false
    || characters.catalog.characters === 0
    || total === 0
  const busy = disabled || operation.pending || catalogUnavailable
  const unlockedCount = result?.persisted
    ? result.remote_skins ?? summary.unlocked
    : Math.min(total, summary.unlocked + applied.size)
  const pendingCount = pendingKeys.length
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
        <span className="cloud-kicker">Confirmado por el propietario · E3</span>
        <h2 id="edit-skins-title">Skins</h2>
        <p className="cloud-state">{amountFormat.format(total)} en el catálogo · {accountLabel}</p>
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
      {incompatibleCount > 0 && <div>
        <span>Incompatibles</span>
        <strong data-testid="skin-incompatible-count">{amountFormat.format(incompatibleCount)}</strong>
      </div>}
    </div>

    {!writeReady && <Notice tone="warning">
      Puedes preparar el cambio y su respaldo. La subida está deshabilitada.
    </Notice>}
    {catalogUnavailable && <Notice tone="warning">
      <span data-testid="skin-catalog-unavailable">
        Catálogo de skins no disponible. La preparación está bloqueada.
      </span>
    </Notice>}
    {summary.characters_with_data < characters.items.length && !catalogUnavailable && <Notice tone="info">
      Algunos personajes no tienen datos de skins; sus posiciones no se crean ni se modifican.
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
          <option value="pending">Con pendientes</option>
          <option value="unlocked">Con desbloqueadas</option>
          <option value="locked_character">Personajes bloqueados</option>
          <option value="incompatible">Con incompatibles</option>
          <option value="all">Todas</option>
        </select>
      </label>
    </div>

    <div className="character-unlock-toolbar">
      <span>{selected.size === 0
        ? 'Selecciona skins pendientes.'
        : `${amountFormat.format(selectedRefs.length)} de ${amountFormat.format(pendingKeys.length)} seleccionadas.`}</span>
      <div className="cloud-actions">
        <button type="button" className="button quiet" disabled={busy || pendingKeys.length === 0}
          onClick={() => addKeys(pendingKeys)}>Seleccionar pendientes</button>
        <button type="button" className="button quiet" disabled={busy || selected.size === 0}
          onClick={() => {
            onSelectedChange(new Set())
            clearPreview()
          }}>Limpiar selección</button>
      </div>
    </div>

    {selectedLockedCharacters.length > 0 && <Notice tone="warning">
      <span data-testid="skin-locked-character-warning">
        La selección incluye personajes bloqueados ({selectedLockedCharacters
          .map((view) => view.character.name).join(', ')}). Esta sección no modifica
        <code> heroUnlock</code>.
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
              {unlocked ? 'Personaje disponible' : character.unlocked === '<missing>' ? 'Sin dato' : 'Personaje bloqueado'}
            </span>
          </summary>
          {isOpen && <div className="skin-character-body">
            {!unlocked && <p className="skin-requirement">
              Personaje bloqueado. Las skins se preparan, pero <code>heroUnlock</code> no se modifica.
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
                      {character.name} · índice {option.index}
                      {isRecorded ? ' · selección registrada' : ''}
                    </small>
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
              {amountFormat.format(view.unknown)} posiciones sin valor reconocible; no se pueden modificar.
            </p>}
            <div className="cloud-actions">
              <button type="button" className="button quiet"
                aria-label={`Seleccionar pendientes de ${character.name}`}
                disabled={busy || pendingKeysForCharacter.length === 0}
                onClick={() => addKeys(pendingKeysForCharacter)}>
                Seleccionar pendientes
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
        }}>Preparar desbloqueo</button>
    </div>

    {prepared && <div className="cloud-preview" data-testid="skin-unlock-preview">
      <h3>Revisar desbloqueo</h3>
      <dl className="cloud-preview-data">
        <div><dt>Skins nuevas</dt><dd>{amountFormat.format(prepared.new_unlocked_count)} / {amountFormat.format(prepared.total_skins)}</dd></div>
        <div><dt>Se desbloquean</dt><dd>{amountFormat.format(prepared.newly_unlocked_skins.length)}</dd></div>
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
          Incluye personajes bloqueados ({prepared.locked_character_codes
            .map((code) => names.get(code) ?? code).join(', ')}). <code>heroUnlock</code> no se modifica.
        </span>
      </Notice>}
      <p className="cloud-note">
        Respaldo cifrado creado. <code>currentSkinDatas</code>, personajes, habilidades,
        niveles y recursos no cambian.
      </p>
      <details className="skin-changed-fields">
        <summary>Campos afectados ({amountFormat.format(prepared.changed_fields.length)})</summary>
        <code>{prepared.changed_fields.slice(0, 30).join(', ')}
          {prepared.changed_fields.length > 30
            ? `, … y ${amountFormat.format(prepared.changed_fields.length - 30)} más`
            : ''}</code>
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
              onApplied(prepared.newly_unlocked_skins.map((skin) => skinKey(skin.code, skin.index)))
              onPrepared?.()
            })
          }}>Desbloquear y verificar</button>
      </>}
    </div>}
    {result && <div role="status" className={`cloud-feedback ${result.persisted ? 'verified' : 'uncertain'}`}
      data-testid="skin-unlock-result">
      {result.persisted
        ? `Desbloqueo verificado en la nube. ${amountFormat.format(result.remote_skins ?? prepared?.new_unlocked_count ?? 0)} de ${amountFormat.format(total)} desbloqueadas.`
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