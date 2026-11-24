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
  petFoodEdits: Record<string, string>
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
    petFoodEdits: {},
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
  return Number.isSafeInteger(number) && number >= 0 ? number : null
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
  return advanced.pets.filter((pet) => pet.editable && pet.present && !pet.unlocked).map((pet) => pet.id)
}

function eligiblePetSkins(advanced: LabAdvanced | null | undefined): string[] {
  if (!advanced || advanced.available === false) return []
  return advanced.pet_skins
    .filter((skin) => skin.editable && skin.present && !skin.unlocked)
    .map((skin) => skin.id)
}

export type Eligibility = Record<BulkKey, string[]>

export function eligibility(save: NativeSaveSummary | null): Eligibility {
  const characters = save?.report?.characters
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
  return Boolean(effective(key, draft, eligible)[item])
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
  return setBulk(key, true, { ...draft, manual: { ...draft.manual, [key]: {} } })
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
  const field = kind === 'materials' ? 'materialEdits' : kind === 'seeds' ? 'seedEdits' : 'petFoodEdits'
  const next = { ...draft[field] }
  if (value.trim() === '') delete next[id]
  else next[id] = value
  return { ...draft, [field]: next }
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
  minimum: QuickToggle | undefined,
  forbidden?: Set<string>,
): Array<{ id: string; value: number }> {
  const result: Array<{ id: string; value: number }> = []
  const minimumValue = minimum?.enabled ? parseQuantity(minimum.value) : null
  for (const row of rows) {
    if (forbidden?.has(row.id)) continue
    const manual = parseQuantity(edits[row.id] ?? '')
    if (manual !== null) {
      if (row.count === null || manual !== row.count) result.push({ id: row.id, value: manual })
      continue
    }
    if (minimumValue === null || !row.editable || !row.owned) continue
    if (row.count !== null && minimumValue > row.count) result.push({ id: row.id, value: minimumValue })
  }
  return result
}

export type BuiltPlan = {
  plan: LabUnifiedPlan
  counts: DraftCounts
  battlePassRecord: NonNullable<LabAdvanced['battle_pass']['records']>[number] | null
}

export function buildDraftPlan(save: NativeSaveSummary, draft: Draft): BuiltPlan {
  const advanced = save.advanced
  const counts: DraftCounts = { changes: 0, operations: 0, byCategory: {} }
  const plan: LabUnifiedPlan = {}
  const bump = (category: string, amount: number) => {
    if (amount <= 0) return
    counts.byCategory[category] = (counts.byCategory[category] ?? 0) + amount
    counts.changes += amount
    counts.operations += 1
  }

  const gems = draft.quick.gems.enabled ? parseQuantity(draft.quick.gems.value) : null
  if (gems !== null && gems !== save.gems) {
    plan.gems = gems
    bump('Gemas', 1)
  }
  const fishChip = draft.quick.fishChip.enabled ? parseQuantity(draft.quick.fishChip.value) : null
  if (fishChip !== null && fishChip !== (save.fish_chip ?? null)) {
    plan.fish_chip = fishChip
    bump('Fichas de pesca', 1)
  }
  const fishProgress = draft.quick.fishProgress.enabled ? parseQuantity(draft.quick.fishProgress.value) : null
  if (fishProgress !== null && fishProgress !== (save.cumulative_fish_count ?? null)) {
    plan.fish_progress = fishProgress
    bump('Recompensas de pesca', 1)
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
  const quickMaterials = draft.quick.materialsMin
  const quickSeeds = draft.quick.seedsMin
  const quickPetFood = draft.quick.petFoodMin
  const quickBattery = draft.quick.batteryMin

  const petFoodIds = new Set(['material_grain', 'material_battery'])
  const materials = materialPlan(
    advanced?.materials ?? [], draft.materialEdits, quickMaterials,
    new Set(['material_fish']),
  )
  // El mínimo de alimento tiene prioridad sobre el mínimo general para sus dos materiales.
  if (quickPetFood.enabled) {
    const foodMinimum = parseQuantity(quickPetFood.value)
    if (foodMinimum !== null) {
      for (const row of advanced?.pet_food ?? []) {
        if (!row.editable || !row.owned) continue
        if (row.count !== null && foodMinimum <= row.count) continue
        const index = materials.findIndex((entry) => entry.id === row.id)
        if (index >= 0) materials.splice(index, 1)
        materials.push({ id: row.id, value: foodMinimum })
      }
    }
  }
  for (const id of petFoodIds) {
    const manual = parseQuantity(draft.petFoodEdits[id] ?? '')
    if (manual !== null) {
      const row = advanced?.pet_food.find((entry) => entry.id === id)
      const index = materials.findIndex((entry) => entry.id === id)
      if (row?.count === manual) {
        if (index >= 0) materials.splice(index, 1)
        continue
      }
      if (index >= 0) materials[index] = { id, value: manual }
      else materials.push({ id, value: manual })
      continue
    }
    if (id !== 'material_battery' || !quickBattery.enabled) continue
    const batteryMinimum = parseQuantity(quickBattery.value)
    const row = advanced?.pet_food.find((entry) => entry.id === id)
    if (batteryMinimum === null || !row?.editable || !row.owned) continue
    if (row.count !== null && batteryMinimum <= row.count) continue
    const index = materials.findIndex((entry) => entry.id === id)
    if (index < 0) materials.push({ id, value: batteryMinimum })
  }
  if (materials.length > 0) {
    advancedPlan.materials = materials
    bump('Materiales', materials.length)
  }

  const seeds = materialPlan(advanced?.seeds ?? [], draft.seedEdits, quickSeeds)
  if (seeds.length > 0) {
    advancedPlan.seeds = seeds
    bump('Semillas', seeds.length)
  }

  const seasonCoin = draft.quick.seasonCoin.enabled ? parseQuantity(draft.quick.seasonCoin.value) : null
  if (seasonCoin !== null && advanced?.season_coin.available && seasonCoin !== advanced.season_coin.value) {
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
  if (draft.battlePass.enabled && advanced?.battle_pass.records?.length) {
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
  const selected = selectedCount(key, draft, eligible)
  if (selected === 0) return 'none'
  return selected >= eligible[key].length ? 'all' : 'some'
}

export function bulkSummary(key: BulkKey, draft: Draft, eligible: Eligibility) {
  return { selected: selectedCount(key, draft, eligible), total: eligible[key].length }
}

export { parseQuantity, skillKey, skinKey }