export type Health = {
  status: 'ok'
  access_mode: 'local' | 'token' | 'disabled'
  max_file_bytes: number
}

export type FormatInfo = {
  id: string
  name: string
  version: string
  extensions: string[]
  compatibility: 'synthetic' | 'confirmed'
  description: string
}

type FieldInfo = { id: string; label: string; category: string; editable: boolean }
export type EditorField = FieldInfo & (
  | { type: 'string'; value: string; min_length: number; max_length: number }
  | { type: 'integer'; value: number; minimum: number; maximum: number }
)

export type Inspection = {
  format: FormatInfo
  byte_size: number
  sha256: string
  fields: EditorField[]
}

export type Value = string | number
export type Changes = Record<string, Value>
export type AppliedChange = { field_id: string; original: Value; modified: Value }
export type Validation = {
  valid: true
  changes: AppliedChange[]
  output_byte_size: number
  output_sha256: string
}

type Issue = { code: string; message: string; field_id: string | null }

export class ApiProblem extends Error {
  constructor(message: string, readonly issues: Issue[] = []) {
    super(message)
  }
}

const baseUrl = (
  import.meta.env.VITE_API_BASE_URL?.trim() ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8017' : '')
).replace(/\/+$/, '')

async function request(path: string, signal: AbortSignal, payload?: object, token = '') {
  if (!baseUrl) throw new ApiProblem('Falta configurar la URL de la API.')
  if (window.location.protocol === 'https:' && !baseUrl.toLowerCase().startsWith('https://')) {
    throw new ApiProblem('Configura una URL HTTPS para la API.')
  }
  const headers = new Headers()
  if (payload) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${baseUrl}/api/v1${path}`, {
    method: payload ? 'POST' : 'GET',
    headers,
    body: payload ? JSON.stringify(payload) : undefined,
    cache: 'no-store',
    credentials: 'omit',
    redirect: 'error',
    signal,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiProblem(
      body?.error?.message ?? 'La API no pudo procesar la solicitud.',
      body?.error?.issues ?? [],
    )
  }
  return response
}

export const api = {
  async health(signal: AbortSignal): Promise<Health> {
    return (await request('/health', signal)).json()
  },
  async formats(signal: AbortSignal): Promise<{ formats: FormatInfo[] }> {
    return (await request('/formats', signal)).json()
  },
  async inspect(content_base64: string, token: string, signal: AbortSignal): Promise<Inspection> {
    return (await request('/files/inspect', signal, { content_base64 }, token)).json()
  },
  async validate(content_base64: string, changes: Changes, token: string, signal: AbortSignal): Promise<Validation> {
    return (await request('/files/validate', signal, { content_base64, changes }, token)).json()
  },
  async export(content_base64: string, changes: Changes, token: string, signal: AbortSignal) {
    const response = await request('/files/export', signal, { content_base64, changes }, token)
    const name = response.headers.get('Content-Disposition')?.match(/filename="([a-zA-Z0-9_.-]+)"/)?.[1]
    return { blob: await response.blob(), name: name ?? 'copia-editada' }
  },
}

export async function encodeFile(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  const chunks: string[] = []
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 0x8000)))
  }
  return btoa(chunks.join(''))
}
