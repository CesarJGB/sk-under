import type { SaveCharacterReport } from './api'

export type UnlockCategory = 'characters' | 'skills' | 'skins'

export type UnlockSelections = {
  characters: Set<string>
  skills: Set<string>
  skins: Set<string>
}

export function emptyUnlockSelections(): UnlockSelections {
  return { characters: new Set(), skills: new Set(), skins: new Set() }
}

export function skillKey(code: string, index: number) {
  return `${code}:${index}`
}

export function skinKey(code: string, index: number) {
  return `${code}:${index}`
}

export function pendingCharacterCodes(
  characters: SaveCharacterReport,
  applied: Set<string> = new Set(),
) {
  return characters.items
    .filter((character) => character.unlocked === false && !applied.has(character.code))
    .map((character) => character.code)
}

export function pendingSkillKeys(
  characters: SaveCharacterReport,
  applied: Set<string> = new Set(),
) {
  return characters.items.flatMap((character) => character.skill_options
    .filter((option) => character.skills.find((entry) => entry.key === option.index)?.unlocked === false)
    .map((option) => skillKey(character.code, option.index))
    .filter((key) => !applied.has(key)))
}

export function pendingSkinKeys(
  characters: SaveCharacterReport,
  applied: Set<string> = new Set(),
) {
  return characters.items.flatMap((character) => character.skin_options
    .filter((option) => option.state === 'locked' && option.compatible)
    .map((option) => skinKey(character.code, option.index))
    .filter((key) => !applied.has(key)))
}

export function pendingKeysFor(
  category: UnlockCategory,
  characters: SaveCharacterReport,
  applied: Set<string>,
) {
  if (category === 'characters') return pendingCharacterCodes(characters, applied)
  if (category === 'skills') return pendingSkillKeys(characters, applied)
  return pendingSkinKeys(characters, applied)
}