import {
  Apple, Battery, Coins, CreditCard, Fish, Flag, Gem, KeyRound, Package, PawPrint, Shirt, Sprout,
  Star, Trophy, UsersRound, Waves, type LucideIcon,
} from 'lucide-react'
import type { LabAdvanced, NativeSaveSummary, SaveResourceGroup } from './api'
import { scalarQuantity } from './draft'

const amountFormat = new Intl.NumberFormat('es-MX')

export type StatCategory = 'Recursos' | 'Colección' | 'Inventario' | 'Progreso'

export type StatEvidence = {
  level: 'E2' | 'E3' | 'E4'
  note: string
  experimental: boolean
}

export type StatValue =
  | { kind: 'count'; value: number }
  | { kind: 'ratio'; value: number; total: number; note?: string }
  | { kind: 'level'; value: number; max: number | null; note?: string }
  | { kind: 'boolean'; value: boolean; trueLabel: string; falseLabel: string }
  | { kind: 'status'; value: string; tone?: 'default' | 'warning' }
  | { kind: 'inventory'; types: number; units: number; note?: string }
  | { kind: 'unavailable'; reason: string }
  | { kind: 'error'; message: string }

export type StatMetric = {
  id: string
  label: string
  icon: LucideIcon
  category: StatCategory
  priority: number
  evidence: StatEvidence
  extract: (save: NativeSaveSummary) => StatValue
}

const confirmed = (level: 'E2' | 'E3' | 'E4', note: string): StatEvidence => ({
  level, note, experimental: false,
})
const experimental = (level: 'E2' | 'E3', note: string): StatEvidence => ({
  level, note, experimental: true,
})

function unavailable(reason: string): StatValue {
  return { kind: 'unavailable', reason }
}

function isQuantity(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function countOf(value: unknown, reason: string): StatValue {
  return isQuantity(value) ? { kind: 'count', value } : unavailable(reason)
}

function ratioOf(value: unknown, total: unknown, reason: string, note?: string): StatValue {
  if (!isQuantity(value) || !isQuantity(total) || total <= 0) return unavailable(reason)
  return { kind: 'ratio', value, total, note }
}

function group(save: NativeSaveSummary, id: string): SaveResourceGroup | undefined {
  return save.report?.resources.groups.find((row) => row.id === id)
}

function inventory(rows: Array<{ count: number | null; owned: boolean }>, reason: string): StatValue {
  const owned = rows.filter((row) => row.owned)
  const known = owned.filter((row): row is { count: number; owned: boolean } => isQuantity(row.count))
  if (!owned.length || !known.length) return unavailable(reason)
  return {
    kind: 'inventory',
    types: known.length,
    units: known.reduce((total, row) => total + row.count, 0),
    note: owned.length > known.length ? 'Algunas cantidades no son legibles y no se sumaron.' : undefined,
  }
}

function advancedOf(save: NativeSaveSummary): LabAdvanced | null {
  if (!save.advanced || save.advanced.available === false) return null
  return save.advanced
}

function advancedFailure(save: NativeSaveSummary, reason: string): StatValue {
  const message = save.advanced?.available === false ? save.advanced.error : null
  return message ? { kind: 'error', message } : unavailable(reason)
}

function characterStat(save: NativeSaveSummary): StatValue {
  const report = save.report?.characters
  if (!report?.catalog.available) return unavailable('Catálogo de personajes no disponible')
  const { characters, unlocked } = report.counts
  if (!isQuantity(characters) || characters <= 0) return unavailable('Catálogo de personajes vacío')
  const observed = report.items.filter(({ unlocked: value }) => typeof value === 'boolean')
  if (!isQuantity(unlocked)) return unavailable('No se pudo leer el número de personajes')
  // Una partida sin observaciones no se interpreta como cero desbloqueados.
  if (unlocked === 0 && observed.length < characters && !observed.some((row) => row.unlocked === true)) {
    return unavailable('La partida no distingue personajes bloqueados de datos ausentes')
  }
  return { kind: 'ratio', value: unlocked, total: characters }
}

function petsStat(save: NativeSaveSummary): StatValue {
  const advanced = advancedOf(save)
  if (!advanced) return unavailable('Datos avanzados no disponibles')
  const observed = advanced.pets.filter(({ unlocked }) => typeof unlocked === 'boolean')
  if (!observed.length) return unavailable('La partida no contiene datos de mascotas')
  return {
    kind: 'ratio',
    value: observed.filter(({ unlocked }) => unlocked === true).length,
    total: observed.length,
    note: observed.length < advanced.pets.length
      ? `${observed.length} de ${advanced.pets.length} mascotas con dato`
      : undefined,
  }
}

function battlePass(save: NativeSaveSummary) {
  const pass = advancedOf(save)?.battle_pass
  if (!pass) return null
  const record = pass.records.find(({ season_id }) => season_id === pass.selected_season_id)
    ?? pass.records[0]
  return record ? { pass, record } : null
}

function batteryStat(save: NativeSaveSummary): StatValue {
  const advanced = advancedOf(save)
  if (!advanced) return advancedFailure(save, 'Datos avanzados no disponibles')
  const battery = advanced.pet_food.find(({ id }) => id === 'material_battery')
  if (!battery) return unavailable('La partida no expone baterías')
  if (!battery.owned) {
    // Solo se puede afirmar que es cero si el mapa de materiales es legible.
    return advanced.materials.some(({ owned }) => owned)
      ? { kind: 'count', value: 0 }
      : unavailable('No se pudo leer el inventario de materiales')
  }
  return countOf(battery.count, 'La cantidad de baterías no es legible')
}

/**
 * Registro único de métricas de Partida.
 *
 * Para añadir una métrica nueva basta con registrar otra entrada aquí: las páginas
 * del carrusel se generan por prioridad en bloques de cuatro. La extracción debe
 * devolver `unavailable` cuando el dato no está presente y nunca inventar un cero.
 */
export const statMetrics: StatMetric[] = [{
  id: 'gems', label: 'Gemas', icon: Gem, category: 'Recursos', priority: 10,
  evidence: confirmed('E4', 'Saldo confirmado por el propietario en Android.'),
  extract: (save) => countOf(scalarQuantity(save, 'gems').original, 'No se pudo leer el saldo de gemas'),
}, {
  id: 'fish_chip', label: 'Fichas de pesca', icon: Fish, category: 'Recursos', priority: 20,
  evidence: confirmed('E4', 'Saldo de pesca confirmado por el propietario.'),
  extract: (save) => countOf(scalarQuantity(save, 'fishChip').original, 'No se pudo leer el saldo de fichas'),
}, {
  id: 'season_coin', label: 'Monedas de temporada', icon: Coins, category: 'Recursos', priority: 30,
  evidence: confirmed('E3', 'Moneda de temporada confirmada en el editor avanzado.'),
  extract: (save) => countOf(scalarQuantity(save, 'seasonCoin').original, 'La partida no expone monedas de temporada'),
}, {
  id: 'characters', label: 'Personajes desbloqueados', icon: UsersRound, category: 'Colección', priority: 40,
  evidence: confirmed('E3', 'Desbloqueo de personajes confirmado por el propietario.'),
  extract: characterStat,
}, {
  id: 'skills', label: 'Habilidades desbloqueadas', icon: Star, category: 'Colección', priority: 50,
  evidence: confirmed('E3', 'Habilidades confirmadas por el propietario.'),
  extract: (save) => {
    const summary = save.report?.characters.skills
    return ratioOf(summary?.unlocked, summary?.total, 'No se pudo leer el catálogo de habilidades')
  },
}, {
  id: 'skins', label: 'Skins desbloqueadas', icon: Shirt, category: 'Colección', priority: 60,
  evidence: confirmed('E3', 'Solo Value=1 se interpreta como skin desbloqueada.'),
  extract: (save) => {
    const summary = save.report?.characters.skins
    return ratioOf(summary?.unlocked, summary?.total, 'No se pudo leer el catálogo de skins')
  },
}, {
  id: 'pets', label: 'Mascotas desbloqueadas', icon: PawPrint, category: 'Colección', priority: 70,
  evidence: confirmed('E3', 'Desbloqueo de mascotas confirmado por el propietario.'),
  extract: petsStat,
}, {
  id: 'materials', label: 'Materiales', icon: Package, category: 'Inventario', priority: 80,
  evidence: confirmed('E3', 'Inventario de materiales confirmado; los valores ilegibles no se suman.'),
  extract: (save) => advancedOf(save)
    ? inventory(save.advanced?.materials ?? [], 'No hay cantidades de materiales legibles')
    : advancedFailure(save, 'Datos avanzados no disponibles'),
}, {
  id: 'pet_food', label: 'Alimentos de mascota', icon: Apple, category: 'Inventario', priority: 90,
  evidence: confirmed('E3', 'Alimentos comparten itemData.materials con el inventario.'),
  extract: (save) => advancedOf(save)
    ? inventory(save.advanced?.pet_food ?? [], 'No hay cantidades de alimento legibles')
    : advancedFailure(save, 'Datos avanzados no disponibles'),
}, {
  id: 'batteries', label: 'Baterías', icon: Battery, category: 'Inventario', priority: 100,
  evidence: confirmed('E3', 'Batería leída como material_battery; no se confunde con otros objetos.'),
  extract: batteryStat,
}, {
  id: 'fish_progress', label: 'Progreso de pesca', icon: Waves, category: 'Progreso', priority: 110,
  evidence: confirmed('E3', 'Contador acumulado de pesca confirmado en Android.'),
  extract: (save) => {
    if (isQuantity(save.cumulative_fish_count)) return { kind: 'count', value: save.cumulative_fish_count }
    const report = group(save, 'cumulative_fish_count')
    return countOf(report?.value, 'No se pudo leer el progreso acumulado de pesca')
  },
}, {
  id: 'battle_pass_level', label: 'Nivel del pase', icon: Trophy, category: 'Progreso', priority: 120,
  evidence: experimental('E2', 'El pase de batalla es experimental; el máximo solo se muestra si está en la partida.'),
  extract: (save) => {
    const current = battlePass(save)
    if (!current) return unavailable('La partida no contiene registros del pase')
    const { record } = current
    if (!isQuantity(record.cur_level)) return unavailable('El nivel del pase no es legible')
    return {
      kind: 'level', value: record.cur_level,
      max: isQuantity(record.max_level) ? record.max_level : null,
      note: record.season_id != null ? `Temporada ${record.season_id}` : undefined,
    }
  },
}, {
  id: 'battle_pass_status', label: 'Estado del pase', icon: Flag, category: 'Progreso', priority: 130,
  evidence: experimental('E2', 'La temporada activa es experimental y puede no estar presente.'),
  extract: (save) => {
    const current = battlePass(save)
    if (!current) return unavailable('La partida no contiene registros del pase')
    const { pass } = current
    if (pass.active_matches_selected === true) return { kind: 'status', value: 'Temporada activa' }
    if (pass.active_matches_selected === false) {
      return { kind: 'status', value: 'Temporada inactiva', tone: 'warning' }
    }
    return unavailable('No se pudo determinar la temporada activa')
  },
}, {
  id: 'reborn_card', label: 'Tarjeta de renacimiento', icon: CreditCard, category: 'Progreso', priority: 140,
  evidence: confirmed('E3', 'Estado booleano confirmado por el propietario.'),
  extract: (save) => {
    if (!advancedOf(save)) return advancedFailure(save, 'Datos avanzados no disponibles')
    const card = save.advanced?.reborn_card
    if (!card?.available || typeof card.value !== 'boolean') {
      return unavailable('La partida no expone la tarjeta de renacimiento')
    }
    return {
      kind: 'boolean', value: card.value,
      trueLabel: 'Obtenida', falseLabel: 'No obtenida',
    }
  },
}, {
  id: 'seeds', label: 'Semillas', icon: Sprout, category: 'Inventario', priority: 150,
  evidence: confirmed('E3', 'Semillas confirmadas; no se inventan totales de catálogo.'),
  extract: (save) => advancedOf(save)
    ? inventory(save.advanced?.seeds ?? [], 'No hay cantidades de semillas legibles')
    : advancedFailure(save, 'Datos avanzados no disponibles'),
}, {
  id: 'unlocked_items', label: 'Objetos desbloqueados', icon: KeyRound, category: 'Colección', priority: 160,
  evidence: confirmed('E2', 'Lista observada en itemData.itemUnlock; el total es su longitud real.'),
  extract: (save) => {
    const items = group(save, 'unlocked_items')
    if (!items || items.state !== 'present') return unavailable('La partida no expone objetos desbloqueados')
    return countOf(items.entries, 'No se pudo leer la lista de objetos desbloqueados')
  },
}]

export type StatDisplay = {
  primary: string
  detail?: string
  title: string
  tone: 'default' | 'muted' | 'warning'
  numeric: boolean
}

export function formatStat(value: StatValue): StatDisplay {
  switch (value.kind) {
    case 'count': {
      const primary = amountFormat.format(value.value)
      return { primary, title: primary, tone: 'default', numeric: true }
    }
    case 'ratio': {
      const primary = `${amountFormat.format(value.value)} / ${amountFormat.format(value.total)}`
      return { primary, detail: value.note, title: primary, tone: 'default', numeric: true }
    }
    case 'level': {
      const primary = value.max == null
        ? amountFormat.format(value.value)
        : `${amountFormat.format(value.value)} / ${amountFormat.format(value.max)}`
      return {
        primary, detail: value.note ?? (value.max == null ? 'Máximo no disponible' : undefined),
        title: primary, tone: 'default', numeric: true,
      }
    }
    case 'boolean':
      return {
        primary: value.value ? value.trueLabel : value.falseLabel,
        title: value.value ? value.trueLabel : value.falseLabel,
        tone: value.value ? 'default' : 'muted', numeric: false,
      }
    case 'status':
      return {
        primary: value.value, title: value.value,
        tone: value.tone ?? 'default', numeric: false,
      }
    case 'inventory': {
      const primary = amountFormat.format(value.units)
      const types = value.types === 1 ? '1 tipo' : `${amountFormat.format(value.types)} tipos`
      return {
        primary, detail: value.note ?? types, title: `${primary} · ${types}`,
        tone: 'default', numeric: true,
      }
    }
    case 'unavailable':
      return { primary: '—', detail: value.reason, title: value.reason, tone: 'muted', numeric: false }
    case 'error':
      return {
        primary: 'Error', detail: value.message, title: value.message,
        tone: 'warning', numeric: false,
      }
  }
}

export function readStat(metric: StatMetric, save: NativeSaveSummary): StatValue {
  try {
    return metric.extract(save)
  } catch {
    return { kind: 'error', message: 'No se pudo interpretar este dato de la partida' }
  }
}

export function statPages(): StatMetric[][] {
  const sorted = [...statMetrics].sort((left, right) => left.priority - right.priority)
  const pages: StatMetric[][] = []
  for (let index = 0; index < sorted.length; index += 4) pages.push(sorted.slice(index, index + 4))
  return pages
}

export function evidenceText(evidence: StatEvidence) {
  return `${evidence.experimental ? 'Experimental' : 'Confirmado'} · ${evidence.level} · ${evidence.note}`
}