import type { AppliedChange, Changes, EditorField, Inspection, Value } from './api'

export type Draft = Record<string, string>
export type Session = { name: string; content: string; inspection: Inspection }

function interpret(field: EditorField, raw: string): Value | null {
  if (field.type === 'string') {
    const length = Array.from(raw).length
    return length >= field.min_length && length <= field.max_length ? raw : null
  }
  const parsed = Number(raw)
  return /^-?\d+$/.test(raw) && Number.isSafeInteger(parsed) &&
    parsed >= field.minimum && parsed <= field.maximum ? parsed : null
}

export function summarize(fields: EditorField[], draft: Draft) {
  const changes: Changes = {}
  const invalid = new Set<string>()
  const summary: AppliedChange[] = []
  for (const field of fields) {
    if (!field.editable || !Object.hasOwn(draft, field.id)) continue
    const modified = interpret(field, draft[field.id])
    if (modified === null) {
      invalid.add(field.id)
    } else if (field.value !== modified) {
      changes[field.id] = modified
      summary.push({ field_id: field.id, original: field.value, modified })
    }
  }
  return { changes, invalid, summary }
}

export function fieldLimits(field: EditorField) {
  return field.type === 'integer'
    ? `Entero de ${field.minimum} a ${field.maximum}`
    : `De ${field.min_length} a ${field.max_length} caracteres`
}

export function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  const [amount, unit] = bytes < 1024 * 1024
    ? [bytes / 1024, 'KiB']
    : [bytes / (1024 * 1024), 'MiB']
  return `${new Intl.NumberFormat('es-MX', { maximumFractionDigits: 1 }).format(amount)} ${unit}`
}
