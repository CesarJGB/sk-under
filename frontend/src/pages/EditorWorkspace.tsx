import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import {
  ApiProblem, nativeAuth,
  type LabAdvanced, type LabUnifiedPrepared, type LabWriteResult, type NativeSaveSummary,
} from '../api'
import {
  buildDraftPlan, bulkSummary, clearSelection, createEmptyDraft,
  eligibility, isSelected, parseQuantity, quickChecked, selectAll, setBulk, setEdit, setQuick,
  toggleItem, type BulkKey, type Draft, type QuantityKey,
} from '../draft'
import { skillKey, skinKey } from '../unlockSelections'
import { Loading, Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'

const amountFormat = new Intl.NumberFormat('es-MX')
const MAX = 2_147_483_647

type SaveBundle = NativeSaveSummary & { downloaded_at?: string }
type CategoryId =
  | 'recursos' | 'personajes' | 'habilidades' | 'skins' | 'mascotas'
  | 'materiales' | 'semillas' | 'temporada' | 'pase'

const categories: Array<{ id: CategoryId; label: string }> = [
  { id: 'recursos', label: 'Monedas y recursos' },
  { id: 'personajes', label: 'Personajes' },
  { id: 'habilidades', label: 'Habilidades' },
  { id: 'skins', label: 'Skins' },
  { id: 'mascotas', label: 'Mascotas' },
  { id: 'materiales', label: 'Materiales' },
  { id: 'semillas', label: 'Semillas' },
  { id: 'temporada', label: 'Temporada' },
  { id: 'pase', label: 'Pase de batalla' },
]

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
}

function QuickRow({
  label, checked, value, enabled = true, invalid = false, hint, onChange, onValue,
}: {
  label: string
  checked: boolean
  value?: string
  enabled?: boolean
  invalid?: boolean
  hint?: string
  onChange: (checked: boolean) => void
  onValue?: (value: string) => void
}) {
  return <label className={`quick-row ${checked ? 'active' : ''}`}>
    <input type="checkbox" checked={checked} disabled={!enabled} aria-label={`Activar ${label}`}
      onChange={(event) => onChange(event.target.checked)} />
    <span className="quick-label">{label}{hint && <small>{hint}</small>}</span>
    {onValue && <input className={`quick-value ${invalid ? 'invalid' : ''}`} inputMode="numeric" aria-label={label}
      value={value ?? ''} placeholder="0" disabled={!enabled || !checked} aria-invalid={invalid}
      onChange={(event) => onValue(event.target.value.replace(/[^\d]/g, ''))} />}
  </label>
}

function QuickEdit({ save, draft, update }: {
  save: SaveBundle
  draft: Draft
  update: (next: Draft) => void
}) {
  const eligible = eligibility(save)
  const characters = save.report?.characters
  const quickNumber = (key: QuantityKey) => parseQuantity(draft.quick[key].value)
  const valid = (key: QuantityKey) => {
    if (!draft.quick[key].enabled) return true
    const value = quickNumber(key)
    return value !== null && value <= MAX
  }
  const bulkRow = (key: BulkKey, label: string, total: number) => {
    const state = quickChecked(key, draft, eligible)
    return <QuickRow key={key} label={label} checked={state !== 'none'}
      hint={`${amountFormat.format(bulkSummary(key, draft, eligible).selected)} / ${amountFormat.format(total)}`}
      onChange={(checked) => update(setBulk(key, checked, draft))} />
  }
  const quantityRow = (key: QuantityKey, label: string, hint?: string) =>
    <QuickRow key={key} label={label} checked={draft.quick[key].enabled}
      value={draft.quick[key].value} invalid={!valid(key)} hint={hint}
      onChange={(checked) => update(setQuick(key, { enabled: checked }, draft))}
      onValue={(value) => update(setQuick(key, { value }, draft))} />

  const allBulk = () => update({
    ...draft,
    bulk: { characters: true, skills: true, skins: true, pets: true, petSkins: true },
    excluded: { characters: {}, skills: {}, skins: {}, pets: {}, petSkins: {} },
  })
  const none = () => update(createEmptyDraft())
  const battlePass = save.advanced?.battle_pass.records?.find(
    (record) => record.season_id === save.advanced?.battle_pass.selected_season_id,
  ) ?? save.advanced?.battle_pass.records?.[0]
  const rebornAvailable = save.advanced?.reborn_card.available && save.advanced.reborn_card.value === false

  return <div className="quick-edit" data-testid="quick-edit">
    <div className="quick-toolbar">
      <span>{amountFormat.format(Object.values(eligible).reduce((sum, items) => sum + items.length, 0))} elementos editables</span>
      <div>
        <button type="button" className="button quiet" onClick={allBulk}>Seleccionar desbloqueos</button>
        <button type="button" className="button quiet" onClick={none}>Limpiar</button>
      </div>
    </div>
    <section className="quick-group" aria-label="Recursos">
      <h3>Recursos</h3>
      {quantityRow('gems', 'Gemas')}
      {quantityRow('fishChip', 'Fichas de pesca')}
      {quantityRow('fishProgress', 'Recompensas de pesca', 'progreso acumulado')}
      {quantityRow('seasonCoin', 'Monedas de temporada')}
    </section>
    <section className="quick-group" aria-label="Cantidades mínimas">
      <h3>Cantidades <small>mínimo, nunca reduce</small></h3>
      {quantityRow('materialsMin', 'Materiales')}
      {quantityRow('seedsMin', 'Semillas')}
      {quantityRow('petFoodMin', 'Alimento de mascotas')}
      {quantityRow('batteryMin', 'Baterías')}
    </section>
    <section className="quick-group" aria-label="Desbloqueos">
      <h3>Desbloqueos</h3>
      {bulkRow('characters', 'Todos los personajes', characters?.counts.characters ?? 0)}
      {bulkRow('skills', 'Todas las habilidades', characters?.skills?.total ?? 0)}
      {bulkRow('skins', 'Todas las skins', characters?.skins?.total ?? 0)}
      {bulkRow('pets', 'Todas las mascotas', save.advanced?.pets.length ?? 0)}
      {bulkRow('petSkins', 'Skins de mascotas', save.advanced?.pet_skins.length ?? 0)}
    </section>
    <section className="quick-group" aria-label="Beneficios">
      <h3>Beneficios</h3>
      <QuickRow label="Tarjeta de renacimiento permanente"
        checked={draft.reborn} enabled={Boolean(rebornAvailable)}
        hint={rebornAvailable ? undefined : 'ya activa o no disponible'}
        onChange={(checked) => update({ ...draft, reborn: checked })} />
      {battlePass && <QuickRow label="Pase de batalla al nivel máximo"
        checked={draft.battlePass.enabled} enabled={battlePass.editable}
        hint={`${battlePass.cur_level} → ${battlePass.max_level}`}
        onChange={(checked) => update({
          ...draft,
          battlePass: {
            ...draft.battlePass,
            enabled: checked,
            seasonId: battlePass.season_id,
            level: checked ? String(battlePass.max_level ?? battlePass.cur_level ?? '') : draft.battlePass.level,
            exp: checked ? String(battlePass.cur_exp) : draft.battlePass.exp,
          },
        })} />}
    </section>
    {!save.report && <Notice tone="warning">Informe no disponible; vuelve a descargar la partida para editar desbloqueos.</Notice>}
  </div>
}

function CheckAll({ checked, indeterminate, onChange, label }: {
  checked: boolean
  indeterminate?: boolean
  onChange: (checked: boolean) => void
  label: string
}) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { if (ref.current) ref.current.indeterminate = Boolean(indeterminate) }, [indeterminate])
  return <label className="inline-check">
    <input ref={ref} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    <span>{label}</span>
  </label>
}

function SelectionToolbar({ selected, total, onAll, onClear }: {
  selected: number
  total: number
  onAll: () => void
  onClear: () => void
}) {
  return <div className="detail-toolbar">
    <span>{amountFormat.format(selected)} de {amountFormat.format(total)} seleccionados</span>
    <div>
      <button type="button" className="button quiet" disabled={total === 0} onClick={onAll}>Seleccionar todo</button>
      <button type="button" className="button quiet" disabled={selected === 0} onClick={onClear}>Limpiar</button>
    </div>
  </div>
}

function LockList({ save, draft, update, mode }: {
  save: SaveBundle
  draft: Draft
  update: (next: Draft) => void
  mode: 'characters' | 'skills' | 'skins'
}) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<'pending' | 'all' | 'done'>('pending')
  const characters = save.report?.characters
  const eligible = eligibility(save)
  const key = mode
  const selected = new Set(eligible[key].filter((item) => isSelected(key, item, draft, eligible)))
  return <div className="detail-editor">
    <div className="detail-filters">
      <input type="search" value={query} placeholder="Buscar" onChange={(event) => setQuery(event.target.value)} />
      <select value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}>
        <option value="pending">Pendientes</option>
        <option value="all">Todos</option>
        <option value="done">Desbloqueados</option>
      </select>
    </div>
    <SelectionToolbar selected={selected.size} total={eligible[key].length}
      onAll={() => update(selectAll(key, draft))}
      onClear={() => update(clearSelection(key, draft))} />
    <p className="detail-note">Las exclusiones individuales se conservan aunque la operación masiva siga activa.</p>
    {!characters ? <Notice tone="warning">Informe de personajes no disponible.</Notice> : <div className="lock-groups">
      {characters.items.map((character) => {
        const options: Array<{ id: string; name: string; available: boolean; compatible?: boolean }> = mode === 'characters'
          ? [{ id: character.code, name: character.name, available: character.unlocked === true }]
          : mode === 'skills'
            ? character.skill_options.map((option) => ({
              id: skillKey(character.code, option.index),
              name: option.name,
              available: character.skills.find((entry) => entry.key === option.index)?.unlocked !== false,
            }))
            : character.skin_options.map((option) => ({
              id: skinKey(character.code, option.index),
              name: option.name,
              available: option.state === 'unlocked',
              compatible: option.compatible,
            }))
        const visible = options.filter((option) => {
          if (!query.trim()) return true
          return option.name.toLowerCase().includes(query.trim().toLowerCase())
            || character.name.toLowerCase().includes(query.trim().toLowerCase())
        }).filter((option) => {
          if (filter === 'all') return true
          if (filter === 'done') return option.available
          return !option.available && (option.compatible ?? true)
        })
        if (visible.length === 0) return null
        const pendingOptions = options.filter((option) => !option.available && (option.compatible ?? true))
        const allSelected = pendingOptions.length > 0 && pendingOptions.every((option) => selected.has(option.id))
        const someSelected = pendingOptions.some((option) => selected.has(option.id)) && !allSelected
        return <section className="lock-group" key={character.code}>
          <header>
            <strong>{character.name}</strong>
            <CheckAll checked={allSelected} indeterminate={someSelected}
              label={`${visible.length}`}
              onChange={(checked) => {
                let next = draft
                for (const option of visible) {
                  if (option.available || option.compatible === false) continue
                  if (checked !== isSelected(key, option.id, next, eligible)) next = toggleItem(key, option.id, next, eligible)
                }
                update(next)
              }} />
          </header>
          <div className="lock-options">
            {visible.map((option) => {
              const checked = selected.has(option.id)
              return <label className={`lock-option ${checked ? 'selected' : ''}`} key={option.id}>
                <input type="checkbox" checked={checked} disabled={option.available || option.compatible === false}
                  onChange={() => update(toggleItem(key, option.id, draft, eligible))} />
                <span>{option.name}</span>
                {option.available && <small>✓</small>}
              </label>
            })}
          </div>
        </section>
      })}
    </div>}
  </div>
}

function numberEdits({
  rows, edits, quickEnabled, quickValue, onChange,
}: {
  rows: LabAdvanced['materials'] | LabAdvanced['seeds'] | LabAdvanced['pet_food']
  edits: Record<string, string>
  quickEnabled: boolean
  quickValue: string
  onChange: (id: string, value: string) => void
}) {
  const [query, setQuery] = useState('')
  const [bulk, setBulk] = useState('')
  const minimum = quickEnabled ? parseQuantity(quickValue) : null
  return <div className="detail-editor">
    <div className="detail-filters">
      <input type="search" value={query} placeholder="Buscar" onChange={(event) => setQuery(event.target.value)} />
      <div className="bulk-apply">
        <input inputMode="numeric" value={bulk} placeholder="Cantidad"
          onChange={(event) => setBulk(event.target.value.replace(/[^\d]/g, ''))} />
        <button type="button" className="button quiet" disabled={parseQuantity(bulk) === null}
          onClick={() => {
            const value = parseQuantity(bulk)
            if (value === null) return
            for (const row of rows) {
              if (row.editable && row.owned && (!query || (row.name.es ?? row.name.en ?? row.id).toLowerCase().includes(query.toLowerCase()))) {
                onChange(row.id, String(value))
              }
            }
          }}>Aplicar</button>
      </div>
    </div>
    <div className="number-list">
      {rows.filter((row) => {
        const name = row.name.es ?? row.name.en ?? row.id
        return !query.trim() || name.toLowerCase().includes(query.trim().toLowerCase()) || row.id.includes(query.trim())
      }).map((row) => {
        const current = row.count
        const manual = edits[row.id] ?? ''
        const proposed = manual !== '' ? parseQuantity(manual)
          : minimum !== null && current !== null && minimum > current ? minimum : null
        const changed = proposed !== null && proposed !== current
        return <label className={`number-row ${changed ? 'changed' : ''}`} key={row.id}>
          <span className="number-name">{row.name.es ?? row.name.en ?? row.id}
            <small>{row.id}</small>
          </span>
          <span className="number-current">{current === null ? '—' : amountFormat.format(current)}</span>
          <input inputMode="numeric" aria-label={`Nueva cantidad para ${row.name.es ?? row.name.en ?? row.id}`}
            value={manual} placeholder={minimum !== null && current !== null
            ? String(Math.max(current, minimum)) : '—'}
            disabled={!row.editable}
            onChange={(event) => onChange(row.id, event.target.value.replace(/[^\d]/g, ''))} />
        </label>
      })}
    </div>
  </div>
}

function MaterialsEditor({ save, draft, update }: { save: SaveBundle; draft: Draft; update: (next: Draft) => void }) {
  if (!save.advanced || save.advanced.available === false) return <Notice tone="warning">Materiales no disponibles en esta partida.</Notice>
  return numberEdits({
    rows: save.advanced.materials,
    edits: draft.materialEdits,
    quickEnabled: draft.quick.materialsMin.enabled,
    quickValue: draft.quick.materialsMin.value,
    onChange: (id, value) => update(setEdit('materials', id, value, draft)),
  })
}

function SeedsEditor({ save, draft, update }: { save: SaveBundle; draft: Draft; update: (next: Draft) => void }) {
  if (!save.advanced || save.advanced.available === false) return <Notice tone="warning">Semillas no disponibles en esta partida.</Notice>
  return numberEdits({
    rows: save.advanced.seeds,
    edits: draft.seedEdits,
    quickEnabled: draft.quick.seedsMin.enabled,
    quickValue: draft.quick.seedsMin.value,
    onChange: (id, value) => update(setEdit('seeds', id, value, draft)),
  })
}

function PetsEditor({ save, draft, update }: { save: SaveBundle; draft: Draft; update: (next: Draft) => void }) {
  if (!save.advanced || save.advanced.available === false) return <Notice tone="warning">Mascotas no disponibles en esta partida.</Notice>
  const advanced = save.advanced
  const eligible = eligibility(save)
  return <div className="pets-detail">
    <SelectionToolbar selected={eligible.pets.filter((id) => isSelected('pets', id, draft, eligible)).length}
      total={eligible.pets.length}
      onAll={() => update(selectAll('pets', draft))}
      onClear={() => update(clearSelection('pets', draft))} />
    <div className="pet-grid">
      {advanced.pets.map((pet) => <label className={`pet-cell ${isSelected('pets', pet.id, draft, eligible) ? 'selected' : ''}`} key={pet.id}>
        <input type="checkbox" aria-label={`Mascota ${pet.name.es ?? pet.name.en ?? pet.id}`}
          disabled={!pet.editable || Boolean(pet.unlocked)} checked={isSelected('pets', pet.id, draft, eligible)}
          onChange={() => update(toggleItem('pets', pet.id, draft, eligible))} />
        <span>{pet.name.es ?? pet.name.en ?? pet.id}</span>
        <small>{pet.unlocked ? 'Activa' : pet.editable ? pet.id : 'No editable'}</small>
      </label>)}
    </div>
    <h3 className="detail-subtitle">Skins de mascotas</h3>
    <SelectionToolbar selected={eligible.petSkins.filter((id) => isSelected('petSkins', id, draft, eligible)).length}
      total={eligible.petSkins.length}
      onAll={() => update(selectAll('petSkins', draft))}
      onClear={() => update(clearSelection('petSkins', draft))} />
    <div className="pet-grid">
      {advanced.pet_skins.map((skin) => <label className={`pet-cell ${isSelected('petSkins', skin.id, draft, eligible) ? 'selected' : ''}`} key={skin.id}>
        <input type="checkbox" aria-label={`Skin ${skin.name.es ?? skin.name.en ?? skin.id}`}
          disabled={!skin.editable || Boolean(skin.unlocked)}
          checked={isSelected('petSkins', skin.id, draft, eligible)}
          onChange={() => update(toggleItem('petSkins', skin.id, draft, eligible))} />
        <span>{skin.name.es ?? skin.name.en ?? skin.id}</span>
        <small>{skin.unlocked ? 'Activa' : skin.id}</small>
      </label>)}
    </div>
    <h3 className="detail-subtitle">Alimento y baterías</h3>
    <div className="number-list">
      {advanced.pet_food.map((row) => <label className="number-row" key={row.id}>
        <span className="number-name">{row.name.es ?? row.name.en ?? row.id}<small>{row.id}</small></span>
        <span className="number-current">{row.count === null ? '—' : amountFormat.format(row.count)}</span>
        <input inputMode="numeric" aria-label={`Cantidad de ${row.name.es ?? row.name.en ?? row.id}`}
          value={draft.petFoodEdits[row.id] ?? ''} placeholder="—"
          onChange={(event) => update(setEdit('petFood', row.id, event.target.value.replace(/[^\d]/g, ''), draft))} />
      </label>)}
    </div>
    <p className="detail-note">Progreso y afinidad son de solo lectura.</p>
  </div>
}

function SeasonEditor({ save, draft, update }: { save: SaveBundle; draft: Draft; update: (next: Draft) => void }) {
  const advanced = save.advanced
  const coin = advanced?.season_coin
  return <div className="detail-editor">
    <label className="number-row">
      <span className="number-name">Monedas de temporada<small>{coin?.path ?? 'seasonData.coin'}</small></span>
      <span className="number-current">{coin?.value == null ? '—' : amountFormat.format(coin.value)}</span>
      <input inputMode="numeric" value={draft.quick.seasonCoin.value} placeholder={coin?.value == null ? '—' : String(coin.value)}
        disabled={!coin?.available}
        onChange={(event) => update(setQuick('seasonCoin', { enabled: true, value: event.target.value.replace(/[^\d]/g, '') }, draft))} />
    </label>
    <label className="number-row">
      <span className="number-name">Recompensas acumuladas<small>itemData.cumulativeFishCount</small></span>
      <span className="number-current">{save.cumulative_fish_count ?? '—'}</span>
      <input inputMode="numeric" value={draft.quick.fishProgress.value} placeholder="—"
        onChange={(event) => update(setQuick('fishProgress', { enabled: true, value: event.target.value.replace(/[^\d]/g, '') }, draft))} />
    </label>
    <label className="toggle-row">
      <input type="checkbox" checked={draft.reborn} disabled={!advanced?.reborn_card.available || advanced.reborn_card.value === true}
        onChange={(event) => update({ ...draft, reborn: event.target.checked })} />
      <span>Tarjeta de renacimiento permanente</span>
    </label>
  </div>
}

function BattlePassEditor({ save, draft, update }: { save: SaveBundle; draft: Draft; update: (next: Draft) => void }) {
  const pass = save.advanced?.battle_pass
  if (!pass?.records?.length) return <Notice tone="warning">El pase de batalla no está disponible en esta partida.</Notice>
  const [season, setSeason] = useState(draft.battlePass.seasonId ?? pass.selected_season_id ?? pass.records[0].season_id)
  const record = pass.records.find((item) => item.season_id === season) ?? pass.records[0]
  return <div className="detail-editor">
    <div className="detail-filters">
      <select value={record.season_id ?? 0} aria-label="Temporada" onChange={(event) => {
        const next = Number(event.target.value)
        setSeason(next)
        update({ ...draft, battlePass: { ...draft.battlePass, enabled: false, seasonId: next, level: '', exp: '', buy: null } })
      }}>
        {pass.records.map((item) => <option key={item.season_id ?? 0} value={item.season_id ?? 0}>Temporada {item.season_id}</option>)}
      </select>
      <button type="button" className="button quiet" disabled={!record.editable}
        onClick={() => update({
          ...draft,
          battlePass: {
            enabled: true,
            seasonId: record.season_id,
            level: record.max_level == null ? '' : String(record.max_level),
            exp: record.cur_exp == null ? '' : String(record.cur_exp),
            buy: record.has_buy,
          },
        })}>Nivel máximo</button>
    </div>
    <div className="number-list">
      <label className="number-row"><span className="number-name">Nivel<small>actual {record.cur_level}</small></span>
        <span className="number-current">{record.max_level ?? '—'}</span>
        <input inputMode="numeric" value={draft.battlePass.level} placeholder={record.cur_level == null ? '—' : String(record.cur_level)}
          onChange={(event) => update({ ...draft, battlePass: { ...draft.battlePass, enabled: true, level: event.target.value.replace(/[^\d]/g, '') } })} />
      </label>
      <label className="number-row"><span className="number-name">Experiencia<small>actual {record.cur_exp}</small></span>
        <span className="number-current">—</span>
        <input inputMode="numeric" value={draft.battlePass.exp} placeholder={record.cur_exp == null ? '—' : String(record.cur_exp)}
          onChange={(event) => update({ ...draft, battlePass: { ...draft.battlePass, enabled: true, exp: event.target.value.replace(/[^\d]/g, '') } })} />
      </label>
      <label className="toggle-row">
        <input type="checkbox" checked={draft.battlePass.buy ?? record.has_buy ?? false} disabled={!record.editable}
          onChange={(event) => update({ ...draft, battlePass: { ...draft.battlePass, enabled: true, buy: event.target.checked } })} />
        <span>Pase premium comprado</span>
      </label>
    </div>
    <p className="detail-note">El pase de batalla conserva su nivel de evidencia experimental.</p>
  </div>
}

function ResourcesEditor({ save, draft, update }: { save: SaveBundle; draft: Draft; update: (next: Draft) => void }) {
  return <div className="detail-editor">
    {([
      ['gems', 'Gemas', save.gems],
      ['fishChip', 'Fichas de pesca', save.fish_chip],
      ['fishProgress', 'Recompensas de pesca', save.cumulative_fish_count],
      ['seasonCoin', 'Monedas de temporada', save.advanced?.season_coin.value],
    ] as Array<[QuantityKey, string, number | null | undefined]>).map(([key, label, current]) =>
      <label className="number-row" key={key}>
        <span className="number-name">{label}</span>
        <span className="number-current">{current == null ? '—' : amountFormat.format(current)}</span>
        <input inputMode="numeric" value={draft.quick[key].value} placeholder="—"
          onChange={(event) => update(setQuick(key, { enabled: true, value: event.target.value.replace(/[^\d]/g, '') }, draft))} />
      </label>)}
  </div>
}

function CategoryGrid({ save, draft, onOpen }: {
  save: SaveBundle
  draft: Draft
  onOpen: (id: CategoryId) => void
}) {
  const { counts } = buildDraftPlan(save, draft)
  const countsMap: Record<CategoryId, number> = {
    recursos: (counts.byCategory.Gemas ?? 0) + (counts.byCategory['Fichas de pesca'] ?? 0)
      + (counts.byCategory['Recompensas de pesca'] ?? 0) + (counts.byCategory['Monedas de temporada'] ?? 0),
    personajes: counts.byCategory.Personajes ?? 0,
    habilidades: counts.byCategory.Habilidades ?? 0,
    skins: counts.byCategory.Skins ?? 0,
    mascotas: counts.byCategory.Mascotas ?? 0,
    materiales: counts.byCategory.Materiales ?? 0,
    semillas: counts.byCategory.Semillas ?? 0,
    temporada: (counts.byCategory['Monedas de temporada'] ?? 0) + (counts.byCategory['Recompensas de pesca'] ?? 0),
    pase: counts.byCategory['Pase de batalla'] ?? 0,
  }
  return <div className="category-grid" data-testid="category-grid">
    {categories.map((category) => <button type="button" className="category-card" key={category.id}
      onClick={() => onOpen(category.id)}>
      <span>{category.label}</span>
      {countsMap[category.id] > 0 && <strong>{amountFormat.format(countsMap[category.id])}</strong>}
    </button>)}
  </div>
}

export function EditorWorkspace({
  save, session, accountLabel, platform, onExpired, onUploaded, onReload, onDirtyChange,
}: {
  save: SaveBundle
  session: { write_ready?: boolean }
  accountLabel: string
  platform: string
  onExpired: () => void
  onUploaded: (result: LabWriteResult) => Promise<void>
  onReload: () => void
  onDirtyChange?: (dirty: boolean) => void
}) {
  const [draft, setDraft] = useState<Draft>(createEmptyDraft)
  const [review, setReview] = useState(false)
  const [prepared, setPrepared] = useState<LabUnifiedPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [confirming, setConfirming] = useState(false)
  const operation = useOperation()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const built = buildDraftPlan(save, draft)
  const hasChanges = built.counts.changes > 0
  const canWrite = Boolean(session.write_ready)

  const route = pathname.startsWith('/editor/categoria/')
    ? pathname.slice('/editor/categoria/'.length).split('/')[0] as CategoryId
    : pathname.startsWith('/editor/categorias') ? 'categories' : 'quick'
  const activeCategory = categories.find((category) => category.id === route)

  useEffect(() => {
    const legacy = pathname.slice('/editor/'.length) as CategoryId
    if (['personajes', 'habilidades', 'skins', 'mascotas'].includes(legacy)) {
      navigate(`/editor/categoria/${legacy}`, { replace: true })
    }
  }, [navigate, pathname])

  useEffect(() => {
    onDirtyChange?.(hasChanges)
  }, [hasChanges, onDirtyChange])

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!hasChanges) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [hasChanges])

  function update(next: Draft) {
    setDraft(next)
    if (prepared) {
      setPrepared(null)
      setConfirm(false)
    }
  }

  function go(path: string) {
    navigate(path)
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

  function prepare() {
    if (!hasChanges || !canWrite) return
    run(async (signal) => {
      setResult(null)
      setConfirm(false)
      const next = await nativeAuth.prepareUnified(built.plan, save.sha256, signal)
      setPrepared(next)
      setReview(true)
    })
  }

  function upload() {
    if (!prepared || confirming) return
    setConfirming(true)
    run(async (signal) => {
      try {
        const uploaded = await nativeAuth.confirm(prepared.backup.id, prepared.candidate_sha256, signal)
        setResult(uploaded)
        setConfirm(false)
        setReview(false)
        if (uploaded.persisted) {
          setPrepared(null)
          setDraft(createEmptyDraft())
          await onUploaded(uploaded)
        }
      } finally {
        setConfirming(false)
      }
    })
  }

  function discard() {
    if (!hasChanges) return
    if (!window.confirm(`¿Descartar ${amountFormat.format(built.counts.changes)} cambios pendientes?`)) return
    setDraft(createEmptyDraft())
    setPrepared(null)
    setReview(false)
    setResult(null)
  }

  const expiredConflict = operation.problem?.code === 'cloud_remote_changed'

  const content = review && prepared
    ? <div className="review-panel" data-testid="unified-preview">
      <div className="review-head">
        <h2>Revisar y guardar</h2>
        <button type="button" className="button quiet" onClick={() => setReview(false)}>Volver</button>
      </div>
      <p className="detail-note">
        {amountFormat.format(prepared.change_count)} campos en un único candidato.
        Se creará un respaldo restaurable y se subirá una sola vez.
      </p>
      <div className="review-categories">
        {prepared.categories.map((category) => <details key={category.key} className="review-category">
          <summary><span>{category.label}</span><strong>{amountFormat.format(category.changes)}</strong></summary>
          <div className="review-detail">
            {Object.entries(category.detail).map(([field, value]) => field === 'kind' ? null
              : <p key={field}><span>{field}</span><code>{Array.isArray(value) ? `${value.length} elementos` : String(value)}</code></p>)}
          </div>
        </details>)}
      </div>
      <details className="review-fields">
        <summary>Campos afectados ({amountFormat.format(prepared.changed_fields.length)})</summary>
        <code>{prepared.changed_fields.join(', ')}</code>
      </details>
      <label className="confirm-row">
        <input type="checkbox" checked={confirm} onChange={(event) => setConfirm(event.target.checked)} />
        <span>Confirmo subir el candidato a {accountLabel}.</span>
      </label>
      <button type="button" className="button primary wide" disabled={!confirm || operation.pending || confirming}
        onClick={upload}>{confirming || operation.pending ? 'Subiendo y verificando…' : 'Guardar en la nube'}</button>
    </div>
    : <div className="editor-content">
      {route === 'quick' && <QuickEdit save={save} draft={draft} update={update} />}
      {route === 'categories' && <CategoryGrid save={save} draft={draft}
        onOpen={(id) => go(`/editor/categoria/${id}`)} />}
      {activeCategory && <div className="category-detail" data-testid={`category-${activeCategory.id}`}>
        <div className="detail-head">
          <button type="button" className="button quiet" onClick={() => go('/editor/categorias')}>← Categorías</button>
          <h2>{activeCategory.label}</h2>
        </div>
        {activeCategory.id === 'recursos' && <ResourcesEditor save={save} draft={draft} update={update} />}
        {activeCategory.id === 'personajes' && <LockList save={save} draft={draft} update={update} mode="characters" />}
        {activeCategory.id === 'habilidades' && <LockList save={save} draft={draft} update={update} mode="skills" />}
        {activeCategory.id === 'skins' && <LockList save={save} draft={draft} update={update} mode="skins" />}
        {activeCategory.id === 'mascotas' && <PetsEditor save={save} draft={draft} update={update} />}
        {activeCategory.id === 'materiales' && <MaterialsEditor save={save} draft={draft} update={update} />}
        {activeCategory.id === 'semillas' && <SeedsEditor save={save} draft={draft} update={update} />}
        {activeCategory.id === 'temporada' && <SeasonEditor save={save} draft={draft} update={update} />}
        {activeCategory.id === 'pase' && <BattlePassEditor save={save} draft={draft} update={update} />}
      </div>}
    </div>

  return <div className="editor-shell">
    <header className="editor-top">
      <div>
        <strong>{accountLabel}</strong>
        <small>{platform} · {save.remote_source}</small>
      </div>
      <div className="editor-mode" role="tablist" aria-label="Modo de edición">
        <button type="button" role="tab" aria-selected={route === 'quick'} className={route === 'quick' ? 'active' : ''}
          onClick={() => go('/editor')}>Rápida</button>
        <button type="button" role="tab" aria-selected={route !== 'quick'} className={route !== 'quick' ? 'active' : ''}
          onClick={() => go('/editor/categorias')}>Categorías</button>
      </div>
    </header>
    {!canWrite && <Notice tone="warning">Acceso de solo lectura: puedes revisar, pero no guardar.</Notice>}
    {expiredConflict && <div className="conflict-banner" role="alert">
      La partida cambió en la nube. <button type="button" className="button quiet" onClick={onReload}>Descargar de nuevo</button>
    </div>}
    {result && <div className={`result-banner ${result.persisted ? 'ok' : 'warn'}`} role="status">
      {result.persisted
        ? `Guardado y verificado. Respaldo ${result.backup_id.slice(0, 8)} disponible.`
        : 'La subida fue aceptada pero no se pudo verificar. No se descarta el resultado.'}
    </div>}
    {result && result.persisted && <div className="result-banner ok">
      <button type="button" className="button quiet" onClick={onReload}>Actualizar partida</button>
    </div>}
    {content}
    {operation.pending && <Loading>{review ? 'Preparando candidato…' : 'Preparando…'}</Loading>}
    {operation.problem && <Problem problem={operation.problem} />}
    <footer className="editor-bar" data-testid="editor-bar">
      <div className="pending-count">
        <strong>{amountFormat.format(built.counts.changes)}</strong>{' '}
        <span>{built.counts.changes === 1 ? 'cambio' : 'cambios'}</span>
        {built.counts.operations > 0 && <>{' '}<small>{amountFormat.format(built.counts.operations)} operaciones</small></>}
      </div>
      <button type="button" className="button quiet" disabled={!hasChanges || operation.pending}
        onClick={discard}>Descartar</button>
      <button type="button" className="button primary" disabled={!hasChanges || !canWrite || operation.pending}
        onClick={prepare}>{review ? 'Revisar' : 'Guardar'}</button>
    </footer>
  </div>
}