import { ChevronDown, Search, WandSparkles } from 'lucide-react'
import { useState } from 'react'
import {
  ApiProblem, nativeAuth,
  type LabAdvanced, type LabAdvancedPlan, type LabAdvancedPrepared,
  type LabPetFoodRow, type LabPetRow, type LabPetSkinRow, type LabWriteResult,
} from '../api'
import { Loading, Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'

const numberFormat = new Intl.NumberFormat('es-MX')
const MAX_VALUE = 2_147_483_647
const FOOD_QUICK = [100, 1_000, 10_000, 100_000]

type Filter = 'all' | 'locked' | 'unlocked'

function petLabel(row: { id: string; name: { en?: string | null; es?: string | null } }) {
  return row.name.es?.trim() || row.name.en?.trim() || row.id
}

function parseQuantity(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) && parsed >= 0 && parsed <= MAX_VALUE ? parsed : null
}

function visibleUnderFilter(unlocked: boolean | null, filter: Filter) {
  if (filter === 'locked') return unlocked !== true
  if (filter === 'unlocked') return unlocked === true
  return true
}

function PetCatalog({
  pets, query, onQuery, filter, onFilter, selected, onSelected, disabled,
}: {
  pets: LabPetRow[]
  query: string
  onQuery: (value: string) => void
  filter: Filter
  onFilter: (value: Filter) => void
  selected: Set<string>
  onSelected: (next: Set<string>) => void
  disabled: boolean
}) {
  const needle = query.trim().toLowerCase()
  const filtered = pets.filter((pet) => {
    if (!visibleUnderFilter(pet.unlocked, filter)) return false
    if (!needle) return true
    return pet.id.toLowerCase().includes(needle)
      || (pet.name.es ?? '').toLowerCase().includes(needle)
      || (pet.name.en ?? '').toLowerCase().includes(needle)
      || String(pet.numeric_id) === needle
  })
  const selectable = filtered.filter((pet) => pet.editable)
  const allSelected = selectable.length > 0 && selectable.every((pet) => selected.has(pet.id))

  function toggle(id: string) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelected(next)
  }

  return <details className="advanced-panel" open>
    <summary>
      <span><strong>Catálogo de mascotas</strong><small>Desbloqueo en gameData.petUnlock</small></span>
      <span className="advanced-count">{numberFormat.format(pets.filter((pet) => pet.unlocked === true).length)} / {pets.length} desbloqueadas</span>
      <ChevronDown size={17} aria-hidden="true" />
    </summary>
    <div className="advanced-panel-body">
      <div className="advanced-toolbar">
        <label className="advanced-search"><Search size={15} aria-hidden="true" />
          <input value={query} disabled={disabled} placeholder="Buscar por nombre, código o ID"
            aria-label="Buscar mascotas" onChange={(event) => onQuery(event.target.value)} />
        </label>
        <label className="cloud-field advanced-filter"><span>Estado</span>
          <select value={filter} disabled={disabled} onChange={(event) => onFilter(event.target.value as Filter)}>
            <option value="all">Todas</option>
            <option value="locked">Bloqueadas</option>
            <option value="unlocked">Desbloqueadas</option>
          </select>
        </label>
      </div>
      <div className="advanced-bulk">
        <button type="button" className="button quiet" disabled={disabled || selectable.length === 0}
          onClick={() => {
            const next = new Set(selected)
            for (const pet of selectable) {
              if (allSelected) next.delete(pet.id)
              else next.add(pet.id)
            }
            onSelected(next)
          }}>{allSelected ? 'Quitar selección' : `Seleccionar ${numberFormat.format(selectable.length)} visibles`}</button>
        <button type="button" className="button quiet" disabled={disabled}
          onClick={() => onSelected(new Set(pets.filter((pet) => pet.editable && pet.unlocked !== true).map((pet) => pet.id)))}>
          Seleccionar todas las pendientes
        </button>
        <button type="button" className="button quiet" disabled={disabled || !pets.some((pet) => pet.editable && pet.unlocked !== true)}
          onClick={() => onSelected(new Set(pets.filter((pet) => pet.editable && pet.unlocked !== true).map((pet) => pet.id)))}>
          Desbloquear todas
        </button>
      </div>
      {filtered.length === 0 ? <p className="cloud-note">Ninguna mascota coincide con el filtro.</p>
        : <div className="advanced-list">
          {filtered.map((pet) => <div key={pet.id} className={`advanced-item${pet.editable ? '' : ' read-only'}`}>
            <label className="advanced-check">
              <input type="checkbox" checked={selected.has(pet.id)} disabled={disabled || !pet.editable}
                aria-label={`Seleccionar ${petLabel(pet)}`} onChange={() => toggle(pet.id)} />
            </label>
            <div className="advanced-item-name">
              <strong>{petLabel(pet)}</strong>
              <code>{pet.id}</code>
              <small>
                ID {pet.numeric_id}
                {!pet.present && ' · Ausente del guardado; se insertará como true'}
                {pet.reason && ` · ${pet.reason}`}
              </small>
            </div>
            <div className="advanced-item-current">
              <span>Estado</span>
              <strong>{pet.unlocked == null ? 'Tipo no válido' : pet.unlocked ? 'Desbloqueada' : 'Bloqueada'}</strong>
            </div>
            <span className={`advanced-pending${pet.unlocked === true ? ' done' : ''}`}>
              {pet.unlocked === true ? 'Activa' : selected.has(pet.id) ? 'Seleccionada' : 'Pendiente'}
            </span>
          </div>)}
        </div>}
    </div>
  </details>
}

function PetSkins({
  skins, pets, query, onQuery, filter, onFilter, selected, onSelected, disabled,
}: {
  skins: LabPetSkinRow[]
  pets: LabPetRow[]
  query: string
  onQuery: (value: string) => void
  filter: Filter
  onFilter: (value: Filter) => void
  selected: Set<string>
  onSelected: (next: Set<string>) => void
  disabled: boolean
}) {
  const petById = new Map(pets.map((pet) => [pet.id, pet]))
  const needle = query.trim().toLowerCase()
  const filtered = skins.filter((skin) => {
    if (!visibleUnderFilter(skin.unlocked, filter)) return false
    if (!needle) return true
    return skin.id.toLowerCase().includes(needle)
      || skin.base_pet.toLowerCase().includes(needle)
      || petLabel(skin).toLowerCase().includes(needle)
      || (skin.name.es ?? '').toLowerCase().includes(needle)
      || (skin.name.en ?? '').toLowerCase().includes(needle)
  })
  const grouped = new Map<string, LabPetSkinRow[]>()
  for (const skin of filtered) {
    grouped.set(skin.base_pet, [...(grouped.get(skin.base_pet) ?? []), skin])
  }

  function toggle(id: string) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelected(next)
  }

  return <details className="advanced-panel">
    <summary>
      <span><strong>Skins de mascota</strong><small>Variantes asociadas a gameData.petUnlock</small></span>
      <span className="advanced-count">{numberFormat.format(skins.filter((skin) => skin.unlocked === true).length)} / {skins.length} desbloqueadas</span>
      <ChevronDown size={17} aria-hidden="true" />
    </summary>
    <div className="advanced-panel-body">
      <div className="advanced-toolbar">
        <label className="advanced-search"><Search size={15} aria-hidden="true" />
          <input value={query} disabled={disabled} placeholder="Buscar skin o mascota base"
            aria-label="Buscar skins de mascota" onChange={(event) => onQuery(event.target.value)} />
        </label>
        <label className="cloud-field advanced-filter"><span>Estado</span>
          <select value={filter} disabled={disabled} onChange={(event) => onFilter(event.target.value as Filter)}>
            <option value="all">Todas</option>
            <option value="locked">Bloqueadas</option>
            <option value="unlocked">Desbloqueadas</option>
          </select>
        </label>
      </div>
      <div className="advanced-bulk">
        <button type="button" className="button quiet" disabled={disabled || filtered.length === 0}
          onClick={() => {
            const next = new Set(selected)
            for (const skin of filtered.filter((row) => row.editable)) next.add(skin.id)
            onSelected(next)
          }}>Seleccionar las {numberFormat.format(filtered.length)} visibles</button>
        <button type="button" className="button quiet" disabled={disabled || skins.length === 0}
          onClick={() => onSelected(new Set(skins.filter((skin) => skin.editable).map((skin) => skin.id)))}>
          Desbloquear todas las skins
        </button>
      </div>
      {filtered.length === 0 ? <p className="cloud-note">Ninguna skin coincide con el filtro.</p>
        : [...grouped.entries()].map(([base, rows]) => <div key={base} className="pet-skin-group">
          <div className="pet-skin-group-head">
            <span><strong>{petById.get(base) ? petLabel(petById.get(base)!) : base}</strong> <code>{base}</code></span>
            <button type="button" className="button quiet" disabled={disabled}
              onClick={() => onSelected(new Set([...selected, ...rows.filter((skin) => skin.editable).map((skin) => skin.id)]))}>
              Seleccionar todas las de {base}
            </button>
          </div>
          <div className="advanced-list">
            {rows.map((skin) => {
              const baseUnlocked = petById.get(base)?.unlocked === true || selected.has(base)
              return <div key={skin.id} className={`advanced-item${skin.editable ? '' : ' read-only'}`}>
                <label className="advanced-check">
                  <input type="checkbox" checked={selected.has(skin.id)} disabled={disabled || !skin.editable}
                    aria-label={`Seleccionar skin ${petLabel(skin)}`} onChange={() => toggle(skin.id)} />
                </label>
                <div className="advanced-item-name">
                  <strong>{petLabel(skin)}</strong>
                  <code>{skin.id}</code>
                  <small>
                    Skin {skin.skin_index} de {base}
                    {!skin.present && ' · Ausente del guardado; se insertará como true'}
                    {!baseUnlocked && ' · La mascota base también se desbloqueará'}
                  </small>
                </div>
                <div className="advanced-item-current">
                  <span>Estado</span>
                  <strong>{skin.unlocked == null ? 'Tipo no válido' : skin.unlocked ? 'Desbloqueada' : 'Bloqueada'}</strong>
                </div>
                <span className={`advanced-pending${skin.unlocked === true ? ' done' : ''}`}>
                  {skin.unlocked === true ? 'Activa' : selected.has(skin.id) ? 'Seleccionada' : 'Pendiente'}
                </span>
              </div>
            })}
          </div>
        </div>)}
      <p className="cloud-note">
        No se encontró un mapa de bloqueo de skins separado de <code>gameData.petUnlock</code>.
        Estas variantes se desbloquean en el mismo mapa y arrastran su mascota base. No se modifica
        la skin equipada ni <code>currentSkinDatas</code>.
      </p>
    </div>
  </details>
}

function FoodEditor({
  row, value, onChange, disabled,
}: {
  row: LabPetFoodRow
  value: string
  onChange: (value: string) => void
  disabled: boolean
}) {
  const parsed = value.trim() === '' ? null : parseQuantity(value)
  return <div className="pet-food-card">
    <div>
      <strong>{petLabel(row)}</strong>
      <code>{row.id}</code>
      <small>{row.field} · {row.owned ? 'presente' : 'se insertará'}</small>
    </div>
    <div className="advanced-item-current">
      <span>Actual</span>
      <strong>{row.owned ? (row.count == null ? 'Tipo no válido' : numberFormat.format(row.count)) : '—'}</strong>
    </div>
    <label className="advanced-item-input"><span>Nueva cantidad</span>
      <input inputMode="numeric" value={value} disabled={disabled || !row.editable}
        placeholder={row.count != null ? String(row.count) : 'Cantidad'}
        aria-label={`Cantidad de ${petLabel(row)}`}
        aria-invalid={value.trim() !== '' && parsed == null}
        onChange={(event) => onChange(event.target.value)} />
    </label>
    <div className="advanced-quick">
      {FOOD_QUICK.map((amount) => <button key={amount} type="button" className="button quiet" disabled={disabled}
        onClick={() => onChange(String(amount))}>{numberFormat.format(amount)}</button>)}
    </div>
    {row.reason && <p className="cloud-note">{row.reason}</p>}
  </div>
}

function changeLabel(value: unknown) {
  if (value == null) return '—'
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function PetsEditorSection({
  saveSha, advanced, writeReady, disabled, accountLabel, formatProblem, onExpired, onPrepared,
}: {
  saveSha: string
  advanced: LabAdvanced
  writeReady: boolean
  disabled: boolean
  accountLabel: string
  formatProblem: (error: ApiProblem, fallback: string) => ApiProblem
  onExpired: () => void
  onPrepared: () => void
}) {
  const [petQuery, setPetQuery] = useState('')
  const [petFilter, setPetFilter] = useState<Filter>('all')
  const [petSelected, setPetSelected] = useState<Set<string>>(new Set())
  const [skinQuery, setSkinQuery] = useState('')
  const [skinFilter, setSkinFilter] = useState<Filter>('all')
  const [skinSelected, setSkinSelected] = useState<Set<string>>(new Set())
  const [foodValues, setFoodValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(advanced.pet_food.map((row) => [row.id, row.count == null ? '' : String(row.count)])))
  const [candidate, setCandidate] = useState<LabAdvancedPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const operation = useOperation()

  const petById = new Map(advanced.pets.map((pet) => [pet.id, pet]))
  const skinRows = new Map(advanced.pet_skins.map((skin) => [skin.id, skin]))
  const unlockedPets = advanced.pets.filter((pet) => pet.unlocked === true).length
  const unlockedSkins = advanced.pet_skins.filter((skin) => skin.unlocked === true).length
  const pendingPets = advanced.pets.filter((pet) => pet.editable && pet.unlocked !== true)
  const effectiveSelected = new Set(petSelected)
  for (const skinId of skinSelected) {
    effectiveSelected.add(skinId)
    const skin = skinRows.get(skinId)
    if (skin) effectiveSelected.add(skin.base_pet)
  }
  const petPlan = [...effectiveSelected].filter((id) => {
    const pet = petById.get(id)
    const skin = skinRows.get(id)
    const editable = pet?.editable ?? skin?.editable ?? false
    const unlocked = pet ? pet.unlocked : skin?.unlocked
    return editable && unlocked !== true
  }).sort()
  const foodPlan = advanced.pet_food.flatMap((row) => {
    const raw = foodValues[row.id] ?? ''
    const parsed = parseQuantity(raw)
    return parsed != null && parsed !== row.count ? [{ id: row.id, value: parsed }] : []
  })
  const foodInvalid = advanced.pet_food.some((row) => {
    const raw = foodValues[row.id] ?? ''
    return raw.trim() !== '' && parseQuantity(raw) == null
  })
  const plannedCount = petPlan.length + foodPlan.length
  const canPrepare = plannedCount > 0 && !foodInvalid && !disabled

  function clearPreview() {
    setCandidate(null)
    setConfirm(false)
    setResult(null)
  }

  function toggleFood(id: string, value: string) {
    setFoodValues((current) => ({ ...current, [id]: value }))
    clearPreview()
  }

  function submit() {
    if (!canPrepare) return
    const plan: LabAdvancedPlan = { materials: [], seeds: [], pets: petPlan }
    if (foodPlan.length > 0) plan.pet_food = foodPlan
    void operation.run(async (signal) => {
      try {
        clearPreview()
        setCandidate(await nativeAuth.prepareAdvanced(plan, saveSha, signal))
        onPrepared()
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      }
    })
  }

  function upload() {
    if (!candidate) return
    void operation.run(async (signal) => {
      try {
        setConfirm(false)
        const uploaded = await nativeAuth.confirm(candidate.backup.id, candidate.candidate_sha256, signal)
        setResult(uploaded)
        onPrepared()
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      }
    })
  }

  return <section className="cloud-section panel advanced-section" aria-labelledby="pets-title">
    <div className="cloud-section-head">
      <div>
        <span className="cloud-kicker">Confirmado por el propietario · E3</span>
        <h2 id="pets-title">Mascotas</h2>
        <p className="cloud-state">Desbloqueos, alimento y progresión de solo lectura</p>
      </div>
      <div className="editor-current">
        <span>Cambios</span>
        <strong data-testid="pets-change-count">{numberFormat.format(plannedCount)}</strong>
      </div>
    </div>
    <p className="cloud-note">
      Edita únicamente <code>gameData.petUnlock</code> y el alimento dentro de
      <code>itemData.materials</code>. La progresión se muestra sin escribir. No toca gemas,
      fichas, recompensas reclamadas, recibos ni compras. Requiere prueba en Android físico.
    </p>
    {!writeReady && <Notice tone="warning">
      Puedes preparar el lote y su respaldo. La subida a la nube está deshabilitada.
    </Notice>}

    <div className="advanced-current-grid">
      <div><span>Mascotas desbloqueadas</span><strong>{unlockedPets} / {advanced.pets.length}</strong></div>
      <div><span>Skins desbloqueadas</span><strong>{unlockedSkins} / {advanced.pet_skins.length}</strong></div>
      <div><span>Pendientes</span><strong>{pendingPets.length}</strong></div>
      <div><span>Progreso completo</span><strong>{advanced.pet_progression.global_full_count ?? '—'}</strong></div>
    </div>

    <div className="advanced-stack">
      <details className="advanced-panel" open>
        <summary>
          <span><strong>Alimento para mascotas</strong><small>Comparte el escritor de itemData.materials</small></span>
          <span className="advanced-count">{advanced.pet_food.length} alimento(s)</span>
          <ChevronDown size={17} aria-hidden="true" />
        </summary>
        <div className="advanced-panel-body">
          {advanced.pet_food.length === 0 ? <p className="cloud-note">
            No hay alimentos compatibles en el catálogo empaquetado.
          </p> : <div className="pet-food-grid">
            {advanced.pet_food.map((row) => <FoodEditor key={row.id} row={row}
              value={foodValues[row.id] ?? ''} onChange={(value) => toggleFood(row.id, value)}
              disabled={disabled} />)}
          </div>}
          <p className="cloud-note">
            <strong>{advanced.pet_policy.food_note}</strong>
          </p>
        </div>
      </details>

      <PetCatalog pets={advanced.pets} query={petQuery} onQuery={(value) => {
        setPetQuery(value)
        clearPreview()
      }} filter={petFilter} onFilter={setPetFilter} selected={petSelected} onSelected={(next) => {
        setPetSelected(next)
        clearPreview()
      }} disabled={disabled} />

      <PetSkins skins={advanced.pet_skins} pets={advanced.pets} query={skinQuery}
        onQuery={(value) => {
          setSkinQuery(value)
          clearPreview()
        }} filter={skinFilter} onFilter={setSkinFilter}
        selected={skinSelected} onSelected={(next) => {
          setSkinSelected(next)
          clearPreview()
        }} disabled={disabled} />

      <details className="advanced-panel">
        <summary>
          <span><strong>Progresión de mascotas</strong><small>Intimidad observada · solo lectura</small></span>
          <span className="advanced-count">{advanced.pet_progression.available ? 'Disponible' : 'No disponible'}</span>
          <ChevronDown size={17} aria-hidden="true" />
        </summary>
        <div className="advanced-panel-body">
          {!advanced.pet_progression.available ? <p className="cloud-note">
            Este guardado no contiene <code>statisticData.event2Count</code>. No se crea la estructura.
          </p> : <>
            <div className="advanced-list">
              {advanced.pet_progression.entries.filter((entry) => entry.present).map((entry) => (
                <div key={entry.id} className="advanced-item read-only">
                  <div className="advanced-item-name">
                    <strong>{petLabel(entry)}</strong>
                    <code>{entry.id}</code>
                    <small>ID {entry.numeric_id} · {entry.path}</small>
                  </div>
                  <div className="advanced-item-current">
                    <span>Intimidad</span>
                    <strong>{entry.intimacy == null ? 'Tipo no válido' : numberFormat.format(entry.intimacy)}</strong>
                  </div>
                  <div className="advanced-item-current">
                    <span>Máximo</span>
                    <strong>{entry.full ? 'Completa' : 'Desconocido'}</strong>
                  </div>
                  <span className={`advanced-pending${entry.full ? ' done' : ''}`}>
                    {entry.full ? 'Completa' : entry.action_unlocked ? 'Acción desbloqueada' : 'En progreso'}
                  </span>
                </div>
              ))}
            </div>
            <p className="cloud-note">{advanced.pet_progression.note}</p>
            <p className="cloud-note">
              El máximo no se escribe ni se simula con 999, 9999 o Int32.MaxValue. Solo
              <code>pet_&lt;ID&gt;_full_intimacy = 1</code> confirma que una mascota alcanzó su máximo.
            </p>
          </>}
        </div>
      </details>
    </div>

    <div className="advanced-actions">
      <button type="button" className="button primary" disabled={!canPrepare} onClick={submit}>
        <WandSparkles size={17} aria-hidden="true" />
        Preparar lote de mascotas
      </button>
      {foodInvalid && <small className="cloud-note">
        Hay cantidades de alimento con formato inválido. Usa enteros entre 0 y 2.147.483.647.
      </small>}
    </div>
    {operation.pending && <Loading>
      {candidate ? 'Subiendo y verificando…' : 'Preparando mascotas y respaldo…'}
    </Loading>}
    {operation.problem && <Problem problem={formatProblem(operation.problem,
      candidate ? 'No se pudo confirmar la subida. Verifica el estado desde Partida.'
        : 'No se pudo preparar el lote de mascotas. Revisa los datos y vuelve a intentarlo.')} />}
    {candidate && <div className="cloud-preview advanced-preview">
      <h3>Revisar lote preparado</h3>
      <p className="cloud-note">
        {candidate.changes.length} campo(s) cambiarán. Respaldo <code>{candidate.backup.id}</code>.
      </p>
      <div className="advanced-diff">
        {candidate.changes.slice(0, 40).map((change) => <div key={change.path}>
          <code>{change.path}</code>
          <span>{changeLabel(change.before)} → <strong>{changeLabel(change.after)}</strong></span>
        </div>)}
      </div>
      {candidate.changes.some((change) => change.path.includes('.petUnlock.')) && <p className="cloud-note">
        Las variantes de skin seleccionadas incluyen su mascota base en este mismo lote.
      </p>}
      {!candidate.changed ? <p className="cloud-note">No hay diferencias que subir.</p>
        : writeReady && !result && <>
          <label className="cloud-check"><input type="checkbox" checked={confirm} disabled={disabled}
            onChange={(event) => setConfirm(event.target.checked)} />
            <span>Confirmo que quiero sobrescribir la partida en la nube de {accountLabel} con este lote.</span>
          </label>
          <button type="button" className="button primary" disabled={disabled || !confirm}
            onClick={upload}>Subir lote y verificar</button>
        </>}
    </div>}
    {result && <div role="status" className={`cloud-feedback ${result.persisted ? 'verified' : 'uncertain'}`}>
      {result.persisted
        ? 'Lote subido y verificado en la nube. Falta comprobar las mascotas en Android físico.'
        : 'No se pudo confirmar la subida del lote. Verifica el estado desde Partida.'}
    </div>}
  </section>
}

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'}
