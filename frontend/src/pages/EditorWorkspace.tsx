import { ArrowLeft, CircleAlert, CircleCheck, CloudUpload, LoaderCircle } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useBlocker, useLocation, useNavigate } from 'react-router'
import { AccordionGroup } from '../AccordionGroup'
import {
  ApiProblem, nativeAuth,
  type LabAdvanced, type LabBlueprintEntry, type LabHeroLevelEntry, type LabUnifiedPrepared, type LabWriteResult,
  type NativeSaveSummary, type NativeSession,
} from '../api'
import {
  advancedSnapshot, applyItemMinimum, battlePassRecord, buildDraftPlan, clearSelection, createEmptyDraft,
  eligibility, isSelected, minimumSource, originalQuantity, parseQuantity, protectedMaterial, quantityInput,
  quickChecked, selectAll, selectedCount, setBlueprintMode, setBlueprintStatus, setBulk, setDecorationLevel,
  setEdit, setHeroLevel, setPetAffinity, setQuick, toggleItem,
  type BuiltPlan, type BulkKey, type Draft, type Eligibility,
} from '../draft'
import { skillKey, skinKey } from '../unlockSelections'
import { Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'
import {
  amountFormat, categories, CategoryGrid, CategoryIcon, formatOriginal, QuickEdit,
  resources, UnlockStatus,
} from './EditorOverview'
import { KillEffectsEditor, WeaponProgressionEditor, WeaponSkinsEditor } from './WeaponSkinsEditor'

type SaveBundle = NativeSaveSummary
type EditorInputs = { save: SaveBundle; draft: Draft; update: (next: Draft) => void }

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
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

function SelectionToolbar({ save, group, eligible, draft, update }: EditorInputs & {
  group: BulkKey
  eligible: Eligibility
}) {
  const selected = selectedCount(group, draft, eligible)
  const total = eligible[group].length
  return <div className="detail-toolbar">
    <UnlockStatus save={save} group={group} eligible={eligible} selected={selected} />
    {(total > 0 || selected > 0) && <div>
      <button type="button" className="button quiet" disabled={!total || eligible[group].every((id) => isSelected(group, id, draft, eligible))}
        onClick={() => update(selectAll(group, draft))}>Seleccionar pendientes</button>
      <button type="button" className="button quiet" disabled={!selected}
        onClick={() => update(clearSelection(group, draft))}>Quitar selección</button>
    </div>}
  </div>
}

function LockList({ save, draft, update, mode }: EditorInputs & { mode: 'characters' | 'skills' | 'skins' }) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<'pending' | 'all' | 'done'>('pending')
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())
  const expansionSnapshot = useRef<Set<string> | null>(null)
  const characters = save.report?.characters
  const eligible = eligibility(save)
  const pending = new Set(eligible[mode])
  const selected = new Set(eligible[mode].filter((id) => isSelected(mode, id, draft, eligible)))
  const search = query.trim().toLowerCase()
  const groups = (characters?.items ?? []).map((character) => {
    const options = mode === 'characters'
      ? [{ id: character.code, name: character.name, unlocked: character.unlocked === true }]
      : mode === 'skills'
        ? character.skill_options.map(({ index, name }) => ({
          id: skillKey(character.code, index), name,
          unlocked: character.skills.some((skill) => skill.key === index && skill.unlocked === true),
        }))
        : character.skin_options.map((option) => ({
          id: skinKey(character.code, option.index), name: option.name,
          unlocked: option.compatible && option.state === 'unlocked',
        }))
    const visible = options.filter(({ id, name, unlocked }) =>
      (name.toLowerCase().includes(search) || character.name.toLowerCase().includes(search))
      && (filter === 'all' || (filter === 'done' ? unlocked : pending.has(id))))
    return { character, options, visible }
  }).filter(({ visible }) => visible.length)

  // Al buscar, los grupos con coincidencias se abren solos. Al limpiar la búsqueda
  // se recupera la expansión que el usuario tenía antes de empezar a buscar.
  useEffect(() => {
    if (search) {
      if (expansionSnapshot.current === null) expansionSnapshot.current = new Set(expanded)
      const matches = groups.map(({ character }) => character.code)
      setExpanded((previous) => {
        if (matches.every((code) => previous.has(code))) return previous
        return new Set([...previous, ...matches])
      })
    } else if (expansionSnapshot.current !== null) {
      const restore = expansionSnapshot.current
      expansionSnapshot.current = null
      setExpanded(restore)
    }
    // `groups` se recalcula con cada consulta; la expansión manual no debe reiniciarse.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, filter])

  const toggleGroup = (code: string) => setExpanded((previous) => {
    const next = new Set(previous)
    if (next.has(code)) next.delete(code)
    else next.add(code)
    return next
  })

  const optionRow = ({ id, name, unlocked }: { id: string; name: string; unlocked: boolean }) => {
    const checked = selected.has(id)
    return <label className={`lock-option ${checked ? 'selected' : ''}`} key={id}>
      <input type="checkbox" checked={checked} disabled={!pending.has(id)}
        aria-label={name} onChange={() => update(toggleItem(mode, id, draft, eligible))} />
      <span>{name}</span>
      {unlocked ? <small className="unlock-status complete"><CircleCheck size={14} aria-hidden="true" />Disponible</small>
        : !pending.has(id) && <small>Sin dato</small>}
    </label>
  }

  return <div className="detail-editor">
    <SelectionToolbar save={save} group={mode} eligible={eligible} draft={draft} update={update} />
    {characters?.items.length ? <>
      <div className="detail-filters">
        <input type="search" aria-label="Buscar desbloqueos" value={query} placeholder="Buscar"
          onChange={(event) => setQuery(event.target.value)} />
        <select aria-label="Filtrar desbloqueos" value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}>
          <option value="pending">Pendientes</option>
          <option value="all">Todos</option>
          <option value="done">Desbloqueados</option>
        </select>
      </div>
      {groups.length > 0 && <div className="lock-groups">
        {mode === 'characters' ? <div className="lock-group lock-options">
          {groups.flatMap(({ visible }) => visible.map(optionRow))}
        </div> : groups.map(({ character, options, visible }) => {
          const selectable = visible.filter(({ id }) => pending.has(id))
          const checked = selectable.filter(({ id }) => selected.has(id)).length
          const unlocked = options.filter((option) => option.unlocked).length
          const chosen = options.filter((option) => selected.has(option.id)).length
          return <AccordionGroup key={character.code} title={character.name}
            testId={`unlock-group-${character.code}`}
            meta={`${options.length} ${mode === 'skins' ? 'skins' : 'habilidades'}`}
            summary={`${unlocked}/${options.length} desbloqueadas${chosen ? ` · ${chosen} en borrador` : ''}`}
            expanded={expanded.has(character.code)} onToggle={() => toggleGroup(character.code)}>
            {selectable.length > 1 && <div className="accordion-tools">
              <CheckAll checked={checked === selectable.length}
                indeterminate={checked > 0 && checked < selectable.length}
                label={`Seleccionar ${character.name}`}
                onChange={(enabled) => {
                  let next = draft
                  for (const { id } of selectable) {
                    if (enabled !== selected.has(id)) next = toggleItem(mode, id, next, eligible)
                  }
                  update(next)
                }} />
            </div>}
            <div className="lock-options">{visible.map(optionRow)}</div>
          </AccordionGroup>
        })}
      </div>}
      {!groups.length && (query || filter !== 'pending') && <p className="detail-note">Sin resultados</p>}
    </> : null}
  </div>
}

function AmountRow({ label, current, edit, proposed, disabled, invalid, inputLabel = label, onChange }: {
  label: string
  current: number | null
  edit?: string
  proposed?: number
  disabled?: boolean
  invalid?: boolean
  inputLabel?: string
  onChange: (value: string) => void
}) {
  const statusId = useId()
  const value = edit ?? String(proposed ?? current ?? '')
  const status = disabled ? current === null ? 'Sin dato' : 'Solo lectura'
    : proposed !== undefined && parseQuantity(value) !== proposed ? `Pendiente ${formatOriginal(proposed)}`
    : proposed !== undefined && current !== null ? `Anterior ${formatOriginal(current)}`
    : current === null ? 'Sin registro' : null
  return <label className={`number-row${proposed !== undefined ? ' changed' : ''}`}>
    <span className="number-label"><span className="number-name">{label}</span>{status && <small id={statusId}>{status}</small>}</span>
    <input inputMode="numeric" aria-label={inputLabel} value={value} aria-describedby={status ? statusId : undefined}
      placeholder={disabled && current === null ? '—' : undefined} disabled={disabled}
      aria-invalid={(invalid ?? quantityInput(current, edit).invalid) || undefined}
      onChange={(event) => onChange(event.target.value)} />
  </label>
}

function AmountList({ children }: { children: ReactNode }) {
  return <div className="number-list">{children}</div>
}

function ProgressRow({ label, status, current, edit, proposed, checked, disabled, invalid, onToggle, onChange }: {
  label: string
  status: string
  current: number | null
  edit?: string
  proposed?: number
  checked: boolean
  disabled?: boolean
  invalid?: boolean
  onToggle: (checked: boolean) => void
  onChange: (value: string) => void
}) {
  const value = edit ?? String(proposed ?? current ?? '')
  return <div className={`level-row${proposed !== undefined ? ' changed' : ''}`}>
    <input type="checkbox" checked={checked} disabled={disabled} aria-label={`Incluir ${label} en la mejora masiva`}
      onChange={(event) => onToggle(event.target.checked)} />
    <span className="level-copy"><strong>{label}</strong><small>{status}</small></span>
    <input className="level-input" inputMode="numeric" aria-label={`Nivel o progreso de ${label}`} value={value}
      disabled={disabled} aria-invalid={invalid || undefined} onChange={(event) => onChange(event.target.value)} />
  </div>
}

function HeroLevelsEditor({ save, draft, update, built }: EditorInputs & { built: BuiltPlan }) {
  const [query, setQuery] = useState('')
  const levels = advancedSnapshot(save)?.hero_levels
  if (!levels?.available) return <Notice tone="warning">Niveles de personaje sin datos.</Notice>
  const eligible = eligibility(save)
  const selection = eligible.heroLevels
  const checked = quickChecked('heroLevels', draft, eligible)
  const planned = new Map((built.plan.hero_levels ?? []).map(({ code, level }) => [code, level]))
  const search = query.trim().toLowerCase()
  const rows = levels.entries.filter((row) => row.name.toLowerCase().includes(search) || row.id.toLowerCase().includes(search))

  return <section className="detail-editor progress-editor" aria-labelledby="hero-levels-title">
    <div className="detail-subhead">
      <div>
        <h3 className="detail-subtitle" id="hero-levels-title">Niveles de personaje</h3>
        <p className="detail-note">Experimental · máximo {levels.max} documentado; el máximo por personaje no se pudo recuperar.</p>
      </div>
      <CheckAll checked={checked === 'all'} indeterminate={checked === 'some'}
        label={`Mejorar ${selection.length} elegibles al máximo`}
        onChange={(value) => update(setBulk('heroLevels', value, draft))} />
    </div>
    <div className="detail-filters">
      <input type="search" aria-label="Buscar personajes" value={query} placeholder="Buscar"
        onChange={(event) => setQuery(event.target.value)} />
      <span className="detail-note">{planned.size} en borrador</span>
    </div>
    {rows.length ? <div className="level-list">
      {rows.map((row: LabHeroLevelEntry) => {
        const edit = draft.heroLevels[row.id]
        const parsed = parseQuantity(edit ?? '')
        const invalid = edit !== undefined && (parsed === null || (row.level !== null && parsed < row.level) || parsed > levels.max)
        const status = !row.present ? 'Sin registro'
          : !row.editable ? row.reason ?? 'Solo lectura'
            : row.level === null ? 'Valor no entero'
              : `${row.unlocked === false ? 'Bloqueado · ' : ''}Actual ${row.level}/${levels.max}`
        return <ProgressRow key={row.id} label={row.name} status={status} current={row.level}
          edit={edit} proposed={planned.get(row.id)} checked={isSelected('heroLevels', row.id, draft, eligible)}
          disabled={!row.editable} invalid={invalid} onToggle={() => update(toggleItem('heroLevels', row.id, draft, eligible))}
          onChange={(value) => update(setHeroLevel(row.id, value, draft))} />
      })}
    </div> : <p className="detail-note">Sin resultados</p>}
  </section>
}

function NumberEdits({ save, draft, update, built, kind }: EditorInputs & {
  built: BuiltPlan
  kind: 'materials' | 'seeds'
}) {
  const [query, setQuery] = useState('')
  const [bulk, setBulk] = useState<string>()
  const rows = advancedSnapshot(save)?.[kind]
  if (!rows?.length) return <Notice tone="warning">{kind === 'materials' ? 'Materiales' : 'Semillas'} sin datos.</Notice>
  const edits = kind === 'materials' ? draft.materialEdits : draft.seedEdits
  const changes = new Map(built.plan.advanced?.[kind]?.map(({ id, value }) => [id, value]))
  const search = query.trim().toLowerCase()
  const visible = rows.filter((row) => (row.name.es ?? row.name.en ?? row.id).toLowerCase().includes(search)
    || row.id.toLowerCase().includes(search))
  const minimum = minimumSource(visible.filter((row) => kind !== 'materials' || row.id !== protectedMaterial))
  const bulkQuantity = quantityInput(minimum.original, minimum.editable ? bulk : undefined)

  return <div className="detail-editor">
    <div className="detail-filters">
      <input type="search" aria-label={kind === 'materials' ? 'Buscar materiales' : 'Buscar semillas'}
        value={query} placeholder="Buscar" onChange={(event) => setQuery(event.target.value)} />
      <div className="bulk-apply">
        <input inputMode="numeric" aria-label="Cantidad mínima" value={bulkQuantity.value}
          placeholder={minimum.editable ? 'Mínimo' : 'No disponible'} disabled={!minimum.editable}
          aria-invalid={bulkQuantity.invalid || undefined}
          onChange={(event) => setBulk(event.target.value)} />
        <button type="button" className="button quiet" disabled={bulkQuantity.requested === null}
          onClick={() => {
            if (bulkQuantity.requested !== null) {
              update(applyItemMinimum(kind, visible, bulkQuantity.requested, draft))
              setBulk(undefined)
            }
          }}>Aplicar mínimo</button>
      </div>
    </div>
    {visible.length ? <AmountList>
      {visible.map((row) => {
        const name = row.name.es ?? row.name.en ?? row.id
        const current = originalQuantity(row.count)
        return <AmountRow key={row.id} label={name} current={current} edit={edits[row.id]} proposed={changes.get(row.id)}
          inputLabel={`Nueva cantidad para ${name}`} disabled={!row.editable || (current === null && !row.insertable)
            || (kind === 'materials' && row.id === protectedMaterial)}
          onChange={(next) => update(setEdit(kind, row.id, next, current, draft))} />
      })}
    </AmountList> : <p className="detail-note">Sin resultados</p>}
  </div>
}

function PetAffinityEditor({ save, draft, update, built }: EditorInputs & { built: BuiltPlan }) {
  const [query, setQuery] = useState('')
  const progression = advancedSnapshot(save)?.pet_progression
  if (!progression?.available) return <Notice tone="warning">Afinidad de mascotas sin datos.</Notice>
  const eligible = eligibility(save)
  const selection = eligible.petAffinity
  const checked = quickChecked('petAffinity', draft, eligible)
  const planned = new Map((built.plan.pet_affinity ?? []).map(({ code, value }) => [code, value]))
  const search = query.trim().toLowerCase()
  const rows = progression.entries.filter((row) =>
    (row.name.es ?? row.name.en ?? row.id).toLowerCase().includes(search) || row.id.toLowerCase().includes(search))

  return <section className="detail-editor progress-editor" aria-labelledby="pet-affinity-title">
    <div className="detail-subhead">
      <div>
        <h3 className="detail-subtitle" id="pet-affinity-title">Afinidad</h3>
        <p className="detail-note">Experimental · solo subidas hasta el máximo observado. Indicadores ajenos intactos.</p>
      </div>
      <CheckAll checked={checked === 'all'} indeterminate={checked === 'some'}
        label={`Maximizar ${selection.length} compatibles`}
        onChange={(value) => update(setBulk('petAffinity', value, draft))} />
    </div>
    <div className="detail-filters">
      <input type="search" aria-label="Buscar mascotas" value={query} placeholder="Buscar"
        onChange={(event) => setQuery(event.target.value)} />
      <span className="detail-note">{planned.size} en borrador</span>
    </div>
    {rows.length ? <div className="level-list">
      {rows.map((row) => {
        const name = row.name.es ?? row.name.en ?? row.id
        const edit = draft.petAffinity[row.id]
        const parsed = parseQuantity(edit ?? '')
        const invalid = edit !== undefined && (parsed === null
          || (row.intimacy !== null && parsed < row.intimacy) || (row.max !== null && parsed > row.max))
        const status = !row.present
          ? row.editable ? `Sin registro · se creará en 0 y subirá a ${row.max}` : row.reason ?? 'Sin registro'
          : !row.editable ? row.reason ?? 'Solo lectura'
            : row.max === null ? 'Máximo no confirmado'
              : `Actual ${row.intimacy}/${row.max}`
        return <ProgressRow key={row.id} label={name} status={status} current={row.intimacy}
          edit={edit} proposed={planned.get(row.id)} checked={isSelected('petAffinity', row.id, draft, eligible)}
          disabled={!row.editable} invalid={invalid}
          onToggle={() => update(toggleItem('petAffinity', row.id, draft, eligible))}
          onChange={(value) => update(setPetAffinity(row.id, value, draft))} />
      })}
    </div> : <p className="detail-note">Sin resultados</p>}
    {progression.limitation && <p className="detail-note">{progression.limitation}</p>}
  </section>
}

function PetsEditor({ save, draft, update, built }: EditorInputs & { built: BuiltPlan }) {
  const advanced = advancedSnapshot(save)
  if (!advanced) return <Notice tone="warning">Mascotas sin datos.</Notice>
  const eligible = eligibility(save)
  const changes = new Map(built.plan.advanced?.materials?.map(({ id, value }) => [id, value]))
  const petRows = (group: 'pets' | 'petSkins', rows: LabAdvanced['pets'] | LabAdvanced['pet_skins']) =>
    <div className="pet-grid">
      {rows.map((pet) => {
        const selected = isSelected(group, pet.id, draft, eligible)
        const name = pet.name.es ?? pet.name.en ?? pet.id
        const canUnlock = pet.editable && (pet.unlocked === false || pet.insertable)
        return <label className={`pet-cell ${selected ? 'selected' : ''}`} key={pet.id}>
          <input type="checkbox" aria-label={`${group === 'pets' ? 'Mascota' : 'Skin'} ${name}`}
            disabled={!canUnlock} checked={selected}
            onChange={() => update(toggleItem(group, pet.id, draft, eligible))} />
          <span>{name}</span>
          {pet.unlocked === true ? <small className="unlock-status complete"><CircleCheck size={13} aria-hidden="true" />Disponible</small>
            : pet.unlocked == null && <small>{pet.insertable ? 'Sin registro' : 'Sin dato'}</small>}
        </label>
      })}
    </div>
  return <div className="pets-detail">
    <SelectionToolbar save={save} group="pets" eligible={eligible} draft={draft} update={update} />
    {petRows('pets', advanced.pets)}
    <h3 className="detail-subtitle">Skins de mascotas</h3>
    <SelectionToolbar save={save} group="petSkins" eligible={eligible} draft={draft} update={update} />
    {petRows('petSkins', advanced.pet_skins)}
    <h3 className="detail-subtitle">Alimento y baterías</h3>
    {advanced.pet_food.length ? <AmountList>
      {advanced.pet_food.map((row) => {
        const name = row.name.es ?? row.name.en ?? row.id
        const current = originalQuantity(row.count)
        return <AmountRow key={row.id} label={name} current={current} edit={draft.materialEdits[row.id]} proposed={changes.get(row.id)}
          inputLabel={`Cantidad de ${name}`} disabled={!row.editable || (current === null && !row.insertable)}
          onChange={(next) => update(setEdit('petFood', row.id, next, current, draft))} />
      })}
    </AmountList> : <p className="detail-note">Sin datos de alimento y baterías</p>}
    <PetAffinityEditor save={save} draft={draft} update={update} built={built} />
  </div>
}

function BlueprintEditor({ save, draft, update, built }: EditorInputs & { built: BuiltPlan }) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<'all' | 'Got' | 'Researched' | 'missing'>('all')
  const [type, setType] = useState('all')
  const catalog = advancedSnapshot(save)?.blueprints
  if (!catalog?.available) return <Notice tone="warning">Planos sin datos.</Notice>
  const eligible = eligibility(save)
  const selection = eligible.blueprints
  const checked = quickChecked('blueprints', draft, eligible)
  const planned = new Map((built.plan.blueprints ?? []).map(({ id, status }) => [id, status]))
  const search = query.trim().toLowerCase()
  const types = [...new Set(catalog.entries.map((row) => row.subcategory).filter((value): value is string => Boolean(value)))].sort()
  const rows = catalog.entries.filter((row: LabBlueprintEntry) => {
    const name = row.name.es ?? row.name.en ?? row.target ?? row.id
    const matches = name.toLowerCase().includes(search) || row.id.toLowerCase().includes(search)
    const state = filter === 'missing' ? row.status === null : filter === 'all' || row.status === filter
    return matches && state && (type === 'all' || row.subcategory === type)
  })
  const obtainable = eligible.blueprintObtain.length

  return <section className="detail-editor progress-editor" aria-labelledby="blueprints-title">
    <div className="detail-subhead">
      <div>
        <h3 className="detail-subtitle" id="blueprints-title">Planos</h3>
        <p className="detail-note">Experimental · crea planos ausentes del catálogo. No rebaja investigados.</p>
      </div>
      {selection.length > 0 && <CheckAll checked={checked === 'all'} indeterminate={checked === 'some'}
        label={`Seleccionar ${selection.length} compatibles`}
        onChange={(value) => update(setBulk('blueprints', value, draft))} />}
    </div>
    <div className="detail-filters blueprint-actions">
      <button type="button" className="button quiet" disabled={!obtainable}
        onClick={() => update(setBulk('blueprints', true, setBlueprintMode('Got', draft)))}>
        Obtener {obtainable} ausentes
      </button>
      <button type="button" className="button quiet" disabled={!selection.length}
        onClick={() => update(setBulk('blueprints', true, setBlueprintMode('Researched', draft)))}>
        Investigar {selection.length}
      </button>
      <button type="button" className="button quiet" disabled={!selectedCount('blueprints', draft, eligible)}
        onClick={() => update(clearSelection('blueprints', draft))}>Quitar selección</button>
    </div>
    <div className="detail-filters">
      <input type="search" aria-label="Buscar planos" value={query} placeholder="Buscar"
        onChange={(event) => setQuery(event.target.value)} />
      <select aria-label="Filtrar por estado" value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}>
        <option value="all">Todos los estados</option>
        <option value="missing">No obtenidos</option>
        <option value="Got">Obtenidos</option>
        <option value="Researched">Investigados</option>
      </select>
      <select aria-label="Filtrar por tipo" value={type} onChange={(event) => setType(event.target.value)}>
        <option value="all">Todos los tipos</option>
        {types.map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
      <span className="detail-note">{planned.size} en borrador · {catalog.encoding === 'integer' ? 'estados enteros' : 'estados de texto'}</span>
    </div>
    {rows.length ? <div className="level-list blueprint-list">
      {rows.map((row: LabBlueprintEntry) => {
        const name = row.name.es ?? row.name.en ?? row.target ?? row.id
        const researched = row.status === 'Researched'
        const override = draft.blueprintStatus[row.id]
        const value = override ?? row.status ?? ''
        const pending = planned.get(row.id)
        return <div className={`level-row blueprint-row${pending ? ' changed' : ''}`} key={row.id}>
          <input type="checkbox" checked={isSelected('blueprints', row.id, draft, eligible)}
            disabled={researched || (!row.creatable && row.status !== 'Got')}
            aria-label={`Incluir ${name} en la operación masiva`}
            onChange={() => update(toggleItem('blueprints', row.id, draft, eligible))} />
          <span className="level-copy">
            <strong>{name}</strong>
            <small>{row.present
              ? `${row.key} · ${row.subcategory ?? 'Plano'} · ${row.target ?? 'Sin objetivo'}`
              : `Sin registro · ${row.subcategory ?? 'Plano'}${row.observed_extra ? ' · observado' : ''}`}</small>
            {!row.present && <small>{row.reason}</small>}
          </span>
          <select aria-label={`Estado de ${name}`} value={value} disabled={researched}
            onChange={(event) => {
              const next = event.target.value
              if (next === 'Got' || next === 'Researched') update(setBlueprintStatus(row.id, next, draft))
            }}>
            {!row.status && <option value="">No obtenido</option>}
            {row.status !== 'Researched' && <option value="Got">Obtenido</option>}
            <option value="Researched">Investigado</option>
          </select>
        </div>
      })}
    </div> : <p className="detail-note">Sin resultados</p>}
    <p className="detail-note">
      {catalog.entries.filter((row) => row.status === 'Researched').length} investigados ·
      {' '}{catalog.entries.filter((row) => row.status === 'Got').length} obtenidos ·
      {' '}{catalog.entries.filter((row) => row.status === null && row.creatable).length} ausentes compatibles.
    </p>
    {catalog.unmatched.length > 0 && <p className="detail-note">
      {catalog.unmatched.length === 1 ? '1 clave del guardado no se pudo identificar y se conserva intacta.'
      : `${catalog.unmatched.length} claves del guardado no se pudieron identificar y se conservan intactas.`}
    </p>}
    {catalog.limitation && <p className="detail-note">{catalog.limitation}</p>}
  </section>
}

function DecorationEditor({ save, draft, update, built }: EditorInputs & { built: BuiltPlan }) {
  const [query, setQuery] = useState('')
  const decorations = advancedSnapshot(save)?.decorations
  if (!decorations?.available) return <Notice tone="warning">Decoraciones sin datos.</Notice>
  const eligible = eligibility(save)
  const objectChecked = quickChecked('decorations', draft, eligible)
  const levelChecked = quickChecked('decorationLevels', draft, eligible)
  const plannedObjects = new Set(built.plan.decorations?.objects ?? [])
  const plannedLevels = new Map((built.plan.decorations?.levels ?? []).map(({ id, level }) => [id, level]))
  const search = query.trim().toLowerCase()
  const objectRows = decorations.objects.filter((row) =>
    row.label.toLowerCase().includes(search) || row.id.toLowerCase().includes(search))
  const levelRows = decorations.levels.filter((row) =>
    row.id.toLowerCase().includes(search))
  const appearanceGroups = decorations.appearances.reduce<Record<string, typeof decorations.appearances>>((groups, row) => {
    const key = row.subcategory ?? 'otros'
    groups[key] = [...(groups[key] ?? []), row]
    return groups
  }, {})
  const groupLabels: Record<string, string> = {
    room_skin: 'Vestíbulo', garden_skin: 'Jardín', hall_skin: 'Salón',
    magic_area_skin: 'Área mágica', work_shop_skin: 'Taller',
  }

  return <div className="detail-editor decoration-editor">
    <div className="detail-filters">
      <input type="search" aria-label="Buscar decoraciones" value={query} placeholder="Buscar"
        onChange={(event) => setQuery(event.target.value)} />
      <span className="detail-note">
        Vestíbulo actual: {String(decorations.room.current ?? 'sin dato')} · nivel {decorations.room.room_level ?? 'sin dato'}
      </span>
    </div>

    <section aria-labelledby="decor-appearances-title">
      <h3 className="detail-subtitle" id="decor-appearances-title">Apariencias del vestíbulo y jardín</h3>
      <p className="detail-note">{decorations.room.selection_reason} La obtención se gestiona en Planos.</p>
      {Object.entries(appearanceGroups).map(([group, rows]) => <details className="detail-group" key={group}>
        <summary>{groupLabels[group] ?? group} · {rows.filter((row) => row.obtained).length}/{rows.length} obtenidas</summary>
        <div className="level-list">
          {rows.map((row) => {
            const name = row.name.es ?? row.name.en ?? row.id
            return <div className="level-row" key={row.id}>
              <span className="level-copy">
                <strong>{name}</strong>
                <small>{row.key ?? row.id} · {row.researched ? 'Investigada' : row.obtained ? 'Obtenida' : 'No obtenida'}</small>
              </span>
            </div>
          })}
        </div>
      </details>)}
      {!decorations.appearances.length && <p className="detail-note">Sin apariencias identificadas.</p>}
    </section>

    <section aria-labelledby="decor-objects-title">
      <div className="detail-subhead">
        <div>
          <h3 className="detail-subtitle" id="decor-objects-title">Muebles y objetos</h3>
          <p className="detail-note">Experimental · posesión, banderas y planos investigados.</p>
        </div>
        <CheckAll checked={objectChecked === 'all'} indeterminate={objectChecked === 'some'}
          label={`Desbloquear ${eligible.decorations.length} objetos`}
          onChange={(value) => update(setBulk('decorations', value, draft))} />
      </div>
      <div className="level-list">
        {objectRows.map((row) => {
          const selected = isSelected('decorations', row.id, draft, eligible)
          const pending = row.requirements.filter((requirement) => !requirement.met)
          const requirementText = pending.map((requirement) =>
            requirement.kind === 'flag' ? requirement.key : `plano ${requirement.key}`).join(', ')
          return <div className={`level-row${plannedObjects.has(row.id) ? ' changed' : ''}`} key={row.id}>
            <input type="checkbox" checked={selected} disabled={!row.editable}
              aria-label={`Desbloquear ${row.label}`}
              onChange={() => update(toggleItem('decorations', row.id, draft, eligible))} />
            <span className="level-copy">
              <strong>{row.label}</strong>
              <small>{row.reason}{requirementText ? ` Requiere ${requirementText}.` : ''}</small>
            </span>
            <span className="unlock-status">
              {row.functional ? 'Disponible' : row.unlocked ? 'Incompleto' : 'Bloqueado'}
            </span>
          </div>
        })}
      </div>
      {decorations.unknown_objects.length > 0 && <p className="detail-note">
        {decorations.unknown_objects.length} objetos del guardado no están identificados y se conservan intactos.
      </p>}
    </section>

    <section aria-labelledby="decor-levels-title">
      <div className="detail-subhead">
        <div>
          <h3 className="detail-subtitle" id="decor-levels-title">Mejoras de objetos</h3>
          <p className="detail-note">Solo subidas hasta el máximo observado por clave.</p>
        </div>
        <CheckAll checked={levelChecked === 'all'} indeterminate={levelChecked === 'some'}
          label={`Mejorar ${eligible.decorationLevels.length} al máximo`}
          onChange={(value) => update(setBulk('decorationLevels', value, draft))} />
      </div>
      {levelRows.length ? <div className="level-list">
        {levelRows.map((row) => {
          const edit = draft.decorationLevels[row.id]
          const parsed = parseQuantity(edit ?? '')
          const invalid = edit !== undefined && (parsed === null
            || (row.level !== null && parsed < row.level) || parsed > row.max_observed)
          return <ProgressRow key={row.id} label={row.id}
            status={row.level === null ? row.reason : `Actual ${row.level}/${row.max_observed}`}
            current={row.level} edit={edit} proposed={plannedLevels.get(row.id)}
            checked={isSelected('decorationLevels', row.id, draft, eligible)}
            disabled={!row.editable} invalid={invalid}
            onToggle={() => update(toggleItem('decorationLevels', row.id, draft, eligible))}
            onChange={(value) => update(setDecorationLevel(row.id, value, draft))} />
        })}
      </div> : <p className="detail-note">Sin resultados</p>}
      {decorations.unknown_levels.length > 0 && <p className="detail-note">
        {decorations.unknown_levels.length} niveles no identificados se conservan intactos.
      </p>}
    </section>
    {decorations.limitation && <p className="detail-note">{decorations.limitation}</p>}
  </div>
}

function ResourceList({ save, draft, update, built, season = false }: EditorInputs & {
  built: BuiltPlan
  season?: boolean
}) {
  const reborn = advancedSnapshot(save)?.reborn_card
  return <div className="detail-editor">
    <AmountList>
      {resources.filter(({ key }) => !season || key === 'fishProgress' || key === 'seasonCoin')
        .map(({ key, label }) => {
          const { original, editable, invalid, requested, value } = built.quantities[key]
          return <AmountRow key={key} label={label} current={original} disabled={!editable}
            edit={value} proposed={requested ?? undefined} invalid={invalid}
            onChange={(next) => update(setQuick(key, next, draft))} />
        })}
    </AmountList>
    {season && <label className="toggle-row">
      <input type="checkbox" checked={draft.reborn || reborn?.value === true} disabled={!reborn?.available || reborn.value !== false}
        onChange={(event) => update({ ...draft, reborn: event.target.checked })} />
      <span>Tarjeta de renacimiento permanente</span>
      <small>{reborn?.value === true ? 'Activa' : reborn?.available ? 'Inactiva' : 'Sin dato'}</small>
    </label>}
  </div>
}

function BattlePassEditor({ save, draft, update, built }: EditorInputs & { built: BuiltPlan }) {
  const pass = advancedSnapshot(save)?.battle_pass
  const records = pass?.records ?? []
  const record = battlePassRecord(advancedSnapshot(save), draft.battlePass.seasonId)
  if (!record) return <Notice tone="warning">Pase de batalla sin datos.</Notice>
  const planned = built.plan.advanced?.battle_pass
  const edit = (patch: Partial<Draft['battlePass']>) =>
    update({ ...draft, battlePass: { ...draft.battlePass, seasonId: record.season_id, ...patch } })
  return <div className="detail-editor">
    <div className="detail-filters">
      <select value={record.season_id ?? ''} aria-label="Temporada" onChange={(event) => {
        const seasonId = event.target.value === '' ? null : Number(event.target.value)
        update({ ...draft, battlePass: { seasonId, buy: null } })
      }}>
        {records.map((item) => <option key={item.index ?? item.season_id} value={item.season_id ?? ''}>{item.season_id == null ? 'Sin temporada' : `Temporada ${item.season_id}`}</option>)}
      </select>
      <button type="button" className="button quiet" disabled={!record.editable || record.max_level == null}
        onClick={() => edit({ level: String(record.max_level) })}>Nivel máximo</button>
    </div>
    <AmountList>
      <AmountRow label="Nivel" current={originalQuantity(record.cur_level)} edit={draft.battlePass.level}
        proposed={planned?.cur_level ?? undefined} disabled={!record.editable}
        onChange={(value) => edit({ level: value })} />
      <AmountRow label="Experiencia" current={originalQuantity(record.cur_exp)} edit={draft.battlePass.exp}
        proposed={planned?.cur_exp ?? undefined} disabled={!record.editable}
        onChange={(value) => edit({ exp: value })} />
    </AmountList>
    <label className="toggle-row">
      <input type="checkbox" checked={draft.battlePass.buy ?? record.has_buy ?? false} disabled={!record.editable}
        onChange={(event) => edit({ buy: event.target.checked })} />
      <span>Estado premium local</span>
      <small>{record.has_buy == null ? 'Sin dato' : record.has_buy ? 'Activo' : 'Inactivo'}</small>
    </label>
    <p className="detail-note">Pase de batalla experimental.</p>
  </div>
}

function LeaveEditor({ blocked, busy, stay, leave }: {
  blocked: boolean
  busy: boolean
  stay: () => void
  leave: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (blocked) dialog.current?.showModal()
    else dialog.current?.close()
  }, [blocked])
  return <dialog className="editor-dialog" ref={dialog} aria-labelledby="leave-editor-title"
    onCancel={(event) => { event.preventDefault(); stay() }}>
    <h2 id="leave-editor-title">{busy ? 'Operación en curso' : '¿Salir del editor?'}</h2>
    <p>{busy ? 'Espera a que termine la operación.' : 'Se descartarán los cambios pendientes de esta partida.'}</p>
    <div>
      <button type="button" className="button quiet" onClick={stay} autoFocus>Seguir editando</button>
      {!busy && <button type="button" className="button primary" onClick={leave}>Descartar y salir</button>}
    </div>
  </dialog>
}

type EditorAction = 'prepare' | 'upload' | 'reload'

export function EditorWorkspace({
  save, session, accountId, basePath, accountLabel, loadingSave, loadProblem, onExpired, onReload,
  onBackupChanged, onCloudWrite,
}: {
  save: SaveBundle
  session: NativeSession
  accountId: string
  basePath: string
  accountLabel: string
  loadingSave: boolean
  loadProblem: ApiProblem | null
  onExpired: () => void
  onReload: (signal: AbortSignal) => Promise<SaveBundle>
  onBackupChanged: () => void
  onCloudWrite: () => void
}) {
  const [draft, setDraft] = useState<Draft>(createEmptyDraft)
  const [review, setReview] = useState(false)
  const [prepared, setPrepared] = useState<LabUnifiedPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const [needsRefresh, setNeedsRefresh] = useState(false)
  const [action, setAction] = useState<EditorAction | null>(null)
  const inFlight = useRef(false)
  const preview = useRef<HTMLDivElement>(null)
  const bar = useRef<HTMLElement>(null)
  const operation = useOperation()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const built = buildDraftPlan(save, draft, session)
  const hasChanges = built.counts.changes > 0
  const canWrite = Boolean(session.write_ready)
  // Preparar un candidato no escribe en la nube. Solo habilitamos esa fase
  // cuando la matriz declara la escritura pendiente de validación (iOS); así
  // una sesión Android con escritura deshabilitada sigue siendo de solo lectura.
  const pendingValidation = !canWrite && session.write_state === 'write_pending_validation'
  const canEdit = canWrite || (pendingValidation && Boolean(session.prepare_ready))
  const busy = action !== null || loadingSave

  const pass = battlePassRecord(advancedSnapshot(save), draft.battlePass.seasonId)
  const quantities = [...Object.values(built.quantities),
    quantityInput(originalQuantity(pass?.cur_level), draft.battlePass.level),
    quantityInput(originalQuantity(pass?.cur_exp), draft.battlePass.exp),
  ]
  const itemEdits = [...Object.values(draft.materialEdits), ...Object.values(draft.seedEdits)]
  const advanced = advancedSnapshot(save)
  const heroMax = advanced?.hero_levels?.max ?? 0
  const heroEdits = (advanced?.hero_levels?.entries ?? []).flatMap((row) => {
    const raw = draft.heroLevels[row.id]
    if (raw === undefined) return []
    const parsed = parseQuantity(raw)
    return [{ parsed, current: row.level, max: heroMax, editable: row.editable }]
  })
  const petEdits = (advanced?.pet_progression?.entries ?? []).flatMap((row) => {
    const raw = draft.petAffinity[row.id]
    if (raw === undefined) return []
    const parsed = parseQuantity(raw)
    return [{ parsed, current: row.intimacy, max: row.max, editable: row.editable }]
  })
  const invalidDraft = quantities.some(({ invalid }) => invalid)
    || itemEdits.some((value) => value !== '' && parseQuantity(value) === null)
    || [...heroEdits, ...petEdits].some(({ parsed, current, max, editable }) =>
      !editable || parsed === null || (current !== null && parsed < current) || (max !== null && parsed > max))
  const dirty = hasChanges || invalidDraft || quantities.some(({ changed }) => changed) || itemEdits.includes('')
    || heroEdits.some(({ parsed, current }) => parsed !== current) || petEdits.some(({ parsed, current }) => parsed !== current)

  const editorBase = `${basePath}/editor`
  const editorSuffix = pathname.startsWith(editorBase) ? pathname.slice(editorBase.length) : ''
  const route = editorSuffix.startsWith('/categoria/')
    ? editorSuffix.slice('/categoria/'.length).split('/')[0]
    : editorSuffix.startsWith('/categorias') ? 'categories' : 'quick'
  const activeCategory = categories.find((category) => category.id === route)
  const showQuick = !activeCategory && route !== 'categories'
  const blocker = useBlocker(({ nextLocation }) =>
    (dirty || inFlight.current) && !nextLocation.pathname.startsWith(`${basePath}/editor`))

  useEffect(() => {
    const legacy = editorSuffix.slice(1).replace(/\/$/, '')
    if (['personajes', 'habilidades', 'skins', 'mascotas'].includes(legacy)) {
      void navigate(`${editorBase}/categoria/${legacy}`, { replace: true })
    }
    setReview(false)
    setConfirm(false)
  }, [editorBase, editorSuffix, navigate])

  useEffect(() => {
    if (!dirty && !busy) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty, busy])

  useEffect(() => {
    if (!review || !prepared) return
    preview.current?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
  }, [review, prepared])

  useEffect(() => {
    const viewport = window.visualViewport
    if (!viewport) return
    const root = document.documentElement
    let frame = 0
    function activeEditable() {
      const active = document.activeElement
      return active instanceof HTMLElement
        && Boolean(active.closest('input:not([type="checkbox"]):not([type="radio"]), textarea, select, [contenteditable="true"]'))
    }
    function positionBar() {
      if (!viewport) return 0
      // Solo se compensa el teclado virtual. El rebote o el desplazamiento normal
      // de iOS no debe alterar `bottom` ni despegar la barra del borde inferior.
      if (viewport.scale !== 1 || !activeEditable()) {
        root.style.setProperty('--editor-keyboard-offset', '0px')
        return 0
      }
      const covered = window.innerHeight - viewport.height - viewport.offsetTop
      const offset = covered > 120 ? Math.max(0, covered) : 0
      root.style.setProperty('--editor-keyboard-offset', `${offset}px`)
      return offset
    }
    function afterResize() {
      cancelAnimationFrame(frame)
      if (!positionBar()) return
      frame = requestAnimationFrame(() => {
        const active = document.activeElement
        if (!(active instanceof HTMLInputElement) || !active.closest('.editor-shell') || !bar.current) return
        const overlap = active.getBoundingClientRect().bottom - bar.current.getBoundingClientRect().top
        if (overlap >= 0) window.scrollBy(0, overlap + 12)
      })
    }
    positionBar()
    viewport.addEventListener('resize', afterResize)
    window.addEventListener('orientationchange', afterResize)
    document.addEventListener('focusin', afterResize)
    document.addEventListener('focusout', afterResize)
    return () => {
      cancelAnimationFrame(frame)
      viewport.removeEventListener('resize', afterResize)
      window.removeEventListener('orientationchange', afterResize)
      document.removeEventListener('focusin', afterResize)
      document.removeEventListener('focusout', afterResize)
      root.style.removeProperty('--editor-keyboard-offset')
    }
  }, [])

  function update(next: Draft) {
    if (inFlight.current || needsRefresh) return
    setDraft(next)
    setPrepared(null)
    setConfirm(false)
    setResult(null)
    operation.clearProblem()
  }

  function go(path: string) {
    setReview(false)
    setConfirm(false)
    void navigate(path)
  }

  function run(nextAction: EditorAction, task: (signal: AbortSignal) => Promise<void>) {
    if (inFlight.current || loadingSave) return
    inFlight.current = true
    setAction(nextAction)
    void operation.run(async (signal) => {
      try {
        await task(signal)
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      } finally {
        inFlight.current = false
        setAction(null)
      }
    })
  }

  function prepare() {
    if (!hasChanges || invalidDraft || !canEdit || needsRefresh) return
    run('prepare', async (signal) => {
      setResult(null)
      setConfirm(false)
      const next = await nativeAuth.prepareUnified(built.plan, save.sha256, signal, accountId)
      if (signal.aborted) return
      onBackupChanged()
      setPrepared(next)
      setReview(true)
    })
  }

  function upload() {
    if (!prepared || !confirm || !canWrite) return
    run('upload', async (signal) => {
      const uploaded = await nativeAuth.confirm(prepared.backup.id, prepared.candidate_sha256, signal, accountId)
        .finally(() => { if (!signal.aborted) onBackupChanged() })
      if (signal.aborted) return
      if (uploaded.uploaded || uploaded.persisted) onCloudWrite()
      setResult(uploaded)
      setConfirm(false)
      setReview(false)
      setPrepared(null)
      if (uploaded.persisted) {
        setDraft(createEmptyDraft())
        setNeedsRefresh(true)
        await onReload(signal)
        if (!signal.aborted) setNeedsRefresh(false)
      } else if (uploaded.uploaded) {
        // La escritura se envió pero no se pudo confirmar la persistencia.
        // Bloquea otra edición hasta verificar la copia real de la nube.
        setNeedsRefresh(true)
      }
    })
  }

  function reload() {
    if (dirty && !window.confirm('Si la copia descargada cambió, se descartarán los cambios pendientes. ¿Continuar?')) return
    run('reload', async (signal) => {
      const fresh = await onReload(signal)
      if (signal.aborted) return
      if (fresh.sha256 !== save.sha256) setDraft(createEmptyDraft())
      setNeedsRefresh(false)
      setPrepared(null)
      setReview(false)
      setConfirm(false)
    })
  }

  function discard() {
    if (!dirty || inFlight.current) return
    if (!window.confirm('¿Descartar los cambios pendientes?')) return
    setDraft(createEmptyDraft())
    setPrepared(null)
    setReview(false)
    setConfirm(false)
    setResult(null)
    operation.clearProblem()
  }

  const expiredConflict = operation.problem?.code === 'cloud_remote_changed'
  const refreshFailed = Boolean(result?.persisted && needsRefresh && operation.problem && !expiredConflict)
  const progress = action === 'prepare' ? 'Preparando candidato…'
    : action === 'upload' ? 'Guardando y verificando…' : action === 'reload' || loadingSave ? 'Descargando partida…' : null
  const barError = operation.problem || (result && !result.persisted)
  const barStatus = progress ?? (invalidDraft ? 'Revisa las cantidades'
    : barError ? 'Revisa el resultado' : result?.persisted ? 'Verificado' : null)

  const content = review && prepared
    ? <div className="review-panel" data-testid="unified-preview" ref={preview} tabIndex={-1}>
      <div className="review-head">
        <h2>{canWrite ? 'Revisar y guardar' : 'Revisar candidato'}</h2>
        <button type="button" className="button quiet" disabled={busy} onClick={() => { setReview(false); setConfirm(false) }}>Volver</button>
      </div>
      {canWrite
        ? <p className="detail-note">Se creará un respaldo restaurable antes de subir el candidato.</p>
        : <Notice tone="warning">
          Se creó un respaldo restaurable y un candidato verificado. La subida remota de iOS
          está pendiente de validación: no se envió nada a la nube.
        </Notice>}
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
      {canWrite
        ? <label className="confirm-row">
          <input type="checkbox" checked={confirm} disabled={busy} onChange={(event) => setConfirm(event.target.checked)} />
          <span>Confirmo subir el candidato a {accountLabel}.</span>
        </label>
        : <p className="detail-note">
          Respaldo <code>{prepared.backup.id.slice(0, 8)}</code> · candidato{' '}
          <code>{prepared.candidate_sha256.slice(0, 12)}…</code>
        </p>}
    </div>
    : <fieldset className="editor-content" disabled={busy || needsRefresh || !canEdit}>
      {showQuick && <QuickEdit save={save} draft={draft} built={built} update={update} />}
      {route === 'categories' && <CategoryGrid built={built} onOpen={(id) => go(`${editorBase}/categoria/${id}`)} />}
      {activeCategory && <div className="category-detail" data-testid={`category-${activeCategory.id}`}>
        <div className="detail-head">
          <button type="button" aria-label="← Categorías" className="editor-back" onClick={() => go(`${editorBase}/categorias`)}>
            <ArrowLeft size={17} aria-hidden="true" />
          </button>
          <CategoryIcon id={activeCategory.id} />
          <h2>{activeCategory.label}</h2>
        </div>
        {activeCategory.id === 'recursos' && <ResourceList save={save} draft={draft} update={update} built={built} />}
        {activeCategory.id === 'personajes' && <>
          <LockList key="characters" save={save} draft={draft} update={update} mode="characters" />
          <HeroLevelsEditor save={save} draft={draft} update={update} built={built} />
        </>}
        {activeCategory.id === 'planos' && <BlueprintEditor save={save} draft={draft} update={update} built={built} />}
        {activeCategory.id === 'decoraciones' && <DecorationEditor save={save} draft={draft} update={update} built={built} />}
        {activeCategory.id === 'habilidades' && <LockList key="skills" save={save} draft={draft} update={update} mode="skills" />}
        {activeCategory.id === 'skins' && <LockList key="skins" save={save} draft={draft} update={update} mode="skins" />}
        {activeCategory.id === 'armas' && <div className="weapon-category-editors">
          <WeaponProgressionEditor key={`weapon-progression:${save.sha256}`} save={save} draft={draft} update={update} />
          <h3 className="detail-subtitle">Skins de arma</h3>
          <WeaponSkinsEditor key={`weapon-skins:${save.sha256}`} save={save} draft={draft} update={update} />
        </div>}
        {activeCategory.id === 'efectos' && <KillEffectsEditor key={`kill-effects:${save.sha256}`} save={save} draft={draft} update={update} />}
        {activeCategory.id === 'mascotas' && <PetsEditor save={save} draft={draft} update={update} built={built} />}
        {activeCategory.id === 'materiales' && <NumberEdits key={`materials:${save.sha256}`} save={save} draft={draft} update={update} built={built} kind="materials" />}
        {activeCategory.id === 'semillas' && <NumberEdits key={`seeds:${save.sha256}`} save={save} draft={draft} update={update} built={built} kind="seeds" />}
        {activeCategory.id === 'temporada' && <ResourceList save={save} draft={draft} update={update} built={built} season />}
        {activeCategory.id === 'pase' && <BattlePassEditor save={save} draft={draft} update={update} built={built} />}
      </div>}
    </fieldset>

  function tabKeys(event: KeyboardEvent<HTMLDivElement>) {
    if (busy || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const quick = event.key === 'Home' || (event.key !== 'End' && !showQuick)
    event.currentTarget.querySelector<HTMLButtonElement>(quick ? '#editor-quick-tab' : '#editor-categories-tab')?.focus()
    go(quick ? editorBase : `${editorBase}/categorias`)
  }

  return <div className="editor-shell">
    {!activeCategory && <div className="editor-mode" role="tablist" aria-label="Modo de edición" onKeyDown={tabKeys}>
      <button id="editor-quick-tab" type="button" role="tab" aria-controls="editor-panel" aria-selected={showQuick}
        tabIndex={showQuick ? 0 : -1} disabled={busy} onClick={() => go(editorBase)}>Rápida</button>
      <button id="editor-categories-tab" type="button" role="tab" aria-controls="editor-panel" aria-selected={!showQuick}
        tabIndex={showQuick ? -1 : 0} disabled={busy} onClick={() => go(`${editorBase}/categorias`)}>Categorías</button>
    </div>}
    {pendingValidation
      ? <Notice tone="warning">
        iOS: puedes editar, preparar un candidato y crear un respaldo. La subida
        remota está pendiente de validación; no se envía nada a la nube.
      </Notice>
      : !canWrite && <Notice tone="warning">Partida de solo lectura.</Notice>}
    {expiredConflict && <div className="conflict-banner" role="alert">
      La partida cambió en la nube. <button type="button" className="button quiet" disabled={busy} onClick={reload}>Descargar de nuevo</button>
    </div>}
    {loadProblem && !save.report && <div className="conflict-banner">
      No se pudo descargar el informe. <button type="button" className="button quiet" disabled={busy} onClick={reload}>Reintentar descarga</button>
    </div>}
    {operation.problem && !expiredConflict && <Problem problem={operation.problem} />}
    {result && <div className={`result-banner ${result.persisted && !refreshFailed ? 'ok' : 'warn'}`} role="status">
      {result.persisted
        ? refreshFailed
          ? 'Subida confirmada. No se pudo descargar la partida actualizada; el editor está bloqueado hasta reintentar solo la descarga.'
          : `Guardado y verificado. Respaldo ${result.backup_id.slice(0, 8)} disponible.`
        : needsRefresh
          ? 'Subida sin confirmar. Actualiza la partida para comprobar su estado antes de volver a editar.'
          : 'No se pudo verificar la subida. El borrador sigue disponible.'}
    </div>}
    {needsRefresh && !busy && <button type="button" className="button quiet editor-reload" onClick={reload}>
      {refreshFailed ? 'Reintentar descarga' : 'Actualizar partida'}
    </button>}
    <div id="editor-panel" role="tabpanel" aria-label={activeCategory?.label}
      aria-labelledby={activeCategory ? undefined : showQuick ? 'editor-quick-tab' : 'editor-categories-tab'}>
      {content}
    </div>
    <footer className="editor-bar" ref={bar} data-testid="editor-bar" aria-busy={busy}>
      <div className="editor-bar-inner">
        <div className="pending-count">
          <span><strong>{amountFormat.format(built.counts.changes)}</strong>{' '}{built.counts.changes === 1 ? 'cambio' : 'cambios'}</span>
          {barStatus && <small className={barError || invalidDraft ? 'error' : result?.persisted ? 'success' : ''} role="status">
            {progress ? <LoaderCircle className="editor-spin" size={13} aria-hidden="true" />
              : barError || invalidDraft ? <CircleAlert size={13} aria-hidden="true" /> : <CircleCheck size={13} aria-hidden="true" />}
            {barStatus}
          </small>}
        </div>
        <button type="button" className="button quiet" disabled={!dirty || busy} onClick={discard}>Descartar</button>
        <button type="button" className="button primary" disabled={!canEdit || busy || needsRefresh
          || (review ? !canWrite || !confirm : !hasChanges || invalidDraft || expiredConflict)}
          onClick={review && canWrite ? upload : prepare}>
          {!review && canWrite && <CloudUpload size={16} aria-hidden="true" />}
          {review
            ? canWrite ? 'Guardar en la nube' : 'Subida pendiente de validación'
            : canWrite ? 'Guardar' : 'Preparar candidato'}
        </button>
      </div>
    </footer>
    <LeaveEditor blocked={blocker.state === 'blocked'} busy={busy}
      stay={() => { if (blocker.state === 'blocked') blocker.reset() }}
      leave={() => { if (!inFlight.current && blocker.state === 'blocked') blocker.proceed() }} />
  </div>
}
