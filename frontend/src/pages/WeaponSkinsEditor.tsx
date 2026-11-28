import { CircleCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { AccordionGroup } from '../AccordionGroup'
import type {
  LabKillEffectItem, LabWeaponProgressionItem, LabWeaponSkinItem, NativeSaveSummary,
} from '../api'
import {
  clearSelection, eligibility, isSelected, selectAll, selectedCount, setItems, setWeaponSkinEquip, toggleItem,
  type Draft,
} from '../draft'
import { Notice } from '../ui'
import { amountFormat, UnlockStatus } from './EditorOverview'

type EditorProps = { save: NativeSaveSummary; draft: Draft; update: (next: Draft) => void }
type Filter = 'pending' | 'all' | 'done'

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

function Toolbar({ save, group, draft, update }: EditorProps & {
  group: 'weaponProgression' | 'weaponSkins' | 'killEffects'
}) {
  const eligible = eligibility(save)
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

function FilterControls({
  query, setQuery, filter, setFilter, searchLabel, searchPlaceholder = 'Buscar skin o arma',
  allLabel = 'Todas', doneLabel = 'Desbloqueadas',
}: {
  query: string
  setQuery: (value: string) => void
  filter: Filter
  setFilter: (value: Filter) => void
  searchLabel?: string
  searchPlaceholder?: string
  allLabel?: string
  doneLabel?: string
}) {
  return <div className="detail-filters">
    {searchLabel && <input type="search" aria-label={searchLabel} value={query} placeholder={searchPlaceholder}
      onChange={(event) => setQuery(event.target.value)} />}
    <select aria-label="Filtrar estado" value={filter} onChange={(event) => setFilter(event.target.value as Filter)}>
      <option value="pending">Pendientes</option>
      <option value="all">{allLabel}</option>
      <option value="done">{doneLabel}</option>
    </select>
  </div>
}

function progressionName(item: LabWeaponProgressionItem) {
  return item.name_es || item.name_en || item.id
}

function forgeLabel(item: LabWeaponProgressionItem) {
  if (!item.forgeable) return 'No forjable'
  if (item.forge_ready) return 'Forja disponible'
  return 'Forja requiere descubrir'
}

type WeaponMode = 'discover' | 'forge'
type ForgeFilter = 'pending' | 'all' | 'locked' | 'unlocked' | 'forgeable' | 'non_forgeable'

function rarityLabel(level: number | null) {
  if (level === 0) return 'Blanca'
  if (level === 1) return 'Verde'
  if (level === 2) return 'Azul'
  if (level === 3) return 'Morada'
  if (level === 4) return 'Naranja'
  if (level === 5) return 'Roja'
  if (level === 6) return 'Mítica'
  return 'Sin rareza'
}

function forgeStateLabel(item: LabWeaponProgressionItem) {
  if (!item.forgeable) return 'No forjable'
  if (item.forge_unlock_status === 'pending_research') return 'Requisito pendiente'
  if (item.forge_unlock_status === 'ready') {
    return item.requirement_status === 'pending_fusion_research'
      ? 'Forja desbloqueada (provisional)' : 'Forja desbloqueada'
  }
  if (item.required_obtains !== null) {
    const suffix = item.requirement_status === 'pending_fusion_research' ? ' (provisional)' : ''
    return `Requiere ${amountFormat.format(item.required_obtains)}${suffix}`
  }
  return 'Requiere desbloqueo'
}

function progressionDetail(item: LabWeaponProgressionItem, selected: boolean) {
  const current = item.count === null ? 'sin registrar' : amountFormat.format(item.count)
  if (item.required_obtains !== null) {
    const proposed = selected || (item.count ?? 0) < item.required_obtains
      ? item.proposed_forge_count
      : item.count
    return `Actual: ${current}/${amountFormat.format(item.required_obtains)} → Propuesto: `
      + `${proposed === null ? '—' : `${amountFormat.format(proposed)}/${amountFormat.format(item.required_obtains)}`}`
  }
  const target = item.recommended_obtains
  return `Actual: ${current} → Objetivo seguro: ${target === null ? '—' : amountFormat.format(target)}`
}

function ForgeUnlockPanel({ save, draft, update }: EditorProps) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<ForgeFilter>('pending')
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())
  const snapshot = save.weapon_progression
  const items = snapshot?.items ?? []
  const provisional = items.filter(
    (item) => item.requirement_status === 'pending_fusion_research',
  ).length
  const eligible = eligibility(save)
  const pending = new Set(eligible.weaponForgeUnlock)
  const selected = new Set(
    eligible.weaponForgeUnlock.filter((id) => isSelected('weaponForgeUnlock', id, draft, eligible)),
  )
  const search = query.trim().toLowerCase()
  const grouped = new Map<string, LabWeaponProgressionItem[]>()
  for (const item of items) {
    const group = item.subcategory || 'Otras'
    const rows = grouped.get(group)
    if (rows) rows.push(item)
    else grouped.set(group, [item])
  }
  const matchesFilter = (item: LabWeaponProgressionItem) => {
    if (filter === 'all') return true
    if (filter === 'pending') return item.forgeable && !item.forge_unlock_ready
    if (filter === 'locked') return item.forgeable && !item.forge_unlock_ready
    if (filter === 'unlocked') return item.forge_unlock_ready
    if (filter === 'forgeable') return item.forgeable
    return !item.forgeable
  }
  const groups = Array.from(grouped, ([category, options]) => {
    const visible = options.filter((item) => {
      const matches = !search || progressionName(item).toLowerCase().includes(search)
        || item.id.toLowerCase().includes(search) || category.toLowerCase().includes(search)
      return matches && matchesFilter(item)
    })
    return { category, options, visible }
  }).filter(({ visible }) => visible.length)

  const toggleGroup = (category: string) => setExpanded((previous) => {
    const next = new Set(previous)
    if (next.has(category)) next.delete(category)
    else next.add(category)
    return next
  })

  return <div data-testid="weapon-forge-unlock-editor">
    <div className="detail-toolbar">
      <UnlockStatus save={save} group="weaponForgeUnlock" eligible={eligible} selected={selected.size} />
      {(eligible.weaponForgeUnlock.length > 0 || selected.size > 0) && <div>
        <button type="button" className="button quiet"
          disabled={!eligible.weaponForgeUnlock.length
            || eligible.weaponForgeUnlock.every((id) => isSelected('weaponForgeUnlock', id, draft, eligible))}
          onClick={() => update(selectAll('weaponForgeUnlock', draft))}>Seleccionar forjables pendientes</button>
        <button type="button" className="button quiet" disabled={!selected.size}
          onClick={() => update(clearSelection('weaponForgeUnlock', draft))}>Quitar selección</button>
      </div>}
    </div>
    <div className="detail-filters">
      <input type="search" aria-label="Buscar armas forjables" value={query}
        placeholder="Buscar arma, rareza o tipo" onChange={(event) => setQuery(event.target.value)} />
      <select aria-label="Filtrar forja" value={filter}
        onChange={(event) => setFilter(event.target.value as ForgeFilter)}>
        <option value="pending">Pendientes</option>
        <option value="all">Todas</option>
        <option value="locked">Bloqueadas para forja</option>
        <option value="unlocked">Desbloqueadas para forja</option>
        <option value="forgeable">Solo forjables</option>
        <option value="non_forgeable">No forjables</option>
      </select>
    </div>
    {groups.length > 0 && <div className="lock-groups">
      {groups.map(({ category, options, visible }) => {
        const selectable = visible.filter(({ id }) => pending.has(id))
        const checked = selectable.filter(({ id }) => selected.has(id)).length
        const unlocked = options.filter((item) => item.forge_unlock_ready).length
        const forgeable = options.filter((item) => item.forgeable).length
        const chosen = options.filter((item) => selected.has(item.id)).length
        return <AccordionGroup key={category} title={category}
          testId={`weapon-forge-group-${category}`}
          meta={`${options.length} ${options.length === 1 ? 'arma' : 'armas'}`}
          summary={`${unlocked}/${forgeable} con forja${chosen ? ` · ${chosen} en borrador` : ''}`}
          expanded={expanded.has(category) || Boolean(search)} onToggle={() => toggleGroup(category)}>
          {selectable.length > 1 && <div className="accordion-tools">
            <CheckAll checked={checked === selectable.length}
              indeterminate={checked > 0 && checked < selectable.length}
              label={`Seleccionar forjables de ${category}`}
              onChange={(enabled) => update(setItems(
                  'weaponForgeUnlock',
                  selectable.filter(({ id }) => enabled !== selected.has(id)).map(({ id }) => id),
                  enabled,
                  draft,
                  eligible,
                ))} />
          </div>}
          <div className="lock-options">
            {visible.map((item) => {
              const isChecked = selected.has(item.id)
              const canSelect = pending.has(item.id)
              return <label className={`lock-option ${isChecked ? 'selected' : ''}`} key={item.id}>
                <input type="checkbox" checked={isChecked} disabled={!canSelect}
                  aria-label={`Desbloquear ${progressionName(item)}`}
                  onChange={() => update(toggleItem('weaponForgeUnlock', item.id, draft, eligible))} />
                <span>
                  {progressionName(item)} <small className="skin-index">{item.id}</small>
                  <small className="detail-note">
                    {rarityLabel(item.level)} (nivel {item.level ?? '—'}) · {item.discovered ? 'descubierta' : 'sin descubrir'}
                  </small>
                  <small className="detail-note">
                    {progressionDetail(item, isChecked)}
                  </small>
                  {item.additional_requirements.length > 0 && <small className="detail-note">
                    Requisitos adicionales: {item.additional_requirements.join(', ')}
                  </small>}
                </span>
                <small className={`unlock-status${item.forge_unlock_ready ? ' complete' : ''}`}>
                  {item.forge_unlock_ready && <CircleCheck size={14} aria-hidden="true" />}
                  {forgeStateLabel(item)}
                  {item.forge_unlock_status === 'pending_research' && item.recommended_obtains !== null
                    ? ` · objetivo ${amountFormat.format(item.recommended_obtains)}` : ''}
                  {item.in_forge_queue ? ' · en cola' : ''}
                </small>
              </label>
            })}
          </div>
        </AccordionGroup>
      })}
    </div>}
    {!groups.length && <p className="detail-note">Sin resultados con este filtro.</p>}
    <details className="review-fields">
      <summary>Detalles técnicos de forja</summary>
      <p className="detail-note">
        Se eleva cada arma seleccionada al umbral de su nivel. Los objetivos de fusión usan ese mismo
        umbral como proxy provisional; si el nivel falta, se usa {amountFormat.format(8)} como fallback.
        Nunca se aplica un valor inferior al contador actual. Los contadores ya superiores se conservan
        y la cola de forja no se modifica.
      </p>
      <p className="detail-note">
        {amountFormat.format(snapshot?.forge_unlock_ready_count ?? 0)} {snapshot?.forge_unlock_ready_count === 1 ? 'arma' : 'armas'} con forja desbloqueada · {' '}
        {amountFormat.format(snapshot?.pending_requirements_count ?? 0)} {snapshot?.pending_requirements_count === 1 ? 'requisito sin umbral' : 'requisitos sin umbral'} determinado
        {' · '}{amountFormat.format(provisional)} umbrales de fusión provisionales.
      </p>
    </details>
  </div>
}

export function WeaponProgressionEditor({ save, draft, update }: EditorProps) {
  const [mode, setMode] = useState<WeaponMode>('discover')
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('pending')
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())
  const snapshot = save.weapon_progression
  const items = snapshot?.items ?? []
  const eligible = eligibility(save)
  const pending = new Set(eligible.weaponProgression)
  const selected = new Set(
    eligible.weaponProgression.filter((id) => isSelected('weaponProgression', id, draft, eligible)),
  )
  const search = query.trim().toLowerCase()
  const grouped = new Map<string, LabWeaponProgressionItem[]>()
  for (const item of items) {
    const group = item.subcategory || 'Otras'
    const rows = grouped.get(group)
    if (rows) rows.push(item)
    else grouped.set(group, [item])
  }
  const groups = Array.from(grouped, ([category, options]) => {
    const visible = options.filter((item) => {
      const matches = !search || progressionName(item).toLowerCase().includes(search)
        || item.id.toLowerCase().includes(search) || category.toLowerCase().includes(search)
      const state = filter === 'all' || (filter === 'pending' ? !item.discovered : item.discovered)
      return matches && state
    })
    return { category, options, visible }
  }).filter(({ visible }) => visible.length)

  const toggleGroup = (category: string) => setExpanded((previous) => {
    const next = new Set(previous)
    if (next.has(category)) next.delete(category)
    else next.add(category)
    return next
  })

  if (snapshot?.available === false) {
    return <div className="detail-editor">
      <Notice tone="warning">
        No se pudo leer el progreso de armas de esta copia: {snapshot.error || 'estructura no reconocida'}.
      </Notice>
    </div>
  }

  return <section className="detail-editor progression-editor" data-testid="weapon-progression-editor"
    aria-labelledby="weapon-progression-title">
    <div className="detail-subhead">
      <div>
        <h3 className="detail-subtitle" id="weapon-progression-title">Descubrimiento y forja</h3>
        <p className="detail-note">
          {mode === 'forge' ? <>
            {amountFormat.format(snapshot?.forge_unlock_ready_count ?? 0)} de {amountFormat.format(snapshot?.forgeable_total ?? 0)} armas forjables
            con forja desbloqueada · {amountFormat.format(
              Math.max(0, (snapshot?.forgeable_total ?? 0) - (snapshot?.forge_unlock_ready_count ?? 0)),
            )} {(snapshot?.forgeable_total ?? 0) - (snapshot?.forge_unlock_ready_count ?? 0) === 1
              ? 'pendiente' : 'pendientes'} de contador.
          </> : <>
            {amountFormat.format(snapshot?.discovered_count ?? 0)} de {amountFormat.format(snapshot?.total_weapons ?? 0)} armas
            descubiertas · {amountFormat.format(snapshot?.forge_unlock_ready_count ?? snapshot?.forge_ready_count ?? 0)} con forja desbloqueada.
          </>}
        </p>
      </div>
    </div>
    <div className="weapon-mode-tabs" role="tablist" aria-label="Acción sobre armas">
      <button type="button" role="tab" aria-selected={mode === 'discover'}
        data-testid="weapon-progression-tab-discover" className={mode === 'discover' ? 'active' : ''}
        onClick={() => setMode('discover')}>Descubrir armas</button>
      <button type="button" role="tab" aria-selected={mode === 'forge'}
        data-testid="weapon-progression-tab-forge" className={mode === 'forge' ? 'active' : ''}
        onClick={() => setMode('forge')}>Desbloquear para forja</button>
    </div>
    {mode === 'discover' ? <>
      <Notice tone="warning">
        <strong>Experimental (E2).</strong> Eleva contadores en cero o ausentes de <code>statisticData.object2ObtainTime</code> a 1;
        nunca reduce valores ni establece máximos. La cola <code>itemData.forgeWeapons</code> es de solo lectura y no se usa como
        desbloqueo permanente. La relación entre el contador y la forja debe validarse en el dispositivo.
      </Notice>
      <Toolbar save={save} group="weaponProgression" draft={draft} update={update} />
      {items.length ? <>
        <FilterControls query={query} setQuery={setQuery} filter={filter} setFilter={setFilter}
          searchLabel="Buscar armas" searchPlaceholder="Buscar arma o tipo"
          allLabel="Todas las armas" doneLabel="Descubiertas" />
        {groups.length > 0 && <div className="lock-groups">
          {groups.map(({ category, options, visible }) => {
            const selectable = visible.filter(({ id }) => pending.has(id))
            const checked = selectable.filter(({ id }) => selected.has(id)).length
            const discovered = options.filter((item) => item.discovered).length
            const chosen = options.filter((item) => selected.has(item.id)).length
            return <AccordionGroup key={category} title={category}
              testId={`weapon-progression-group-${category}`}
              meta={`${options.length} ${options.length === 1 ? 'arma' : 'armas'}`}
              summary={`${discovered}/${options.length} descubiertas${chosen ? ` · ${chosen} en borrador` : ''}`}
              expanded={expanded.has(category) || Boolean(search)} onToggle={() => toggleGroup(category)}>
              {selectable.length > 1 && <div className="accordion-tools">
                <CheckAll checked={checked === selectable.length}
                  indeterminate={checked > 0 && checked < selectable.length}
                  label={`Seleccionar ${category}`}
                  onChange={(enabled) => update(setItems(
                    'weaponProgression',
                    selectable.filter(({ id }) => enabled !== selected.has(id)).map(({ id }) => id),
                    enabled,
                    draft,
                    eligible,
                  ))} />
              </div>}
              <div className="lock-options">
                {visible.map((item) => {
                  const isChecked = selected.has(item.id)
                  return <label className={`lock-option ${isChecked ? 'selected' : ''}`} key={item.id}>
                    <input type="checkbox" checked={isChecked} disabled={!pending.has(item.id)}
                      aria-label={`Descubrir ${progressionName(item)}`}
                      onChange={() => update(toggleItem('weaponProgression', item.id, draft, eligible))} />
                    <span>
                      {progressionName(item)} <small className="skin-index">{item.id}</small>
                      <small className="detail-note">
                        {rarityLabel(item.level)} (nivel {item.level ?? '—'}) · Actual: {item.discovered ? amountFormat.format(item.count ?? 0) : 'sin registrar'}
                        {' → '}Propuesto: {amountFormat.format(
                          !item.discovered || isChecked ? item.proposed_count : item.count ?? item.proposed_count,
                        )}
                      </small>
                    </span>
                    <small className={`unlock-status${item.forge_ready ? ' complete' : ''}`}>
                      {item.forge_ready && <CircleCheck size={14} aria-hidden="true" />}
                      {forgeLabel(item)}{item.in_forge_queue ? ' · en cola' : ''}
                    </small>
                  </label>
                })}
              </div>
            </AccordionGroup>
          })}
        </div>}
        {!groups.length && <p className="detail-note">Sin resultados con este filtro.</p>}
        <details className="review-fields">
          <summary>Detalles técnicos</summary>
          <p className="detail-note">
            {amountFormat.format(snapshot?.forgeable_total ?? 0)} armas forjables en el catálogo · {' '}
            {amountFormat.format(snapshot?.unknown_counter_count ?? 0)} contadores ajenos o desconocidos preservados.
            {snapshot?.unknown_weapon_ids?.length
              ? ` Identificadores de arma no catalogados conservados: ${snapshot.unknown_weapon_ids.join(', ')}.`
              : ''}
          </p>
          <p className="detail-note">
            Cola de forja actual (solo lectura): {(snapshot?.forge_queue ?? []).join(', ') || 'vacía'}.
          </p>
        </details>
      </> : <p className="detail-note">La copia no contiene un catálogo legible de armas.</p>}
    </> : <>
      <Notice tone="warning">
        <strong>Experimental (E2).</strong> Eleva el contador de cada arma forjable al umbral individual requerido
        (2/3/4/6/6/8 según nivel; excepciones y fusiones marcadas aparte). Nunca reduce contadores, no modifica
        <code> itemData.forgeWeapons</code> ni estadísticas ajenas. Los requisitos aún no confirmados se muestran como pendientes.
      </Notice>
      <ForgeUnlockPanel save={save} draft={draft} update={update} />
    </>}
  </section>
}

function skinName(item: LabWeaponSkinItem) {
  return item.name_es || item.name_en || item.id
}

function weaponName(item: LabWeaponSkinItem) {
  return item.weapon_name_es || item.weapon_name_en || item.weapon_id
}

export function WeaponSkinsEditor({ save, draft, update }: EditorProps) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('pending')
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())
  const snapshot = save.weapon_skins
  const items = snapshot?.items ?? []
  const eligible = eligibility(save)
  const pending = new Set(eligible.weaponSkins)
  const selected = new Set(eligible.weaponSkins.filter((id) => isSelected('weaponSkins', id, draft, eligible)))
  const search = query.trim().toLowerCase()
  const grouped = new Map<string, LabWeaponSkinItem[]>()
  for (const item of items) {
    const group = grouped.get(item.weapon_id)
    if (group) group.push(item)
    else grouped.set(item.weapon_id, [item])
  }
  const groups = Array.from(grouped, ([weaponId, options]) => {
    const visible = options.filter((item) => {
      const matches = !search || skinName(item).toLowerCase().includes(search)
        || weaponName(item).toLowerCase().includes(search) || item.id.includes(search)
      const state = filter === 'all' || (filter === 'pending' ? !item.unlocked : item.unlocked)
      return matches && state
    })
    return { weaponId, options, visible }
  }).filter(({ visible }) => visible.length)

  const toggleGroup = (weaponId: string) => setExpanded((previous) => {
    const next = new Set(previous)
    if (next.has(weaponId)) next.delete(weaponId)
    else next.add(weaponId)
    return next
  })

  if (snapshot?.available === false) {
    return <div className="detail-editor">
      <Notice tone="warning">No se pudieron leer las skins de arma de esta copia: {snapshot.error || 'estructura no reconocida'}.</Notice>
    </div>
  }

  return <div className="detail-editor" data-testid="weapon-skins-editor">
    <Notice>
      <strong>Desbloqueo validado en Android físico (E3) e iOS (E4).</strong> Añade skins a <code>UnlockedSkins</code> de cada arma.
      La skin activa se puede cambiar de forma experimental (E2): se escribe <code>CurrentSkinIndex</code> con el índice
      del catálogo o 0 para la predeterminada. No cambia el nivel del arma. Crear el registro de un arma no la desbloquea:
      el arma base puede seguir bloqueada hasta desbloquear su descubrimiento.
    </Notice>
    <Toolbar save={save} group="weaponSkins" draft={draft} update={update} />
    {items.length ? <>
      <FilterControls query={query} setQuery={setQuery} filter={filter} setFilter={setFilter} searchLabel="Buscar skins de arma" />
      {groups.length > 0 && <div className="lock-groups">
        {groups.map(({ weaponId, options, visible }) => {
          const selectable = visible.filter(({ id }) => pending.has(id))
          const checked = selectable.filter(({ id }) => selected.has(id)).length
          const unlocked = options.filter((item) => item.unlocked).length
          const chosen = options.filter((item) => selected.has(item.id)).length
          const title = weaponName(options[0])
          const currentIndex = options.find((item) => item.current_skin_index !== null)?.current_skin_index ?? null
          const hasRecord = currentIndex !== null
          const currentSkin = options.find((item) => item.skin_index === currentIndex)
          const hasDraftEquip = Object.prototype.hasOwnProperty.call(draft.weaponSkinEquip, weaponId)
          const equipValue = hasDraftEquip
            ? draft.weaponSkinEquip[weaponId] ?? ''
            : currentIndex === 0 ? '' : currentSkin?.id ?? ''
          return <AccordionGroup key={weaponId} title={title}
            testId={`weapon-skin-group-${weaponId}`}
            meta={`${options.length} ${options.length === 1 ? 'skin' : 'skins'}`}
            summary={`${unlocked}/${options.length} desbloqueadas${chosen ? ` · ${chosen} en borrador` : ''}`}
            expanded={expanded.has(weaponId) || Boolean(search)} onToggle={() => toggleGroup(weaponId)}>
            {hasRecord && <div className="detail-filters">
              <span className="detail-note">Skin activa</span>
              <select aria-label={`Skin activa de ${title}`} value={equipValue}
                onChange={(event) => update(setWeaponSkinEquip(
                  weaponId, event.target.value === '' ? null : event.target.value, draft,
                ))}>
                <option value="">Predeterminada (sin skin)</option>
                {options.filter((item) => item.unlocked || selected.has(item.id)
                  || item.equipped || item.id === equipValue).map((item) => (
                  <option key={item.id} value={item.id}>{skinName(item)} · #{item.skin_index}</option>
                ))}
              </select>
            </div>}
            {selectable.length > 1 && <div className="accordion-tools">
              <CheckAll checked={checked === selectable.length}
                indeterminate={checked > 0 && checked < selectable.length}
                label={`Seleccionar ${title}`}
                onChange={(enabled) => update(setItems(
                  'weaponSkins',
                  selectable.filter(({ id }) => enabled !== selected.has(id)).map(({ id }) => id),
                  enabled,
                  draft,
                  eligible,
                ))} />
            </div>}
            <div className="lock-options">
              {visible.map((item) => {
                const isChecked = selected.has(item.id)
                return <label className={`lock-option ${isChecked ? 'selected' : ''}`} key={item.id}>
                  <input type="checkbox" checked={isChecked} disabled={!pending.has(item.id)}
                    aria-label={`${skinName(item)} de ${title}`}
                    onChange={() => update(toggleItem('weaponSkins', item.id, draft, eligible))} />
                  <span>{skinName(item)} <small className="skin-index">#{item.skin_index}</small></span>
                  {item.equipped
                    ? <small className="unlock-status complete"><CircleCheck size={14} aria-hidden="true" />En uso</small>
                    : item.unlocked
                      ? <small className="unlock-status complete"><CircleCheck size={14} aria-hidden="true" />Disponible</small>
                      : <small className="unlock-status">Bloqueada</small>}
                </label>
              })}
            </div>
          </AccordionGroup>
        })}
      </div>}
      {!groups.length && <p className="detail-note">Sin resultados con este filtro.</p>}
      <details className="review-fields">
        <summary>Detalles técnicos</summary>
        <p className="detail-note">
          {amountFormat.format(snapshot?.weapons_with_data ?? 0)} armas con registro · {' '}
          {amountFormat.format(snapshot?.unknown_weapon_ids?.length ?? 0)} armas desconocidas · {' '}
          {amountFormat.format(snapshot?.unknown_skin_ids?.length ?? 0)} skins desconocidas preservadas.
          La skin activa se escribe en <code>CurrentSkinIndex</code> solo si el arma ya tiene registro de evolución y la skin está desbloqueada. Los índices observados son 0 para la predeterminada y el índice del catálogo para una skin.
        </p>
      </details>
    </> : <p className="detail-note">La copia no contiene un catálogo legible de skins de arma.</p>}
  </div>
}

function effectName(item: LabKillEffectItem | undefined, effectId: number) {
  return item ? item.name_es || item.name_en || `Efecto ${effectId}` : `Efecto ${effectId}`
}

export function KillEffectsEditor({ save, draft, update }: EditorProps) {
  const [filter, setFilter] = useState<Filter>('pending')
  const snapshot = save.kill_effects
  const items = snapshot?.items ?? []
  const eligible = eligibility(save)
  const pending = new Set(eligible.killEffects)
  const selected = new Set(eligible.killEffects.filter((id) => isSelected('killEffects', id, draft, eligible)))
  const visible = items.filter((item) => {
    const state = filter === 'all' || (filter === 'pending' ? !item.unlocked : item.unlocked)
    return state
  })
  const byId = new Map(items.map((item) => [item.id, item]))
  const equipped = snapshot?.equipped ?? []
  const unknown = snapshot?.unknown_unlocked_ids ?? []

  if (snapshot?.available === false) {
    return <div className="detail-editor">
      <Notice tone="warning">No se pudieron leer los efectos de eliminación de esta copia: {snapshot.error || 'estructura no reconocida'}.</Notice>
    </div>
  }

  return <div className="detail-editor" data-testid="kill-effects-editor">
    <Notice>
      <strong>Validado en Android físico (E3).</strong> Añade IDs evidenciados a <code>miscData.unlockedKillEffectIds</code>.
      El efecto activo por escena es de solo lectura: su significado todavía no está confirmado.
    </Notice>
    <Toolbar save={save} group="killEffects" draft={draft} update={update} />
    {(equipped.length > 0 || unknown.length > 0) && <div className="kill-effect-reference">
      {equipped.length > 0 && <p className="detail-note">
        Efecto activo guardado: {equipped.map(({ scene, effect_id }) =>
          `escena ${scene} → ${effectName(byId.get(effect_id), effect_id)}`).join(' · ')}. Solo lectura.
      </p>}
      {unknown.length > 0 && <p className="detail-note">
        IDs observados no catalogados (se conservan, no se ofrecen): {unknown.join(', ')}.
      </p>}
    </div>}
    {items.length ? <>
      <FilterControls query="" setQuery={() => undefined} filter={filter} setFilter={setFilter}
        allLabel="Todos" doneLabel="Desbloqueados" />
      <div className="lock-group lock-options kill-effect-list">
        {visible.map((item) => {
          const isChecked = selected.has(String(item.id))
          return <label className={`lock-option ${isChecked ? 'selected' : ''}`} key={item.id}>
            <input type="checkbox" checked={isChecked} disabled={!pending.has(String(item.id))}
              aria-label={effectName(item, item.id)}
              onChange={() => update(toggleItem('killEffects', String(item.id), draft, eligible))} />
            <span>{effectName(item, item.id)} <small className="skin-index">ID {item.id}</small></span>
            {item.unlocked
              ? <small className="unlock-status complete"><CircleCheck size={14} aria-hidden="true" />Disponible</small>
              : <small className="unlock-status">Bloqueado</small>}
          </label>
        })}
      </div>
      {!visible.length && <p className="detail-note">Sin resultados con este filtro.</p>}
      <p className="detail-note">
        {amountFormat.format(snapshot?.unlocked_count ?? 0)} de {amountFormat.format(snapshot?.total_effects ?? 0)} efectos evidenciados.
        {filter === 'pending' && !eligible.killEffects.length ? ' No hay efectos pendientes.' : ''}
      </p>
      <details className="review-fields">
        <summary>Alcance y evidencias</summary>
        <p className="detail-note">
          Catálogo limitado a IDs 0–8 con recursos o localización. Las escenas guardadas usan claves numéricas cuyo
          significado (por ejemplo PvE/PvP) aún no está confirmado. No se modifican animaciones de ataque, impactos ni
          partículas de habilidades.
        </p>
      </details>
    </> : <p className="detail-note">La copia no contiene un catálogo legible de efectos de eliminación.</p>}
  </div>
}