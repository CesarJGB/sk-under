import { useSyncExternalStore } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'
export type EffectiveTheme = 'light' | 'dark'

export const THEME_KEY = 'sk-under.theme'
export const THEME_COLORS: Record<EffectiveTheme, string> = {
  light: '#112820',
  dark: '#0C120F',
}

const DARK_QUERY = '(prefers-color-scheme: dark)'
const VALID_PREFERENCES: ThemePreference[] = ['light', 'dark', 'system']

function isPreference(value: unknown): value is ThemePreference {
  return typeof value === 'string' && VALID_PREFERENCES.includes(value as ThemePreference)
}

function readPreference(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  try {
    const value = window.localStorage.getItem(THEME_KEY)
    return isPreference(value) ? value : 'system'
  } catch {
    return 'system'
  }
}

function systemTheme(): EffectiveTheme {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'light'
  try {
    return window.matchMedia(DARK_QUERY).matches ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

let preference = readPreference()
let system = systemTheme()
let effective: EffectiveTheme = preference === 'system' ? system : preference
let initialized = false
let media: MediaQueryList | null = null
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((listener) => listener())
}

function applyTheme(theme: EffectiveTheme) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (root.dataset.theme !== theme) root.dataset.theme = theme
  root.style.colorScheme = theme
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta && meta.getAttribute('content') !== THEME_COLORS[theme]) {
    meta.setAttribute('content', THEME_COLORS[theme])
  }
}

function computeEffective() {
  effective = preference === 'system' ? system : preference
}

function onSystemChange(event: MediaQueryListEvent) {
  system = event.matches ? 'dark' : 'light'
  if (preference !== 'system') return
  const previous = effective
  computeEffective()
  if (effective === previous) return
  applyTheme(effective)
  emit()
}

function bindSystemListener() {
  if (media || typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
  try {
    media = window.matchMedia(DARK_QUERY)
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', onSystemChange)
    } else {
      media.addListener(onSystemChange)
    }
  } catch {
    media = null
  }
}

function initialize() {
  if (initialized || typeof window === 'undefined') return
  initialized = true
  bindSystemListener()
  applyTheme(effective)
  window.addEventListener('storage', (event) => {
    if (event.key !== null && event.key !== THEME_KEY) return
    const next = readPreference()
    if (next === preference) return
    preference = next
    computeEffective()
    applyTheme(effective)
    emit()
  })
}

initialize()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function getThemePreference() {
  return preference
}

export function getEffectiveTheme() {
  return effective
}

export function setThemePreference(next: ThemePreference) {
  if (!isPreference(next) || next === preference) return
  preference = next
  try {
    window.localStorage.setItem(THEME_KEY, next)
  } catch {
    // La apariencia es una preferencia visual: un almacenamiento bloqueado no debe romper la app.
  }
  computeEffective()
  applyTheme(effective)
  emit()
}

export function useTheme() {
  const selected = useSyncExternalStore(subscribe, getThemePreference, getThemePreference)
  const theme = useSyncExternalStore(subscribe, getEffectiveTheme, getEffectiveTheme)
  return { preference: selected, theme, setPreference: setThemePreference }
}