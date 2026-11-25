import type {
  LabAdvanced, LabAdvancedPlan, LabSkillRef, LabSkinRef, LabUnifiedPlan, NativeSaveSummary,
  SaveCharacterReport,
} from './api'
import { pendingCharacterCodes, pendingSkillKeys, pendingSkinKeys, skillKey, skinKey } from './unlockSelections'

export type BulkKey = 'characters' | 'skills' | 'skins' | 'pets' | 'petSkins'
export type QuantityKey =
  | 'gems' | 'fishChip' | 'fishProgress' | 'seasonCoin'
  | 'materialsMin' | 'seedsMin' | 'petFoodMin' | 'batteryMin'

export type QuickToggle = { enabled: boolean; value: string }

export type Draft = {
  bulk: Record<BulkKey, boolean>
  manual: {
    characters: Record<string, true>
    skills: Record<string, true>
    skins: Record<string, true>
    pets: Record<string, true>
    petSkins: Record<string, true>
  }
  excluded: {
    characters: Record<string, true>
    skills: Record<string, true>
    skins: Record<string, true>
    pets: Record<string, true>
    petSkins: Record<string, true>
  }
  quick: Record<QuantityKey, QuickToggle>
  materialEdits: Record<string, string>
  seedEdits: Record<string, string>
  materialMinimums: Record<string, number>
  seedMinimums: Record<string, number>
  reborn: boolean
  battlePass: { enabled: boolean; seasonId: number | null; level: string; exp: string; buy: boolean | null }
}

export type DraftCounts = {
  changes: number
  operations: number
  byCategory: Record<string, number>
}

const quantityKeys: QuantityKey[] = [
  'gems', 'fishChip', 'fishProgress', 'seasonCoin', 'materialsMin', 'seedsMin', 'petFoodMin', 'batteryMin',
]

export const MAX_QUANTITY = 2_147_483_647
export const protectedMaterial = 'material_fish'
export const batteryId = 'material_battery'

export function originalQuantity(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null
}

export function advancedSnapshot(save: NativeSaveSummary | null) {
  return save?.advanced?.available === false ? null : save?.advanced
}

export function scalarQuantity(save: NativeSaveSummary, key: 'gems' | 'fishChip' | 'fishProgress' | 'seasonCoin') {
  const coin = advancedSnapshot(save)?.season_coin
  const stored = originalQuantity({
    gems: save.gems, fishChip: save.fish_chip, fishProgress: save.cumulative_fish_count, seasonCoin: coin?.value,
  }[key])
  const fish = save.report?.fish_chips
  const observed = key === 'fishChip' && fish?.balance_path === 'gameData.fishChip' && fish.balance_is_integer
    ? originalQuantity(fish.balance) : null
  return { original: stored ?? observed, editable: stored !== null && (key !== 'seasonCoin' || !!coin?.available) }
}

export function minimumRows(save: NativeSaveSummary, key: 'materialsMin' | 'seedsMin' | 'petFoodMin' | 'batteryMin') {
  const advanced = advancedSnapshot(save)
  if (key === 'materialsMin') return (advanced?.materials ?? []).filter((row) => row.id !== protectedMaterial)
  if (key === 'seedsMin') return advanced?.seeds ?? []
  const food = advanced?.pet_food ?? []
  return key === 'batteryMin' ? food.filter((row) => row.id === batteryId) : food
}

function emptySet(): Record<string, true> {
  return {}
}

export function createEmptyDraft(): Draft {
  return {
    bulk: { characters: false, skills: false, skins: false, pets: false, petSkins: false },
    manual: {
      characters: emptySet(), skills: emptySet(), skins: emptySet(), pets: emptySet(), petSkins: emptySet(),
    },
    excluded: {
      characters: emptySet(), skills: emptySet(), skins: emptySet(), pets: emptySet(), petSkins: emptySet(),
    },
    quick: Object.fromEntries(quantityKeys.map((key) => [key, { enabled: false, value: '' }])) as Record<QuantityKey, QuickToggle>,
    materialEdits: {},
    seedEdits: {},
    materialMinimums: {},
    seedMinimums: {},
    reborn: false,
    battlePass: { enabled: false, seasonId: null, level: '', exp: '', buy: null },
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

export function setQuick(key: QuantityKey, patch: Partial<QuickToggle>, draft: Draft): Draft {
  return { ...draft, quick: { ...draft.quick, [key]: { ...draft.quick[key], ...patch } } }
}

export function setEdit(
  kind: 'materials' | 'seeds' | 'petFood',
  id: string,
  value: string,
  draft: Draft,
): Draft {
  const field = kind === 'seeds' ? 'seedEdits' : 'materialEdits'
  const next = { ...draft[field] }
  if (value.trim() === '') delete next[id]
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
    if (manual !== null) {
      if ((original !== null || row.insertable) && manual !== original) result.push({ id: row.id, value: manual })
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
  battlePassRecord: NonNullable<LabAdvanced['battle_pass']['records']>[number] | null
}

export function buildDraftPlan(save: NativeSaveSummary, draft: Draft): BuiltPlan {
  const advanced = advancedSnapshot(save)
  const counts: DraftCounts = { changes: 0, operations: 0, byCategory: {} }
  const plan: LabUnifiedPlan = {}
  const bump = (category: string, amount: number) => {
    if (amount <= 0) return
    counts.byCategory[category] = (counts.byCategory[category] ?? 0) + amount
    counts.changes += amount
    counts.operations += 1
  }
  const requested = (key: QuantityKey) => draft.quick[key].enabled ? parseQuantity(draft.quick[key].value) : null
  const scalarChange = (key: 'gems' | 'fishChip' | 'fishProgress' | 'seasonCoin') => {
    const source = scalarQuantity(save, key)
    const value = requested(key)
    return source.editable && value !== source.original ? value : null
  }

  for (const [key, field, label] of [
    ['gems', 'gems', 'Gemas'],
    ['fishChip', 'fish_chip', 'Fichas de pesca'],
    ['fishProgress', 'fish_progress', 'Recompensas de pesca'],
  ] as const) {
    const value = scalarChange(key)
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
    if (explicit !== null) {
      if (explicit === current) materialChanges.delete(row.id)
      else if (current !== null || row.insertable) materialChanges.set(row.id, explicit)
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

  const seasonCoin = scalarChange('seasonCoin')
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

  let battlePassRecord: BuiltPlan['battlePassRecord'] = null
  if (draft.battlePass.enabled && advanced?.battle_pass?.records?.length) {
    const record = advanced.battle_pass.records.find((item) => item.season_id === draft.battlePass.seasonId)
      ?? advanced.battle_pass.records.find((item) => item.season_id === advanced.battle_pass.selected_season_id)
      ?? advanced.battle_pass.records[0]
    if (record.editable && record.season_id !== null) {
      const level = parseQuantity(draft.battlePass.level)
      const exp = parseQuantity(draft.battlePass.exp)
      const next: NonNullable<LabAdvancedPlan['battle_pass']> = { season_id: record.season_id }
      let changes = 0
      if (level !== null && level !== record.cur_level) {
        next.cur_level = level
        changes += 1
      }
      if (exp !== null && exp !== record.cur_exp) {
        next.cur_exp = exp
        changes += 1
      }
      if (draft.battlePass.buy !== null && draft.battlePass.buy !== record.has_buy) {
        next.has_buy = draft.battlePass.buy
        changes += 1
      }
      if (changes > 0) {
        advancedPlan.battle_pass = next
        battlePassRecord = record
        bump('Pase de batalla', changes)
      }
    }
  }

  if (advancedPlan.materials?.length || advancedPlan.seeds?.length
    || advancedPlan.season_coin !== undefined || advancedPlan.reborn_card
    || advancedPlan.battle_pass || advancedPlan.pets?.length || advancedPlan.pet_food?.length) {
    plan.advanced = advancedPlan
  }
  return { plan, counts, battlePassRecord }
}

export function draftHasChanges(save: NativeSaveSummary, draft: Draft): boolean {
  return buildDraftPlan(save, draft).counts.changes > 0
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
  }[key]()
  const pending = eligible[key].length
  return { unlocked, pending, total: unlocked + pending }
}

export { parseQuantity, skillKey, skinKey }
