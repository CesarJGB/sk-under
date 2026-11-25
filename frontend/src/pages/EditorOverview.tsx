import {
  ArrowLeft, BatteryCharging, Check, CircleCheck, CircleDot, Coins, Fish, Gem, Medal,
  PawPrint, Shirt, Sprout, Swords, Ticket, UserRound, Zap, Package, type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { NativeSaveSummary } from '../api'
import {
  advancedSnapshot, batteryId, clearSelection, eligibility, minimumRows, originalQuantity, parseQuantity,
  quickChecked, scalarQuantity, selectAll, selectedCount, setBulk, setQuick, unlockProgress,
  type BuiltPlan, type BulkKey, type Draft, type Eligibility, type QuantityKey,
} from '../draft'

export const amountFormat = new Intl.NumberFormat('es-MX')

export const categories = [
  { id: 'recursos', label: 'Recursos' },
  { id: 'personajes', label: 'Personajes' },
  { id: 'habilidades', label: 'Habilidades' },
  { id: 'skins', label: 'Skins' },
  { id: 'mascotas', label: 'Mascotas' },
  { id: 'materiales', label: 'Materiales' },
  { id: 'semillas', label: 'Semillas' },
  { id: 'temporada', label: 'Temporada' },
  { id: 'pase', label: 'Pase de batalla' },
] as const

export type CategoryId = typeof categories[number]['id']

export const resources = [
  { key: 'gems', label: 'Gemas', icon: Gem, field: 'gems' },
  { key: 'fishChip', label: 'Fichas de pesca', icon: Ticket, field: 'fish_chip' },
  { key: 'fishProgress', label: 'Recompensas de pesca', icon: Fish, field: 'fish_progress' },
  { key: 'seasonCoin', label: 'Monedas de temporada', icon: Coins, field: 'season_coin' },
] as const

const minimums = [
  { key: 'materialsMin', label: 'Materiales', icon: Package },
  { key: 'seedsMin', label: 'Semillas', icon: Sprout },
  { key: 'petFoodMin', label: 'Alimento de mascotas', icon: PawPrint },
  { key: 'batteryMin', label: 'Baterías', icon: BatteryCharging },
] as const

const unlocks: Array<{ key: BulkKey; label: string; control: string; icon: LucideIcon }> = [
  { key: 'characters', label: 'Personajes', control: 'Todos los personajes', icon: UserRound },
  { key: 'skills', label: 'Habilidades', control: 'Todas las habilidades', icon: Zap },
  { key: 'skins', label: 'Skins', control: 'Todas las skins', icon: Shirt },
  { key: 'pets', label: 'Mascotas', control: 'Todas las mascotas', icon: PawPrint },
  { key: 'petSkins', label: 'Skins de mascotas', control: 'Skins de mascotas', icon: Shirt },
]

export function EditorHeader({ accountLabel, platform, version, status, ready }: {
  accountLabel?: string
  platform?: string
  version?: string
  status: string
  ready?: boolean
}) {
  return <header className="editor-top">
    <Link to="/partida" className="editor-back" aria-label="Volver a Partida">
      <ArrowLeft size={20} aria-hidden="true" />
    </Link>
    <h1>Editor</h1>
    <div className="editor-context">
      {accountLabel && <strong title={accountLabel}>{accountLabel}</strong>}
      {(platform || version) && <span>{[platform, version].filter(Boolean).join(' · ')}</span>}
      <span className={`editor-load-state ${ready ? 'ready' : ''}`} role="status">
        {ready ? <CircleCheck size={13} aria-hidden="true" /> : <CircleDot size={13} aria-hidden="true" />}
        {status}
      </span>
    </div>
  </header>
}

export function CategoryIcon({ id }: { id: CategoryId }) {
  return <img className="category-icon" src={`${import.meta.env.BASE_URL}editor-icons/${id}.png`}
    width="40" height="40" alt="" />
}

export function formatOriginal(value: unknown) {
  const number = originalQuantity(value)
  return number === null ? 'Sin dato' : amountFormat.format(number)
}

export function UnlockStatus({ save, group, eligible, selected = 0 }: {
  save: NativeSaveSummary
  group: BulkKey
  eligible: Eligibility
  selected?: number
}) {
  const { unlocked, total, pending } = unlockProgress(save, group, eligible)
  if (!total) return <span className="unlock-status">No disponible</span>
  return <span className={`unlock-status ${pending === 0 ? 'complete' : ''}`}>
    {pending === 0 && <CircleCheck size={13} aria-hidden="true" />}
    <span>{amountFormat.format(unlocked)}/{amountFormat.format(total)} {group === 'characters' ? 'desbloqueados' : 'desbloqueadas'}</span>
    {pending === 0 ? <span>· Completo</span> : <span>· {amountFormat.format(pending)} {pending === 1 ? 'pendiente' : 'pendientes'}</span>}
    {selected > 0 && <span className="unlock-selected">· {amountFormat.format(selected)} en borrador</span>}
  </span>
}

function QuickRow({ label, control = label, icon: Icon, checked, mixed, editable = true, invalid, changed, description, value, onChange, onValue, minimum }: {
  label: string
  control?: string
  icon: LucideIcon
  checked: boolean
  mixed?: boolean
  editable?: boolean
  invalid?: boolean
  changed?: boolean
  description?: ReactNode
  value?: string
  onChange: (checked: boolean) => void
  onValue?: (value: string) => void
  minimum?: boolean
}) {
  return <div className={`quick-row ${changed ? 'changed' : ''}${onValue ? ' quantity' : ''}`}>
    <label className="quick-select">
      <input type="checkbox" checked={checked} disabled={!editable} aria-label={`Activar ${control}`}
        ref={(input) => { if (input) input.indeterminate = Boolean(mixed) }}
        onChange={(event) => onChange(event.target.checked)} />
      <Icon size={16} className="quick-icon" aria-hidden="true" />
      <span className="quick-label"><strong>{label}</strong>{description}</span>
    </label>
    {onValue && <input className="quick-value" inputMode="numeric" aria-label={label}
      value={checked ? value : ''} placeholder={editable ? minimum ? 'Mínimo' : 'Nueva' : '—'}
      disabled={!editable || !checked} aria-invalid={invalid || undefined}
      onChange={(event) => onValue(event.target.value)} />}
  </div>
}

function minimumDescription(save: NativeSaveSummary, key: typeof minimums[number]['key']) {
  const rows = minimumRows(save, key)
  const eligible = rows.filter((row) => row.editable && row.owned && originalQuantity(row.count) !== null)
  const observed = key === 'batteryMin' ? rows : eligible
  const values = new Set(observed.map((row) => originalQuantity(row.count)))
  if (!values.size || values.has(null)) return { text: 'No disponible', editable: false }
  return {
    text: values.size > 1 ? 'Cantidades distintas' : `Actual ${formatOriginal(values.values().next().value)}`,
    editable: eligible.length > 0,
  }
}

export function QuickEdit({ save, draft, built, update, invalid }: {
  save: NativeSaveSummary
  draft: Draft
  built: BuiltPlan
  update: (next: Draft) => void
  invalid: Set<QuantityKey>
}) {
  const eligible = eligibility(save)
  const advanced = advancedSnapshot(save)
  const pass = advanced?.battle_pass
  const battlePass = pass?.records?.find((record) => record.season_id === draft.battlePass.seasonId)
    ?? pass?.records?.find((record) => record.season_id === pass.selected_season_id) ?? pass?.records?.[0]
  const reborn = advanced?.reborn_card
  const quantityRow = (key: QuantityKey, label: string, icon: LucideIcon, text: string, editable: boolean, changed: boolean, minimum = false) =>
    <QuickRow key={key} label={label} icon={icon} checked={draft.quick[key].enabled}
      value={draft.quick[key].value} editable={editable} invalid={invalid.has(key)} changed={changed} minimum={minimum}
      description={<small>{text}</small>}
      onChange={(enabled) => update(setQuick(key, { enabled }, draft))}
      onValue={(value) => update(setQuick(key, { value }, draft))} />
  const allPendingSelected = unlocks.every(({ key }) => quickChecked(key, draft, eligible) === 'all' || eligible[key].length === 0)

  return <div className="quick-edit" data-testid="quick-edit">
    <section className="quick-group" aria-label="Recursos">
      <h2>Recursos</h2>
      {resources.map(({ key, label, icon, field }) => {
        const source = scalarQuantity(save, key)
        const planned = field === 'season_coin' ? built.plan.advanced?.season_coin : built.plan[field]
        return quantityRow(key, label, icon, source.original === null ? 'No disponible' : `Actual ${formatOriginal(source.original)}`,
          source.editable, planned != null)
      })}
    </section>
    <section className="quick-group" aria-label="Cantidades mínimas">
      <h2>Cantidades mínimas</h2>
      {minimums.map(({ key, label, icon }) => {
        const { text, editable } = minimumDescription(save, key)
        const changes = key === 'seedsMin' ? built.plan.advanced?.seeds : built.plan.advanced?.materials
        const value = parseQuantity(draft.quick[key].value)
        const changed = draft.quick[key].enabled && value !== null && minimumRows(save, key).some((row) =>
          changes?.some((change) => change.id === row.id && change.value === value))
        return quantityRow(key, label, icon, text, editable, Boolean(changed), true)
      })}
    </section>
    <section className="quick-group" aria-label="Desbloqueos">
      <div className="quick-group-head">
        <h2>Desbloqueos</h2>
        <button type="button" className="button quiet" disabled={allPendingSelected} onClick={() =>
          update(unlocks.reduce((next, { key }) => eligible[key].length ? selectAll(key, next) : next, draft))}>
          <Check size={15} aria-hidden="true" />Seleccionar pendientes
        </button>
      </div>
      {unlocks.map(({ key, label, control, icon }) => {
        const state = quickChecked(key, draft, eligible)
        const selected = selectedCount(key, draft, eligible)
        return <QuickRow key={key} label={label} control={control} icon={icon} checked={state === 'all'} mixed={state === 'some'}
          editable={eligible[key].length > 0} changed={selected > 0}
          description={<UnlockStatus save={save} group={key} eligible={eligible} selected={selected} />}
          onChange={(checked) => update(checked ? selectAll(key, draft)
            : draft.bulk[key] ? setBulk(key, false, draft) : clearSelection(key, draft))} />
      })}
    </section>
    <section className="quick-group" aria-label="Beneficios">
      <h2>Beneficios</h2>
      <QuickRow label="Tarjeta de renacimiento permanente" icon={Swords} checked={draft.reborn}
        editable={Boolean(reborn?.available && reborn.value === false)} changed={Boolean(built.plan.advanced?.reborn_card)}
        description={reborn?.value === true ? <span className="unlock-status complete"><CircleCheck size={13} aria-hidden="true" />Activa</span>
          : <small>{reborn?.available ? 'Inactiva' : 'No disponible'}</small>}
        onChange={(checked) => update({ ...draft, reborn: checked })} />
      <QuickRow label="Pase de batalla al nivel máximo" icon={Medal}
        checked={Boolean(battlePass && draft.battlePass.enabled && draft.battlePass.seasonId === battlePass.season_id
          && parseQuantity(draft.battlePass.level) === battlePass.max_level)}
        editable={Boolean(battlePass?.editable && battlePass.max_level != null)}
        changed={built.plan.advanced?.battle_pass?.cur_level === battlePass?.max_level && battlePass?.max_level != null}
        description={<small>{battlePass?.cur_level == null ? 'No disponible' : `Nivel actual ${formatOriginal(battlePass.cur_level)}`}</small>}
        onChange={(checked) => {
          if (!battlePass) return
          update({
            ...draft,
            battlePass: {
              ...draft.battlePass, enabled: checked || draft.battlePass.exp !== '' || draft.battlePass.buy !== null,
              seasonId: battlePass.season_id, level: checked ? String(battlePass.max_level ?? '') : '',
            },
          })
        }} />
    </section>
  </div>
}

export function CategoryGrid({ built, onOpen }: { built: BuiltPlan; onOpen: (id: CategoryId) => void }) {
  const counts = built.counts.byCategory
  const resources = (counts.Gemas ?? 0) + (counts['Fichas de pesca'] ?? 0)
  const season = (counts['Monedas de temporada'] ?? 0) + (counts['Recompensas de pesca'] ?? 0)
  const food = built.plan.advanced?.materials?.filter(({ id }) => id === batteryId || id === 'material_grain').length ?? 0
  const pending: Record<CategoryId, number> = {
    recursos: resources + season,
    personajes: counts.Personajes ?? 0,
    habilidades: counts.Habilidades ?? 0,
    skins: counts.Skins ?? 0,
    mascotas: (counts.Mascotas ?? 0) + food,
    materiales: counts.Materiales ?? 0,
    semillas: counts.Semillas ?? 0,
    temporada: season + (counts['Tarjeta de renacimiento'] ?? 0),
    pase: counts['Pase de batalla'] ?? 0,
  }
  return <div className="category-grid" data-testid="category-grid">
    {categories.map(({ id, label }) => <button type="button" className="category-card" key={id} onClick={() => onOpen(id)}>
      <CategoryIcon id={id} />
      <span>{label}</span>
      {pending[id] > 0 && <strong><span className="sr-only">Cambios pendientes </span>{amountFormat.format(pending[id])}</strong>}
    </button>)}
  </div>
}
