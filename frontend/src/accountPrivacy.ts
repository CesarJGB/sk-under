import { useSyncExternalStore } from 'react'
import type { NativeSession } from './api'

export const HIDDEN_EMAIL = '••••••••@••••.•••'
export const EMAIL_PRIVACY_KEY = 'sk-under.hide-email'
export const AUTO_ACCOUNT_LABEL = /^Cuenta [a-f0-9]{12}$/i

export function readEmailPrivacy() {
  try {
    return window.localStorage.getItem(EMAIL_PRIVACY_KEY) === 'true'
  } catch {
    return false
  }
}

let hidden = readEmailPrivacy()
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function setHideEmail(next: boolean | ((value: boolean) => boolean)) {
  const value = typeof next === 'function' ? next(hidden) : next
  if (value === hidden) return
  hidden = value
  try {
    window.localStorage.setItem(EMAIL_PRIVACY_KEY, String(value))
  } catch {
    // La preferencia es solo visual; un almacenamiento bloqueado no debe romper la cuenta.
  }
  listeners.forEach((listener) => listener())
}

export function useEmailPrivacy() {
  const hideEmail = useSyncExternalStore(subscribe, () => hidden, () => hidden)
  return [hideEmail, setHideEmail] as const
}

export function accountDisplay(
  session: NativeSession | null | undefined,
  options: { index?: number; total?: number; hideEmail: boolean },
) {
  const email = session?.account?.email?.trim() ?? ''
  const rawLabel = session?.account?.label?.trim() ?? ''
  const legacyLabel = rawLabel && !AUTO_ACCOUNT_LABEL.test(rawLabel) ? rawLabel : ''
  const total = options.total ?? 1
  const hasSensitive = Boolean(email) || rawLabel.includes('@')

  if (options.hideEmail && hasSensitive) {
    if (total > 1) {
      const label = `Cuenta ${(options.index ?? 0) + 1}`
      return { label, title: undefined, masked: true }
    }
    return { label: HIDDEN_EMAIL, title: undefined, masked: true }
  }

  const label = email || legacyLabel || 'Cuenta de ChillyRoom'
  return {
    label,
    title: options.hideEmail ? undefined : email || undefined,
    masked: false,
  }
}