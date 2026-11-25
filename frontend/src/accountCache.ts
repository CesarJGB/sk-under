import type { NativeSaveSummary } from './api'

// Solo en memoria: la copia descargada se reutiliza al navegar entre Partida y Editor
// sin persistirla en el navegador ni mezclarla entre cuentas.
const downloaded = new Map<string, NativeSaveSummary>()

export function cachedSave(accountId: string) {
  return downloaded.get(accountId) ?? null
}

export function cacheSave(accountId: string, save: NativeSaveSummary) {
  downloaded.set(accountId, save)
}

export function clearCachedSave(accountId: string) {
  downloaded.delete(accountId)
}