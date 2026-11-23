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
  compatibility: 'synthetic' | 'confirmed' | 'read_only'
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

export type LabStatus = {
  mode: 'live' | 'read_only' | 'disabled'
  read_ready: boolean
  write_enabled: boolean
  write_ready: boolean
  admin_configured: boolean
  admin_required: boolean
  backup_count: number
  min_gems: number
  max_gems: number
  message: string
}

export type LabRemote = { source: string; size: number; sha256: string }

export type LabSave = {
  remote: LabRemote
  gems: number
  size: number
  sha256: string
  serialzed_version: number
}

export type LabBackup = {
  id: string
  created_at: string
  changed: boolean
  original_size: number
  original_sha256: string
  original_gems: number
  candidate_size: number
  candidate_sha256: string
  candidate_gems: number
  remote_source: string
  remote_size: number
  remote_sha256: string
}

export type LabByteDiff = {
  original_size: number
  modified_size: number
  first_difference: number | null
  common_prefix: number
  common_suffix: number
  changed_original_bytes: number
  changed_modified_bytes: number
  original_sha256: string
  modified_sha256: string
}

export type LabPrepared = {
  remote: LabRemote
  backup: LabBackup
  original_gems: number
  new_gems: number
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  validation: {
    valid: true
    structure_valid: true
    only_gems_changed: true
    message: string
  }
}

export type LabWriteResult = {
  action: 'confirm' | 'restore'
  backup_id: string
  uploaded: boolean
  accepted: boolean
  persisted: boolean
  already_original: boolean
  expected_sha256: string
  remote_sha256: string | null
  remote_size: number | null
  remote_gems: number | null
  status: number | null
  message: string
}

export type LabVerification = {
  backup_id: string
  matches_candidate: boolean
  matches_original: boolean
  remote_sha256: string
  remote_size: number
  remote_gems: number | null
  expected_candidate_sha256: string
  expected_original_sha256: string
  message: string
}

export class ApiProblem extends Error {
  constructor(message: string, readonly issues: Issue[] = [], readonly code = '') {
    super(message)
  }
}

const baseUrl = (
  import.meta.env.VITE_API_BASE_URL?.trim() ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8017' : '')
).replace(/\/+$/, '')

async function request(
  path: string,
  signal: AbortSignal,
  payload?: object,
  token = '',
  admin = '',
  credentials: RequestCredentials = 'omit',
) {
  if (!baseUrl) throw new ApiProblem('Falta configurar la URL de la API.')
  if (window.location.protocol === 'https:' && !baseUrl.toLowerCase().startsWith('https://')) {
    throw new ApiProblem('Configura una URL HTTPS para la API.')
  }
  const headers = new Headers()
  if (payload) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (admin) headers.set('X-SK-Cloud-Admin', admin)

  const response = await fetch(`${baseUrl}/api/v1${path}`, {
    method: payload ? 'POST' : 'GET',
    headers,
    body: payload ? JSON.stringify(payload) : undefined,
    cache: 'no-store',
    credentials,
    redirect: 'error',
    signal,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiProblem(
      body?.error?.message ?? 'La API no pudo procesar la solicitud.',
      body?.error?.issues ?? [],
      body?.error?.code,
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
  async labStatus(token: string, signal: AbortSignal): Promise<LabStatus> {
    return (await request('/cloud/lab/status', signal, undefined, token)).json()
  },
  async labSave(token: string, signal: AbortSignal): Promise<LabSave> {
    return (await request('/cloud/lab/save', signal, undefined, token)).json()
  },
  async labPrepare(new_gems: number, token: string, signal: AbortSignal): Promise<LabPrepared> {
    return (await request('/cloud/lab/prepare', signal, { new_gems }, token)).json()
  },
  async labConfirm(
    backup_id: string,
    expected_sha256: string,
    confirmation: 'SUBIR',
    token: string,
    admin: string,
    signal: AbortSignal,
  ): Promise<LabWriteResult> {
    return (await request(
      '/cloud/lab/confirm', signal,
      { backup_id, expected_sha256, confirmation }, token, admin,
    )).json()
  },
  async labRestore(
    backup_id: string,
    confirmation: 'RESTAURAR',
    token: string,
    admin: string,
    signal: AbortSignal,
  ): Promise<LabWriteResult> {
    return (await request(
      '/cloud/lab/restore', signal, { backup_id, confirmation }, token, admin,
    )).json()
  },
  async labVerify(backup_id: string, token: string, signal: AbortSignal): Promise<LabVerification> {
    return (await request('/cloud/lab/verify', signal, { backup_id }, token)).json()
  },
  async labBackups(token: string, signal: AbortSignal): Promise<{ backups: LabBackup[] }> {
    return (await request('/cloud/lab/backups', signal, undefined, token)).json()
  },
}

export type CloudAccount = {
  id: string
  label: string
  platform: 'android-global'
  connected: boolean
  write_ready: boolean
}
export type CloudAccounts = {
  configured: boolean
  storage_status?: 'ready' | 'misconfigured' | 'unavailable'
  message: string | null
  password_login_available: boolean
  login_message: string
  session_active?: boolean
  write_enabled?: boolean
  min_gems: number
  max_gems: number
  accounts: CloudAccount[]
}
type CloudAccountSession = { accounts: CloudAccount[]; session_active?: boolean }
export type AccountSave = LabSave & { downloaded_at: string }
export type AccountBackup = LabBackup & { confirmed: boolean }

async function accountRequest<T>(path: string, signal: AbortSignal, payload?: object): Promise<T> {
  return (await request(`/cloud/accounts${path}`, signal, payload, '', '', 'include')).json()
}

export const cloudAccounts = {
  list: (signal: AbortSignal) => accountRequest<CloudAccounts>('', signal),
  claim: (ticket: string, signal: AbortSignal) =>
    accountRequest<CloudAccountSession>('/claim', signal, { ticket }),
  login(email: string, password: string, signal: AbortSignal) {
    if (window.location.protocol !== 'https:' || !baseUrl.toLowerCase().startsWith('https://')) {
      throw new ApiProblem('El inicio de sesión requiere HTTPS en el editor y en la API.')
    }
    return accountRequest<CloudAccountSession>('/login', signal, { platform: 'android-global', email, password })
  },
  logout: (signal: AbortSignal) =>
    request('/cloud/accounts/logout', signal, {}, '', '', 'include'),
  account(id: string) {
    const path = `/${encodeURIComponent(id)}`
    return {
      rename: (label: string, signal: AbortSignal) =>
        accountRequest<{ accounts: CloudAccount[] }>(`${path}/rename`, signal, { label }),
      unlink: (signal: AbortSignal) =>
        accountRequest<{ accounts: CloudAccount[] }>(`${path}/unlink`, signal, { confirmation: 'DESVINCULAR' }),
      save: (signal: AbortSignal) => accountRequest<AccountSave>(`${path}/save`, signal),
      backups: (signal: AbortSignal) => accountRequest<{ backups: AccountBackup[] }>(`${path}/backups`, signal),
      prepare: (new_gems: number, source_sha256: string, signal: AbortSignal) =>
        accountRequest<LabPrepared>(`${path}/prepare`, signal, { new_gems, source_sha256 }),
      confirm: (backup_id: string, expected_sha256: string, signal: AbortSignal) =>
        accountRequest<LabWriteResult>(`${path}/confirm`, signal, { backup_id, expected_sha256, confirmation: 'SUBIR' }),
      restore: (backup_id: string, signal: AbortSignal) =>
        accountRequest<LabWriteResult>(`${path}/restore`, signal, { backup_id, confirmation: 'RESTAURAR' }),
      verify: (backup_id: string, signal: AbortSignal) =>
        accountRequest<LabVerification>(`${path}/verify`, signal, { backup_id }),
    }
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
