import type {
  LabAdvanced, LabAdvancedPlan, LabSkillRef, LabSkinRef, LabUnifiedPlan, NativeSaveSummary, NativeSession,
  SaveCharacterReport,
} from './api'
import { pendingCharacterCodes, pendingSkillKeys, pendingSkinKeys, skillKey, skinKey } from './unlockSelections'

export type BulkKey =
  | 'characters' | 'skills' | 'skins' | 'pets' | 'petSkins'
  | 'heroLevels' | 'petAffinity' | 'blueprints' | 'blueprintObtain'
  | 'decorations' | 'decorationLevels'
export type QuantityKey =
  | 'gems' | 'fishChip' | 'fishProgress' | 'seasonCoin'
  | 'materialsMin' | 'seedsMin' | 'petFoodMin' | 'batteryMin'

export type Draft = {
  bulk: Record<BulkKey, boolean>
  manual: {
    characters: Record<string, true>
    skills: Record<string, true>
    skins: Record<string, true>
    pets: Record<string, true>
    petSkins: Record<string, true>
    heroLevels: Record<string, true>
    petAffinity: Record<string, true>
    blueprints: Record<string, true>
    blueprintObtain: Record<string, true>
    decorations: Record<string, true>
    decorationLevels: Record<string, true>
  }
  excluded: {
    characters: Record<string, true>
    skills: Record<string, true>
    skins: Record<string, true>
    pets: Record<string, true>
    petSkins: Record<string, true>
    heroLevels: Record<string, true>
    petAffinity: Record<string, true>
    blueprints: Record<string, true>
    blueprintObtain: Record<string, true>
    decorations: Record<string, true>
    decorationLevels: Record<string, true>
  }
  quick: Partial<Record<QuantityKey, string>>
  materialEdits: Record<string, string>
  seedEdits: Record<string, string>
  materialMinimums: Record<string, number>
  seedMinimums: Record<string, number>
  heroLevels: Record<string, string>
  petAffinity: Record<string, string>
  blueprintStatus: Record<string, 'Got' | 'Researched'>
  blueprintMode: 'Got' | 'Researched'
  decorationLevels: Record<string, string>
  reborn: boolean
  battlePass: { seasonId: number | null; level?: string; exp?: string; buy: boolean | null }
}

export type DraftCounts = {
  changes: number
  operations: number
  byCategory: Record<string, number>
}

const scalarKeys = ['gems', 'fishChip', 'fishProgress', 'seasonCoin'] as const
const minimumKeys = ['materialsMin', 'seedsMin', 'petFoodMin', 'batteryMin'] as const

export const MAX_QUANTITY = 2_147_483_647
export const protectedMaterial = 'material_fish'
export const batteryId = 'material_battery'

export function originalQuantity(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null
}

export function advancedSnapshot(save: NativeSaveSummary | null) {
  return save?.advanced?.available === false ? null : save?.advanced
}

export function scalarQuantity(save: NativeSaveSummary, key: typeof scalarKeys[number]) {
  const coin = advancedSnapshot(save)?.season_coin
  const stored = originalQuantity({
    gems: save.gems, fishChip: save.fish_chip, fishProgress: save.cumulative_fish_count, seasonCoin: coin?.value,
  }[key])
  const fish = save.report?.fish_chips
  const observed = key === 'fishChip' && fish?.balance_path === 'gameData.fishChip' && fish.balance_is_integer
    ? originalQuantity(fish.balance) : null
  return { original: stored ?? observed, editable: stored !== null && (key !== 'seasonCoin' || !!coin?.available) }
}

export function minimumRows(save: NativeSaveSummary, key: typeof minimumKeys[number]) {
  const advanced = advancedSnapshot(save)
  if (key === 'materialsMin') return (advanced?.materials ?? []).filter((row) => row.id !== protectedMaterial)
  if (key === 'seedsMin') return advanced?.seeds ?? []
  const food = advanced?.pet_food ?? []
  return key === 'batteryMin' ? food.filter((row) => row.id === batteryId) : food
}

export function minimumSource(rows: LabAdvanced['materials'] | LabAdvanced['pet_food']) {
  const counts = new Set<number>()
  for (const row of rows) {
    const count = originalQuantity(row.count)
    if (row.editable && row.owned && count !== null) counts.add(count)
  }
  return { original: counts.size === 1 ? (counts.values().next().value ?? null) : null, editable: counts.size > 0 }
}

function emptySet(): Record<string, true> {
  return {}
}

export function createEmptyDraft(): Draft {
  return {
    bulk: {
      characters: false, skills: false, skins: false, pets: false, petSkins: false,
      heroLevels: false, petAffinity: false, blueprints: false, blueprintObtain: false,
      decorations: false, decorationLevels: false,
    },
    manual: {
      characters: emptySet(), skills: emptySet(), skins: emptySet(), pets: emptySet(), petSkins: emptySet(),
      heroLevels: emptySet(), petAffinity: emptySet(), blueprints: emptySet(),
      blueprintObtain: emptySet(), decorations: emptySet(), decorationLevels: emptySet(),
    },
    excluded: {
      characters: emptySet(), skills: emptySet(), skins: emptySet(), pets: emptySet(), petSkins: emptySet(),
      heroLevels: emptySet(), petAffinity: emptySet(), blueprints: emptySet(),
      blueprintObtain: emptySet(), decorations: emptySet(), decorationLevels: emptySet(),
    },
    quick: {},
    materialEdits: {},
    seedEdits: {},
    materialMinimums: {},
    seedMinimums: {},
    heroLevels: {},
    petAffinity: {},
    blueprintStatus: {},
    blueprintMode: 'Researched',
    decorationLevels: {},
    reborn: false,
    battlePass: { seasonId: null, buy: null },
  }
}

export function draftKey(profile: string, sha: string) {
  return `${profile}:${sha}`
}

function parseQuantity(value: string): number | null {
  const trimmed = value.trim()
  if (!/^\d+$/.test(trimmed)) return null
  const number = Number(trimmed)
  return Number.isSafeInteger(number) && number <= MAX_QUANTITY ? number : null
}

export function quantityInput(original: number | null, edit: string | undefined, min = 0, max = MAX_QUANTITY) {
  const initial = String(original ?? '')
  const value = edit ?? initial
  if (value === initial) return { value, changed: false, invalid: false, requested: null }
  const parsed = parseQuantity(value)
  const changed = parsed === null || parsed !== original
  const invalid = changed && value !== '' && (parsed === null || parsed < min || parsed > max)
  return { value, changed, invalid, requested: changed && !invalid ? parsed : null }
}

function quickQuantities(save: NativeSaveSummary, draft: Draft, session: NativeSession) {
  function field(key: QuantityKey, source: { original: number | null; editable: boolean }, min?: number, max?: number) {
    return { ...source, ...quantityInput(source.original, source.editable ? draft.quick[key] : undefined, min, max) }
  }
  const coin = advancedSnapshot(save)?.season_coin
  const scalars = scalarKeys.map((key) => {
    const min = key === 'gems' ? session.min_gems : key === 'fishChip' ? session.min_fish_chip : key === 'seasonCoin' ? coin?.min : undefined
    const max = key === 'gems' ? session.max_gems : key === 'fishChip' ? session.max_fish_chip : key === 'seasonCoin' ? coin?.max : undefined
    return [key, field(key, scalarQuantity(save, key), min, max)] as const
  })
  const minimums = minimumKeys.map((key) => {
    const rows = minimumRows(save, key)
    const source = minimumSource(rows)
    const original = key === 'batteryMin' ? originalQuantity(rows[0]?.count) : source.original
    return [key, field(key, { ...source, original })] as const
  })
  return Object.fromEntries([...scalars, ...minimums]) as Record<QuantityKey, ReturnType<typeof field>>
}

export function minimumTarget(original: unknown, ...minimums: Array<number | null>): number | null {
  const current = originalQuantity(original)
  if (current === null) return null
  const target = Math.max(current, ...minimums.map((minimum) => minimum ?? current))
  return target > current ? target : null
}

function eligibleCharacters(characters: SaveCharacterReport | null | undefined): string[] {
  return characters ? pendingCharacterCodes(characters) : []
}

function eligibleSkills(characters: SaveCharacterReport | null | undefined): string[] {
  return characters ? pendingSkillKeys(characters) : []
}

function eligibleSkins(characters: SaveCharacterReport | null | undefined): string[] {
  return characters ? pendingSkinKeys(characters) : []
}

function eligiblePets(advanced: LabAdvanced | null | undefined): string[] {
  if (!advanced || advanced.available === false) return []
  return advanced.pets.filter((pet) => pet.editable && pet.present && pet.unlocked === false).map((pet) => pet.id)
}

function eligiblePetSkins(advanced: LabAdvanced | null | undefined): string[] {
  if (!advanced || advanced.available === false) return []
  return advanced.pet_skins
    .filter((skin) => skin.editable && skin.present && skin.unlocked === false)
    .map((skin) => skin.id)
}

export type Eligibility = Record<BulkKey, string[]>

export function eligibility(save: NativeSaveSummary | null): Eligibility {
  const report = save?.report?.characters
  const characters = report?.catalog?.available === false ? null : report
  const advanced = save?.advanced
  return {
    characters: eligibleCharacters(characters),
    skills: eligibleSkills(characters),
    skins: eligibleSkins(characters),
    pets: eligiblePets(advanced),
    petSkins: eligiblePetSkins(advanced),
    heroLevels: (advanced?.hero_levels?.entries ?? [])
      .filter((row) => row.editable && row.level !== null && row.level < (advanced?.hero_levels?.max ?? 0))
      .map((row) => row.id),
    petAffinity: (advanced?.pet_progression?.entries ?? [])
      .filter((row) => row.editable && row.intimacy !== null && row.max !== null && row.intimacy < row.max)
      .map((row) => row.id),
    blueprints: (advanced?.blueprints?.entries ?? [])
      .filter((row) => row.status !== 'Researched' && (row.status === 'Got' || row.creatable))
      .map((row) => row.id),
    blueprintObtain: (advanced?.blueprints?.entries ?? [])
      .filter((row) => row.creatable)
      .map((row) => row.id),
    decorations: (advanced?.decorations?.objects ?? [])
      .filter((row) => row.editable)
      .map((row) => row.id),
    decorationLevels: (advanced?.decorations?.levels ?? [])
      .filter((row) => row.editable && row.level !== null && row.level < row.max_observed)
      .map((row) => row.id),
  }
}

function effective(
  key: BulkKey,
  draft: Draft,
  eligible: Eligibility,
): Record<string, true> {
  const result: Record<string, true> = {}
  if (draft.bulk[key]) for (const item of eligible[key]) result[item] = true
  for (const item of Object.keys(draft.manual[key])) result[item] = true
  for (const item of Object.keys(draft.excluded[key])) delete result[item]
  return result
}

export function selectedCount(
  key: BulkKey,
  draft: Draft,
  eligible: Eligibility,
): number {
  return Object.keys(effective(key, draft, eligible)).length
}

export function isSelected(
  key: BulkKey,
  item: string,
  draft: Draft,
  eligible: Eligibility,
): boolean {
  return !draft.excluded[key][item] && Boolean(draft.manual[key][item] || (draft.bulk[key] && eligible[key].includes(item)))
}

export function toggleItem(
  key: BulkKey,
  item: string,
  draft: Draft,
  eligible: Eligibility,
): Draft {
  const selected = isSelected(key, item, draft, eligible)
  const manual = { ...draft.manual[key] }
  const excluded = { ...draft.excluded[key] }
  if (draft.bulk[key]) {
    if (selected) {
      delete manual[item]
      excluded[item] = true
    } else {
      delete excluded[item]
      if (!eligible[key].includes(item)) manual[item] = true
    }
  } else if (selected) {
    delete manual[item]
    delete excluded[item]
  } else {
    manual[item] = true
    delete excluded[item]
  }
  return { ...draft, manual: { ...draft.manual, [key]: manual }, excluded: { ...draft.excluded, [key]: excluded } }
}

export function setBulk(key: BulkKey, value: boolean, draft: Draft): Draft {
  return {
    ...draft,
    bulk: { ...draft.bulk, [key]: value },
    excluded: { ...draft.excluded, [key]: {} },
  }
}

export function selectAll(key: BulkKey, draft: Draft): Draft {
  return setBulk(key, true, draft)
}

export function clearSelection(key: BulkKey, draft: Draft): Draft {
  return setBulk(key, false, { ...draft, manual: { ...draft.manual, [key]: {} }, excluded: { ...draft.excluded, [key]: {} } })
}

export function setQuick(key: QuantityKey, value: string, draft: Draft): Draft {
  return { ...draft, quick: { ...draft.quick, [key]: value } }
}

export function setHeroLevel(id: string, value: string, draft: Draft): Draft {
  const next = { ...draft.heroLevels }
  if (value === '') delete next[id]
  else next[id] = value
  return { ...draft, heroLevels: next }
}

export function setPetAffinity(id: string, value: string, draft: Draft): Draft {
  const next = { ...draft.petAffinity }
  if (value === '') delete next[id]
  else next[id] = value
  return { ...draft, petAffinity: next }
}

export function setBlueprintStatus(id: string, status: 'Got' | 'Researched', draft: Draft): Draft {
  return { ...draft, blueprintStatus: { ...draft.blueprintStatus, [id]: status } }
}

export function setBlueprintMode(mode: 'Got' | 'Researched', draft: Draft): Draft {
  return { ...draft, blueprintMode: mode }
}

export function setDecorationLevel(id: string, value: string, draft: Draft): Draft {
  const next = { ...draft.decorationLevels }
  if (value === '') delete next[id]
  else next[id] = value
  return { ...draft, decorationLevels: next }
}

export function setEdit(
  kind: 'materials' | 'seeds' | 'petFood',
  id: string,
  value: string,
  original: number | null,
  draft: Draft,
): Draft {
  const field = kind === 'seeds' ? 'seedEdits' : 'materialEdits'
  const next = { ...draft[field] }
  if (value === '' && original === null) delete next[id]
  else next[id] = value
  return { ...draft, [field]: next }
}

export function applyItemMinimum(
  kind: 'materials' | 'seeds', rows: LabAdvanced['materials'], minimum: number, draft: Draft,
): Draft {
  const editKey = kind === 'materials' ? 'materialEdits' : 'seedEdits'
  const minimumKey = kind === 'materials' ? 'materialMinimums' : 'seedMinimums'
  const edits = { ...draft[editKey] }
  const minimums = { ...draft[minimumKey] }
  for (const row of rows) {
    const current = originalQuantity(row.count)
    if (!row.editable || !row.owned || current === null || (kind === 'materials' && row.id === protectedMaterial)) continue
    const target = minimumTarget(current, minimum, minimums[row.id] ?? null)
    if (target !== null) minimums[row.id] = target
    const manual = parseQuantity(edits[row.id] ?? '')
    if (manual !== null && manual < (target ?? current)) delete edits[row.id]
  }
  return { ...draft, [editKey]: edits, [minimumKey]: minimums }
}

function effectiveUnlockedSet(
  key: BulkKey,
  draft: Draft,
  eligible: Eligibility,
): string[] {
  return Object.keys(effective(key, draft, eligible))
}

export function effectiveCharacters(draft: Draft, save: NativeSaveSummary): string[] {
  return effectiveUnlockedSet('characters', draft, eligibility(save))
}

export function effectiveSkillRefs(draft: Draft, save: NativeSaveSummary): LabSkillRef[] {
  return effectiveUnlockedSet('skills', draft, eligibility(save)).map((key) => {
    const [code, index] = key.split(':')
    return { code, index: Number(index) }
  })
}

export function effectiveSkinRefs(draft: Draft, save: NativeSaveSummary): LabSkinRef[] {
  return effectiveUnlockedSet('skins', draft, eligibility(save)).map((key) => {
    const [code, index] = key.split(':')
    return { code, index: Number(index) }
  })
}

export function effectivePets(draft: Draft, save: NativeSaveSummary): string[] {
  return effectiveUnlockedSet('pets', draft, eligibility(save))
}

export function effectivePetSkins(draft: Draft, save: NativeSaveSummary): string[] {
  return effectiveUnlockedSet('petSkins', draft, eligibility(save))
}

function materialPlan(
  rows: LabAdvanced['materials'] | LabAdvanced['seeds'] | LabAdvanced['pet_food'],
  edits: Record<string, string>,
  minimum: number | null,
  itemMinimums: Record<string, number>,
): Array<{ id: string; value: number }> {
  const result: Array<{ id: string; value: number }> = []
  for (const row of rows) {
    if (!row.editable) continue
    const original = originalQuantity(row.count)
    const manual = parseQuantity(edits[row.id] ?? '')
    if (manual !== null && manual !== original) {
      if (original !== null || row.insertable) result.push({ id: row.id, value: manual })
      continue
    }
    const target = row.owned ? minimumTarget(original, minimum, itemMinimums[row.id] ?? null) : null
    if (target !== null) result.push({ id: row.id, value: target })
  }
  return result
}

export type BuiltPlan = {
  plan: LabUnifiedPlan
  counts: DraftCounts
  quantities: ReturnType<typeof quickQuantities>
}

export function battlePassRecord(advanced: LabAdvanced | null | undefined, seasonId: number | null) {
  const pass = advanced?.battle_pass
  const records = pass?.records ?? []
  return records.find((record) => record.season_id === seasonId)
    ?? records.find((record) => record.season_id === pass?.selected_season_id) ?? records[0]
}

export function buildDraftPlan(save: NativeSaveSummary, draft: Draft, session: NativeSession): BuiltPlan {
  const advanced = advancedSnapshot(save)
  const quantities = quickQuantities(save, draft, session)
  const counts: DraftCounts = { changes: 0, operations: 0, byCategory: {} }
  const plan: LabUnifiedPlan = {}
  const bump = (category: string, amount: number) => {
    if (amount <= 0) return
    counts.byCategory[category] = (counts.byCategory[category] ?? 0) + amount
    counts.changes += amount
    counts.operations += 1
  }
  const requested = (key: QuantityKey) => quantities[key].requested

  for (const [key, field, label] of [
    ['gems', 'gems', 'Gemas'],
    ['fishChip', 'fish_chip', 'Fichas de pesca'],
    ['fishProgress', 'fish_progress', 'Recompensas de pesca'],
  ] as const) {
    const value = requested(key)
    if (value === null) continue
    plan[field] = value
    bump(label, 1)
  }

  const characters = effectiveCharacters(draft, save)
  if (characters.length > 0) {
    plan.characters = characters
    bump('Personajes', characters.length)
  }
  const skills = effectiveSkillRefs(draft, save)
  if (skills.length > 0) {
    plan.skills = skills
    bump('Habilidades', skills.length)
  }
  const skins = effectiveSkinRefs(draft, save)
  if (skins.length > 0) {
    plan.skins = skins
    bump('Skins', skins.length)
  }

  const advancedPlan: LabAdvancedPlan = { materials: [], seeds: [] }
  const materials = materialPlan(minimumRows(save, 'materialsMin'), draft.materialEdits, requested('materialsMin'), draft.materialMinimums)
  const materialChanges = new Map(materials.map(({ id, value }) => [id, value]))
  for (const row of advanced?.pet_food ?? []) {
    if (!row.editable || row.id === protectedMaterial) continue
    const current = originalQuantity(row.count)
    const explicit = parseQuantity(draft.materialEdits[row.id] ?? '')
    if (explicit !== null && explicit !== current) {
      if (current !== null || row.insertable) materialChanges.set(row.id, explicit)
      continue
    }
    if (!row.owned) continue
    const value = minimumTarget(current, materialChanges.get(row.id) ?? null, requested('petFoodMin'),
      row.id === batteryId ? requested('batteryMin') : null)
    if (value !== null) materialChanges.set(row.id, value)
  }
  advancedPlan.materials = Array.from(materialChanges, ([id, value]) => ({ id, value }))
  bump('Materiales', advancedPlan.materials.length)

  advancedPlan.seeds = materialPlan(minimumRows(save, 'seedsMin'), draft.seedEdits, requested('seedsMin'), draft.seedMinimums)
  bump('Semillas', advancedPlan.seeds.length)

  const seasonCoin = requested('seasonCoin')
  if (seasonCoin !== null) {
    advancedPlan.season_coin = seasonCoin
    bump('Monedas de temporada', 1)
  }

  if (draft.reborn && advanced?.reborn_card.available && advanced.reborn_card.value === false) {
    advancedPlan.reborn_card = true
    bump('Tarjeta de renacimiento', 1)
  }

  const pets = [...new Set([...effectivePets(draft, save), ...effectivePetSkins(draft, save)])]
  if (pets.length > 0) {
    advancedPlan.pets = pets
    bump('Mascotas', pets.length)
  }

  const record = battlePassRecord(advanced, draft.battlePass.seasonId)
  if (record?.editable && record.season_id !== null) {
    const level = quantityInput(originalQuantity(record.cur_level), draft.battlePass.level).requested
    const exp = quantityInput(originalQuantity(record.cur_exp), draft.battlePass.exp).requested
    const next: NonNullable<LabAdvancedPlan['battle_pass']> = { season_id: record.season_id }
    let changes = 0
    if (level !== null) {
      next.cur_level = level
      changes += 1
    }
    if (exp !== null) {
      next.cur_exp = exp
      changes += 1
    }
    if (draft.battlePass.buy !== null && draft.battlePass.buy !== record.has_buy) {
      next.has_buy = draft.battlePass.buy
      changes += 1
    }
    if (changes > 0) {
      advancedPlan.battle_pass = next
      bump('Pase de batalla', changes)
    }
  }

  if (advancedPlan.materials?.length || advancedPlan.seeds?.length
    || advancedPlan.season_coin !== undefined || advancedPlan.reborn_card
    || advancedPlan.battle_pass || advancedPlan.pets?.length || advancedPlan.pet_food?.length) {
    plan.advanced = advancedPlan
  }

  const selected = eligibility(save)
  const heroMax = advanced?.hero_levels?.max ?? 0
  const heroPlan = new Map<string, number>()
  const selectedHeroes = new Set(effectiveUnlockedSet('heroLevels', draft, selected))
  for (const row of advanced?.hero_levels?.entries ?? []) {
    if (!row.editable || row.level === null) continue
    const explicit = parseQuantity(draft.heroLevels[row.id] ?? '')
    if (explicit !== null && explicit !== row.level && explicit >= row.level && explicit <= heroMax) {
      heroPlan.set(row.id, explicit)
    } else if (selectedHeroes.has(row.id) && row.level < heroMax) {
      heroPlan.set(row.id, heroMax)
    }
  }
  if (heroPlan.size > 0) {
    plan.hero_levels = Array.from(heroPlan, ([code, level]) => ({ code, level }))
    bump('Niveles', heroPlan.size)
  }

  const petPlan = new Map<string, number>()
  const selectedPets = new Set(effectiveUnlockedSet('petAffinity', draft, selected))
  for (const row of advanced?.pet_progression?.entries ?? []) {
    if (!row.editable || row.intimacy === null || row.max === null) continue
    const explicit = parseQuantity(draft.petAffinity[row.id] ?? '')
    if (explicit !== null && explicit !== row.intimacy && explicit >= row.intimacy && explicit <= row.max) {
      petPlan.set(row.id, explicit)
    } else if (selectedPets.has(row.id) && row.intimacy < row.max) {
      petPlan.set(row.id, row.max)
    }
  }
  if (petPlan.size > 0) {
    plan.pet_affinity = Array.from(petPlan, ([code, value]) => ({ code, value }))
    bump('Afinidad', petPlan.size)
  }

  const blueprintPlan = new Map<string, 'Got' | 'Researched'>()
  const selectedBlueprints = new Set(effectiveUnlockedSet('blueprints', draft, selected))
  const selectedObtain = new Set(effectiveUnlockedSet('blueprintObtain', draft, selected))
  for (const row of advanced?.blueprints?.entries ?? []) {
    if (row.status === 'Researched') continue
    const canCreate = row.creatable
    const canResearch = row.status === 'Got' || canCreate
    if (!canResearch) continue
    let target: 'Got' | 'Researched' | null = null
    const explicit = draft.blueprintStatus[row.id]
    if (explicit === 'Researched' && canResearch) target = 'Researched'
    else if (explicit === 'Got' && canCreate) target = 'Got'
    else if (selectedBlueprints.has(row.id)) target = draft.blueprintMode
    else if (selectedObtain.has(row.id)) target = 'Got'
    if (target && target !== row.status) blueprintPlan.set(row.id, target)
  }
  if (blueprintPlan.size > 0) {
    plan.blueprints = Array.from(blueprintPlan, ([id, status]) => ({ id, status }))
    bump('Planos', blueprintPlan.size)
  }

  const decorationPlan: NonNullable<LabUnifiedPlan['decorations']> = {}
  const decorationObjects = effectiveUnlockedSet('decorations', draft, selected)
  if (decorationObjects.length > 0) decorationPlan.objects = decorationObjects
  const decorationLevels: Array<{ id: string; level: number }> = []
  const selectedDecorationLevels = new Set(effectiveUnlockedSet('decorationLevels', draft, selected))
  for (const row of advanced?.decorations?.levels ?? []) {
    if (!row.editable || row.level === null) continue
    const explicit = parseQuantity(draft.decorationLevels[row.id] ?? '')
    if (explicit !== null && explicit > row.level && explicit <= row.max_observed) {
      decorationLevels.push({ id: row.id, level: explicit })
    } else if (selectedDecorationLevels.has(row.id) && row.level < row.max_observed) {
      decorationLevels.push({ id: row.id, level: row.max_observed })
    }
  }
  if (decorationLevels.length > 0) decorationPlan.levels = decorationLevels
  if (decorationObjects.length > 0 || decorationLevels.length > 0) {
    plan.decorations = decorationPlan
    bump('Decoraciones', decorationObjects.length + decorationLevels.length)
  }

  return { plan, counts, quantities }
}

export function quickChecked(
  key: BulkKey,
  draft: Draft,
  eligible: Eligibility,
): 'all' | 'some' | 'none' {
  const selection = effective(key, draft, eligible)
  const selected = eligible[key].filter((id) => selection[id]).length
  if (selected === 0) return 'none'
  return selected === eligible[key].length ? 'all' : 'some'
}

export function unlockProgress(save: NativeSaveSummary, key: BulkKey, eligible: Eligibility) {
  const report = save.report?.characters
  const characters = report?.catalog?.available === false ? [] : report?.items ?? []
  const advanced = advancedSnapshot(save)
  const unlocked = {
    characters: () => characters.filter((item) => item.unlocked === true).length,
    skills: () => characters.reduce((total, item) => total + item.skill_options.filter(
      ({ index }) => item.skills.some((skill) => skill.key === index && skill.unlocked === true),
    ).length, 0),
    skins: () => characters.reduce((total, item) => total + item.skin_options.filter(
      (skin) => skin.compatible && skin.state === 'unlocked',
    ).length, 0),
    pets: () => (advanced?.pets ?? []).filter((pet) => pet.present && pet.unlocked === true).length,
    petSkins: () => (advanced?.pet_skins ?? []).filter((skin) => skin.present && skin.unlocked === true).length,
    heroLevels: () => (advanced?.hero_levels?.entries ?? [])
      .filter((row) => row.level !== null && row.level >= (advanced?.hero_levels?.max ?? 0)).length,
    petAffinity: () => (advanced?.pet_progression?.entries ?? [])
      .filter((row) => row.intimacy !== null && row.max !== null && row.intimacy >= row.max).length,
    blueprints: () => (advanced?.blueprints?.entries ?? [])
      .filter((row) => row.status === 'Researched').length,
    blueprintObtain: () => (advanced?.blueprints?.entries ?? [])
      .filter((row) => row.status !== null).length,
    decorations: () => (advanced?.decorations?.objects ?? [])
      .filter((row) => row.unlocked).length,
    decorationLevels: () => (advanced?.decorations?.levels ?? [])
      .filter((row) => row.level !== null && row.level >= row.max_observed).length,
  }[key]()
  const pending = eligible[key].length
  return { unlocked, pending, total: unlocked + pending }
}

export { parseQuantity, skillKey, skinKey }
