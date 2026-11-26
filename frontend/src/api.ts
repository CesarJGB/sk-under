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

export type SaveFishChipField = {
  path: string
  type: string
  value?: number | string
  entries?: number | null
  role?: string
  evidence?: string
}

export type SaveFishChips = {
  balance_path: string | null
  balance: number | null
  balance_is_integer: boolean
  server_authority: 'unknown'
  status: 'read_only'
  evidence: string
  validation_level?: 'E2' | 'E4'
  write_policy?: 'experimental_authorized' | 'confirmed_by_owner'
  transaction_validated: boolean
  missing_proof: string
  fields: SaveFishChipField[]
  distinct_collections: Record<string, { type: string; entries: number | null }>
}

export type SaveSkill = { key: number; unlocked: boolean | null; name: string | null }
export type SaveSkillOption = { index: number; name: string }
export type SaveSkin = { key: number; state: number | null; name: string | null }
export type SaveSkinOption = {
  index: number
  key: string
  name: string
  state: 'unlocked' | 'locked' | 'unknown'
  value: number | null
  compatible: boolean
}
export type SaveCharacter = {
  code: string
  name: string
  catalog_index: number | null
  unlocked: boolean | '<missing>'
  level: number | '<missing>'
  level_max: null
  level_status: 'not_validated'
  selected_skill: number | '<missing>'
  skills: SaveSkill[]
  skill_options: SaveSkillOption[]
  selected_skin: number | '<missing>'
  equipped_skin: SaveSkin | null
  skins_recorded: number
  skin_options: SaveSkinOption[]
  skins_status: 'confirmed_by_owner'
}

export type SaveSkillSummary = {
  total: number
  unlocked: number
  locked: number
  selected: number
  characters_with_data: number
  status: 'read_only'
}

export type SaveSkinsSummary = {
  total: number
  unlocked: number
  pending: number
  selected: number
  incompatible: number
  characters_with_data: number
  status: 'confirmed_by_owner'
}

export type SaveCharacterReport = {
  items: SaveCharacter[]
  counts: { characters: number; unlocked: number; selected_skins: number }
  skills?: SaveSkillSummary
  skins?: SaveSkinsSummary
  level_status: 'not_validated'
  skins_status: 'confirmed_by_owner'
  catalog: {
    available: boolean
    error: string | null
    version: string | null
    source: string | null
    characters: number
  }
  notes: string[]
  status: 'read_only'
}

export type SaveResourceItem = {
  id?: string
  count?: number
  type?: string
  text_length?: number
  plant?: string | null
  state?: number | string | null
  fertilized?: boolean | null
  watered?: boolean | null
  name?: string | null
  value?: number | string
}

export type SaveResourceGroup = {
  id: string
  label: string
  path: string
  state: 'present' | 'missing' | 'null'
  type: string
  entries: number
  status: 'read_only'
  evidence: string
  note: string
  items?: SaveResourceItem[]
  truncated?: boolean
  item_types?: Record<string, number>
  list_length?: number
  value?: number | string
}

export type SaveReport = {
  version: number
  game_version: number | null
  serialzed_version?: number
  encoding?: 'json' | 'gzip'
  fish_chips: SaveFishChips
  characters: SaveCharacterReport
  resources: {
    groups: SaveResourceGroup[]
    counts: Record<string, number>
    status: 'read_only'
    notes: string[]
  }
  limitations: string[]
}

export type LabItemRow = {
  id: string
  name: { en?: string | null; es?: string | null }
  subcategory: string | null
  plant_id: string | null
  count: number | null
  value_type: string | null
  owned: boolean
  known: boolean
  editable: boolean
  insertable: boolean
  reason: string | null
  path: string
}

export type LabSeasonCoin = {
  value: number | null
  value_type: string | null
  available: boolean
  path: string
  min: number
  max: number
  owner_reference: string
  note: string
}

export type LabRebornCard = {
  value: boolean | null
  available: boolean
  path: string
  experimental: boolean
  local_reference: string
  remote_representation: string
  projection: string
  limitation: string
  evidence_level: 'E2' | 'E3'
}

export type LabBattlePassRecord = {
  index: number
  key: number | null
  season_id: number | null
  cur_level: number | null
  cur_exp: number | null
  has_buy: boolean | null
  free_claimed_level: number | null
  paid_claimed_level: number | null
  max_level: number | null
  editable: boolean
  error: string | null
}

export type LabBattlePass = {
  records: LabBattlePassRecord[]
  selected_season_id: number | null
  active_season_id: number | null
  active_matches_selected: boolean | null
  note: string
}

export type LabPetRow = {
  id: string
  numeric_id: number
  name: { en?: string | null; es?: string | null }
  unlocked: boolean | null
  present: boolean
  value_type: string | null
  editable: boolean
  insertable: boolean
  path: string
  skins: string[]
  reason: string | null
}

export type LabPetSkinRow = {
  id: string
  pet_code: string
  base_pet: string
  skin_index: number
  name: { en?: string | null; es?: string | null }
  unlocked: boolean | null
  present: boolean
  value_type: string | null
  editable: boolean
  insertable: boolean
  path: string
  base_unlocked: boolean | null
  dependency_note: string
}

export type LabPetFoodRow = {
  id: string
  name: { en?: string | null; es?: string | null }
  count: number | null
  value_type: string | null
  owned: boolean
  editable: boolean
  insertable: boolean
  path: string
  field: 'itemData.materials'
  population: 'itemData.materials'
  reason: string | null
}

export type LabPetProgressionEntry = {
  id: string
  numeric_id: number
  name: { en?: string | null; es?: string | null }
  present: boolean
  intimacy: number | null
  full: boolean | null
  action_unlocked: boolean | null
  value_type: string | null
  max: number | null
  max_note: string
  path: string
  editable?: boolean
  reason?: string | null
  full_path?: string
}

export type LabPetProgression = {
  available: boolean
  path: string
  read_only: boolean
  global_full_count: number | null
  full_count_key: string
  entries: LabPetProgressionEntry[]
  note: string
  limitation?: string
  experimental?: boolean
  evidence_level?: 'E1' | 'E2' | 'E3' | 'E4'
}

export type LabHeroLevelEntry = {
  id: string
  name: string
  level: number | null
  value_type: string | null
  present: boolean
  editable: boolean
  unlocked: boolean | null
  path: string
  reason: string | null
}

export type LabHeroLevels = {
  available: boolean
  path: string
  min: number
  max: number
  max_note: string
  experimental: boolean
  evidence_level: 'E1' | 'E2' | 'E3' | 'E4'
  entries: LabHeroLevelEntry[]
  note: string
}

export type LabBlueprintEntry = {
  id: string
  key: string | null
  alias_key?: string | null
  name: { en?: string | null; es?: string | null }
  subcategory: string | null
  blueprint_type: number | null
  target: string | null
  research_materials: Array<{ item: string; num: number }>
  observed_extra?: boolean
  status: 'Got' | 'Researched' | null
  raw_value?: string | number | null
  value_type: string | null
  present: boolean
  creatable: boolean
  editable: boolean
  bulk_eligible: boolean
  reason?: string | null
  path: string | null
}

export type LabBlueprints = {
  available: boolean
  path: string
  statuses: Array<'Got' | 'Researched'>
  encoding?: 'text' | 'integer'
  entries: LabBlueprintEntry[]
  unmatched: string[]
  experimental: boolean
  evidence_level: 'E1' | 'E2' | 'E3' | 'E4'
  note: string
  limitation: string
}

export type LabAdvanced = {
  available?: false
  error?: string
  materials: LabItemRow[]
  seeds: LabItemRow[]
  season_coin: LabSeasonCoin
  reborn_card: LabRebornCard
  battle_pass: LabBattlePass
  pets: LabPetRow[]
  pet_skins: LabPetSkinRow[]
  pet_food: LabPetFoodRow[]
  pet_progression: LabPetProgression
  hero_levels?: LabHeroLevels
  blueprints?: LabBlueprints
  decorations?: LabDecorations
  pet_policy: {
    field: 'pets'
    experimental: boolean
    evidence_level: 'E2' | 'E3'
    path: string
    skin_note: string
    food_note: string
    progression_note: string
  }
  policy: {
    field: 'advanced'
    experimental: boolean
    evidence_level: 'E2' | 'E3'
    min: number
    max: number
    max_note: string
    material_fish_note: string
    confirmed_functions?: string[]
    experimental_functions?: string[]
  }
}

export type LabAdvancedPlan = {
  materials: Array<{ id: string; value: number }>
  seeds: Array<{ id: string; value: number }>
  season_coin?: number | null
  reborn_card?: true | null
  battle_pass?: {
    season_id: number
    cur_level?: number
    cur_exp?: number
    has_buy?: boolean
  } | null
  pets?: string[]
  pet_food?: Array<{ id: string; value: number }>
}

export type LabSave = {
  remote: LabRemote
  gems: number
  fish_chip?: number | null
  fish_chip_path?: string
  material_fish?: number | null
  material_fish_path?: string
  cumulative_fish_count?: number | null
  cumulative_fish_count_path?: string
  fish_chip_write_policy?: 'confirmed_by_owner'
  character_write_policy?: 'confirmed_by_owner'
  skill_write_policy?: 'confirmed_by_owner'
  skin_write_policy?: 'confirmed_by_owner'
  size: number
  sha256: string
  serialzed_version: number
  report?: SaveReport | null
  advanced?: LabAdvanced | null
}

export type LabBackup = {
  id: string
  created_at: string
  field?: 'gems' | 'fish_chip' | 'fish_progress' | 'characters' | 'skills' | 'skins' | 'advanced' | 'unified'
  changed: boolean
  original_size: number
  original_sha256: string
  original_gems: number
  original_value?: number
  candidate_size: number
  candidate_sha256: string
  candidate_gems: number
  candidate_value?: number
  remote_source: string
  remote_size: number
  remote_sha256: string
  character_codes?: string[]
  skill_selections?: Array<{ code: string; index: number }>
  skin_selections?: Array<{ code: string; index: number }>
  advanced_plan?: LabAdvancedPlan
  unified_plan?: LabUnifiedPlan
}

export type LabDecorationObject = {
  id: string
  label: string
  unlocked: boolean
  value: unknown
  editable: boolean
  reason: string
  path: string | null
}

export type LabDecorationLevel = {
  id: string
  level: number | null
  max_observed: number
  editable: boolean
  reason: string
  path: string | null
}

export type LabDecorationAppearance = {
  id: string
  key: string | null
  name: { en?: string | null; es?: string | null }
  subcategory: string | null
  status: 'Got' | 'Researched' | null
  obtained: boolean
  researched: boolean
  path: string | null
}

export type LabDecorations = {
  available: boolean
  objects: LabDecorationObject[]
  levels: LabDecorationLevel[]
  appearances: LabDecorationAppearance[]
  unknown_objects: string[]
  unknown_levels: string[]
  room: {
    current: unknown
    current_type: string | null
    room_level: number | null
    unlock_list: string[] | null
    selection_editable: boolean
    selection_reason: string
  }
  experimental: boolean
  evidence_level: 'E1' | 'E2' | 'E3' | 'E4'
  note: string
  limitation: string
}

export type LabUnifiedPlan = {
  gems?: number | null
  fish_chip?: number | null
  fish_progress?: number | null
  characters?: string[]
  skills?: LabSkillRef[]
  skins?: LabSkinRef[]
  advanced?: LabAdvancedPlan | null
  hero_levels?: Array<{ code: string; level: number }>
  pet_affinity?: Array<{ code: string; value: number }>
  blueprints?: Array<{ id: string; status: 'Got' | 'Researched' }>
  decorations?: {
    objects?: string[]
    levels?: Array<{ id: string; level: number }>
  } | null
}

export type LabCategoryKey =
  | 'gems' | 'fish_chip' | 'fish_progress' | 'characters' | 'skills' | 'skins'
  | 'advanced' | 'hero_levels' | 'pet_affinity' | 'blueprints' | 'decorations'

export type LabUnifiedCategory = {
  key: LabCategoryKey
  label: string
  changes: number
  detail: Record<string, unknown>
}

export type LabUnifiedPrepared = {
  remote: LabRemote
  backup: LabBackup
  field: 'unified'
  plan: LabUnifiedPlan
  categories: LabUnifiedCategory[]
  steps: string[]
  change_count: number
  original_value?: number
  new_value?: number
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  changed_fields: string[]
  validation: {
    valid: true
    structure_valid: true
    atomic: true
    message: string
  }
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
  field?: 'gameData.gems'
  original_gems: number
  new_gems: number
  original_value?: number
  new_value?: number
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  changed_fields?: string[]
  validation: {
    valid: true
    structure_valid: true
    only_gems_changed: boolean
    message: string
  }
}

export type LabFishChipPrepared = {
  remote: LabRemote
  backup: LabBackup
  field: 'gameData.fishChip'
  material_fish_path: string
  original_fish_chip: number
  new_fish_chip: number
  original_material_fish?: number | null
  new_material_fish: number
  original_value?: number
  new_value?: number
  experimental: true
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  changed_fields: string[]
  validation: {
    valid: true
    structure_valid: true
    only_fish_fields_changed: boolean
    experimental: true
    evidence_level: 'E2'
    message: string
  }
}

export type LabFishProgressPrepared = {
  remote: LabRemote
  backup: LabBackup
  field: 'itemData.cumulativeFishCount'
  original_cumulative_fish_count: number
  new_cumulative_fish_count: number
  original_value?: number
  new_value?: number
  experimental: true
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  changed_fields: string[]
  validation: {
    valid: true
    structure_valid: true
    only_fish_progress_changed: boolean
    experimental: true
    evidence_level: 'E2'
    message: string
  }
}

export type LabAdvancedPrepared = {
  remote: LabRemote
  backup: LabBackup
  field: 'advanced'
  plan: LabAdvancedPlan
  changes: Array<{ path: string; before: unknown; after: unknown }>
  original_value?: number
  new_value?: number
  experimental: boolean
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  changed_fields: string[]
  validation: {
    valid: true
    structure_valid: true
    only_advanced_changed: boolean
    experimental: boolean
    evidence_level: 'E2' | 'E3'
    message: string
  }
}

export type LabCharacterPrepared = {
  remote: LabRemote
  backup: LabBackup
  field: 'gameData.heroUnlock'
  original_unlocked_count: number
  new_unlocked_count: number
  total_characters: number
  selected_codes: string[]
  newly_unlocked_codes: string[]
  original_value?: number
  new_value?: number
  experimental: false
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  changed_fields: string[]
  validation: {
    valid: true
    structure_valid: true
    only_characters_changed: boolean
    experimental: false
    evidence_level: 'confirmed_by_owner'
    message: string
  }
}

export type LabSkillRef = { code: string; index: number }

export type LabSkillPrepared = {
  remote: LabRemote
  backup: LabBackup
  field: 'gameData.heroSkillUnlock'
  original_unlocked_count: number
  new_unlocked_count: number
  total_skills: number
  selected_skills: LabSkillRef[]
  newly_unlocked_skills: LabSkillRef[]
  affected_codes: string[]
  original_value?: number
  new_value?: number
  experimental: false
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  changed_fields: string[]
  validation: {
    valid: true
    structure_valid: true
    only_skills_changed: boolean
    experimental: false
    evidence_level: 'E3'
    message: string
  }
}

export type LabSkinRef = { code: string; index: number }

export type LabSkinPrepared = {
  remote: LabRemote
  backup: LabBackup
  field: 'gameData.skinLock'
  original_unlocked_count: number
  new_unlocked_count: number
  total_skins: number
  selected_skins: LabSkinRef[]
  newly_unlocked_skins: LabSkinRef[]
  affected_codes: string[]
  locked_character_codes: string[]
  original_value?: number
  new_value?: number
  experimental: false
  changed: boolean
  candidate_size: number
  candidate_sha256: string
  byte_diff: LabByteDiff
  changed_fields: string[]
  validation: {
    valid: true
    structure_valid: true
    only_skins_changed: boolean
    experimental: false
    evidence_level: 'E3'
    message: string
  }
}

export type LabWriteResult = {
  action: 'confirm' | 'restore'
  backup_id: string
  field?: string
  uploaded: boolean
  accepted: boolean
  persisted: boolean
  already_original: boolean
  expected_sha256: string
  remote_sha256: string | null
  remote_size: number | null
  remote_gems: number | null
  remote_value?: number | null
  remote_material_fish?: number | null
  remote_characters?: number | null
  remote_skills?: number | null
  remote_skins?: number | null
  status: number | null
  message: string
  historical?: boolean
  preventive_backup_id?: string | null
}

export type LabVerification = {
  backup_id: string
  field?: string
  matches_candidate: boolean
  matches_original: boolean
  remote_sha256: string
  remote_size: number
  remote_gems: number | null
  remote_value?: number | null
  remote_material_fish?: number | null
  remote_characters?: number | null
  remote_skills?: number | null
  remote_skins?: number | null
  expected_candidate_sha256: string
  expected_original_sha256: string
  message: string
}

export class ApiProblem extends Error {
  constructor(message: string, readonly issues: Issue[] = [], readonly code = '', readonly status = 0) {
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
  extraHeaders?: Record<string, string>,
) {
  if (!baseUrl) throw new ApiProblem('Falta configurar la URL de la API.')
  if (window.location.protocol === 'https:' && !baseUrl.toLowerCase().startsWith('https://')) {
    throw new ApiProblem('Configura una URL HTTPS para la API.')
  }
  const headers = new Headers(extraHeaders)
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
  }).catch((error: unknown) => {
    if (error instanceof TypeError) {
      throw new ApiProblem('No se pudo conectar con la API de SK-Under.', [], 'network_error')
    }
    throw error
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiProblem(
      body?.error?.message ?? 'La API no pudo procesar la solicitud.',
      body?.error?.issues ?? [],
      body?.error?.code,
      response.status,
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

export type NativeDistribution = {
  id: string
  label: string
  platform: 'android' | 'ios' | null
  game_version: string
  enabled: boolean
  validated: boolean
  note: string
}

export type NativeProfile = {
  id: string
  label: string
  distribution: string
  installation_ready: boolean
  bound: boolean
  write_allowed: boolean
  auto_generated?: boolean
  binding_pending?: boolean
  binding_wait_until?: number | null
  last_save_error?: string | null
}

export type NativeSaveSummary = {
  sha256: string
  gems: number
  fish_chip?: number | null
  fish_chip_path?: string
  material_fish?: number | null
  material_fish_path?: string
  cumulative_fish_count?: number | null
  cumulative_fish_count_path?: string
  fish_chip_write_policy?: 'confirmed_by_owner'
  character_write_policy?: 'confirmed_by_owner'
  skill_write_policy?: 'confirmed_by_owner'
  skin_write_policy?: 'confirmed_by_owner'
  downloaded_at?: string
  report?: SaveReport | null
  advanced?: LabAdvanced | null
}

export type NativeBackupKind = 'edit' | 'manual' | 'preventive'

export type NativeBackupSummary = {
  save_size?: number
  gems?: number
  fish_chip?: number
  material_fish?: number
  cumulative_fish_count?: number
  characters?: number
  skills?: number
  skins?: number
  game_version?: string | null
  serialzed_version?: string | null
}

export type NativeBackup = {
  id: string
  created_at: string | null
  field: NonNullable<LabBackup['field']> | 'snapshot' | null
  kind?: NativeBackupKind
  status: 'prepared' | 'verified' | 'unverified' | 'available' | 'unreadable'
  problem?: 'authentication' | 'incompatible' | 'file_unavailable' | 'integrity'
  integrity?: 'verified' | 'unreadable'
  can_restore?: boolean
  restoration?: 'verified' | 'unverified' | null
  interrupted?: boolean
  changed?: boolean
  original_size?: number
  original_value?: number
  candidate_value?: number
  changes?: number
  categories?: LabCategoryKey[]
  summary?: NativeBackupSummary | null
}

export type NativeBackupHistory = {
  backups: NativeBackup[]
  total: number
  listed: number
  limit: number
  unreadable: number
  next_cursor?: string | null
}

export type NativeVersion = {
  service: string
  api_version: string
  features: string[]
  commit: string | null
}

export type NativeSession = {
  active: boolean
  reason?: 'none' | 'expired' | 'disabled' | 'unavailable'
  message?: string | null
  account_id?: string
  expired?: boolean
  identity_verified?: boolean
  account?: {
    label: string
    email?: string | null
    distribution: string
    distribution_label: string
    platform: string | null
  }
  session_expires_at?: string
  idle_expires_at?: string
  installation_ready?: boolean
  auto_identity?: boolean
  binding_wait_until?: string | null
  write_enabled?: boolean
  write_ready?: boolean
  min_gems?: number
  max_gems?: number
  min_fish_chip?: number
  max_fish_chip?: number
  fish_chip_write_policy?: 'confirmed_by_owner'
  character_write_policy?: 'confirmed_by_owner'
  skill_write_policy?: 'confirmed_by_owner'
  skin_write_policy?: 'confirmed_by_owner'
  save?: NativeSaveSummary | null
  save_error?: string | null
}

export type NativeAccount = NativeSession & { id: string }

export type NativeConfig = {
  available: boolean
  enabled: boolean
  configured: boolean
  native_auth_ready?: boolean
  write_enabled: boolean
  secure: boolean
  min_gems: number
  max_gems: number
  min_fish_chip?: number
  max_fish_chip?: number
  fish_chip_write_policy?: 'confirmed_by_owner'
  character_write_policy?: 'confirmed_by_owner'
  skill_write_policy?: 'confirmed_by_owner'
  skin_write_policy?: 'confirmed_by_owner'
  login_available: boolean
  auto_identity?: boolean
  portal_enabled?: boolean
  requires_profile_selection?: boolean
  profiles: NativeProfile[]
  distributions: NativeDistribution[]
  accounts?: NativeAccount[]
  session: NativeSession
  problem_code?: string | null
  message?: string | null
}

export type NativeLoginInput = {
  distribution: string
  email: string
  password: string
  profile_id?: string
}

function requireSecureLogin() {
  const host = window.location.hostname
  if (host === 'localhost' || host === '127.0.0.1' || host === '::1') return
  if (window.location.protocol !== 'https:' || !baseUrl.toLowerCase().startsWith('https://')) {
    throw new ApiProblem('El inicio de sesión requiere HTTPS en el editor y en la API.', [], 'native_https_required')
  }
}

async function nativeRequest<T>(
  path: string, signal: AbortSignal, payload?: object, accountId?: string,
): Promise<T> {
  return (await request(
    `/cloud/native${path}`, signal, payload, '', '', 'include',
    accountId ? { 'X-SK-Account': accountId } : undefined,
  )).json()
}

export const nativeAuth = {
  config: (signal: AbortSignal) => nativeRequest<NativeConfig>('/config', signal),
  accounts: async (signal: AbortSignal) => {
    const response = await nativeRequest<{ accounts: NativeAccount[] }>('/accounts', signal)
    return response.accounts
  },
  session: (signal: AbortSignal, accountId?: string) =>
    nativeRequest<NativeSession>('/session', signal, undefined, accountId),
  login(input: NativeLoginInput, signal: AbortSignal) {
    requireSecureLogin()
    return nativeRequest<NativeSession>('/login', signal, input)
  },
  async logout(signal: AbortSignal): Promise<void> {
    await request('/cloud/native/logout', signal, {}, '', '', 'include')
  },
  async logoutAccount(accountId: string, signal: AbortSignal): Promise<void> {
    await request(`/cloud/native/accounts/${encodeURIComponent(accountId)}/logout`, signal, {}, '', '', 'include')
  },
  save: (signal: AbortSignal, accountId?: string) =>
    nativeRequest<NativeSaveSummary & { downloaded_at: string }>('/save', signal, undefined, accountId),
  installation: (unique_id: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<NativeSession>('/installation', signal, { unique_id }, accountId),
  prepare: (new_gems: number, source_sha256: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabPrepared>('/prepare', signal, { new_gems, source_sha256 }, accountId),
  prepareFishChip: (new_fish_chip: number, source_sha256: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabFishChipPrepared>('/prepare-fish-chip', signal, { new_fish_chip, source_sha256 }, accountId),
  prepareFishProgress: (
    new_cumulative_fish_count: number, source_sha256: string, signal: AbortSignal, accountId?: string,
  ) => nativeRequest<LabFishProgressPrepared>('/prepare-fish-progress', signal, {
    new_cumulative_fish_count,
    source_sha256,
  }, accountId),
  prepareAdvanced: (plan: LabAdvancedPlan, source_sha256: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabAdvancedPrepared>('/prepare-advanced', signal, { ...plan, source_sha256 }, accountId),
  prepareCharacters: (codes: string[], source_sha256: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabCharacterPrepared>('/prepare-characters', signal, { codes, source_sha256 }, accountId),
  prepareSkills: (skills: LabSkillRef[], source_sha256: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabSkillPrepared>('/prepare-skills', signal, { skills, source_sha256 }, accountId),
  prepareSkins: (skins: LabSkinRef[], source_sha256: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabSkinPrepared>('/prepare-skins', signal, { skins, source_sha256 }, accountId),
  prepareUnified: (plan: LabUnifiedPlan, source_sha256: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabUnifiedPrepared>('/prepare-unified', signal, { ...plan, source_sha256 }, accountId),
  confirm: (backup_id: string, expected_sha256: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabWriteResult>('/confirm', signal, { backup_id, expected_sha256, confirmation: 'SUBIR' }, accountId),
  restore: (backup_id: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabWriteResult>('/restore', signal, { backup_id, confirmation: 'RESTAURAR' }, accountId),
  restoreHistory: (backup_id: string, expected_sha256: string | null, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabWriteResult>('/restore-history', signal, {
      backup_id, confirmation: 'RESTAURAR', ...(expected_sha256 ? { expected_sha256 } : {}),
    }, accountId),
  verify: (backup_id: string, signal: AbortSignal, accountId?: string) =>
    nativeRequest<LabVerification>('/verify', signal, { backup_id }, accountId),
  createBackup: (signal: AbortSignal, accountId?: string) =>
    nativeRequest<{ message: string }>('/backups', signal, { confirmation: 'RESPALDAR' }, accountId),
  backups: async (signal: AbortSignal, cursor?: string | null, accountId?: string) => {
    const query = new URLSearchParams({ limit: '25' })
    if (cursor) query.set('cursor', cursor)
    const history = await nativeRequest<NativeBackupHistory>(`/backups?${query}`, signal, undefined, accountId)
    if (!Number.isInteger(history.total) || !Array.isArray(history.backups)) {
      throw new ApiProblem(
        'El servidor respondió con un formato de historial incompatible. Actualiza la página y vuelve a intentarlo.',
        [], 'native_backup_incompatible',
      )
    }
    return history
  },
  version: async (signal: AbortSignal): Promise<NativeVersion> => {
    const response = await request('/version', signal)
    return response.json()
  },
  diagnostics: (signal: AbortSignal, accountId?: string) =>
    nativeRequest<Record<string, unknown>>('/diagnostics', signal, undefined, accountId),
}

export async function encodeFile(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  const chunks: string[] = []
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 0x8000)))
  }
  return btoa(chunks.join(''))
}
