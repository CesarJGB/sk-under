import { expect, test, type Page } from '@playwright/test'

const EMPTY_NATIVE_HISTORY = { backups: [], total: 0, listed: 0, limit: 25, unreadable: 0 }
const SHA = 'a'.repeat(64)
const CANDIDATE = 'b'.repeat(64)
const PROFILE = {
  id: '1'.repeat(32), label: 'Instalación Android Global', distribution: 'android-global',
  installation_ready: true, bound: true, write_allowed: true,
}
const SECOND_PROFILE = {
  id: '2'.repeat(32), label: 'Cuenta B', distribution: 'android-global',
  installation_ready: true, bound: true, write_allowed: true,
}
const DISTRIBUTIONS = [
  { id: 'android-global', label: 'Android Global (GP)', platform: 'android', game_version: '8.8.0', enabled: true, validated: true, note: 'Validada.' },
  { id: 'android-vietnam', label: 'Android Vietnam (GP_VNM)', platform: 'android', game_version: '8.8.0', enabled: false, validated: false, note: 'No validada.' },
  { id: 'ios-global', label: 'iOS Global (IOS)', platform: 'ios', game_version: '8.8.0.13', enabled: true, validated: true, note: 'Solo lectura.' },
  { id: 'ios-vietnam', label: 'iOS Vietnam (IOS_VNM)', platform: 'ios', game_version: '8.8.0', enabled: false, validated: false, note: 'No validada.' },
  { id: 'ios-china', label: 'iOS China (IOS_CN)', platform: 'ios', game_version: '8.8.0', enabled: false, validated: false, note: 'No validada.' },
  { id: 'taptap', label: 'TapTap', platform: 'android', game_version: '8.8.0', enabled: false, validated: false, note: 'No validada.' },
]
const SAVE = {
  verified: true, bytes: 505, sha256: SHA, gems: 1001, fish_chip: 3,
  fish_chip_path: 'gameData.fishChip', material_fish: 3,
  material_fish_path: 'itemData.materials.material_fish',
  cumulative_fish_count: 42,
  cumulative_fish_count_path: 'itemData.cumulativeFishCount',
  fish_chip_write_policy: 'confirmed_by_owner',
  sections: 17, remote_source: 'modern-cloud',
}
const ACTIVE = {
  active: true, identity_verified: true,
  account: {
    label: PROFILE.label, email: 'holder@example.test', distribution: 'android-global',
    distribution_label: 'Android Global (GP)', platform: 'android',
  },
  session_expires_at: '2026-12-01T00:05:40Z',
  idle_expires_at: '2026-11-24T02:00:00Z',
  installation_ready: true, auto_identity: true, binding_wait_until: null,
  write_enabled: true, write_ready: true,
  min_gems: 0, max_gems: 2_147_483_647, save: null, save_error: null,
}
const BASE_CONFIG = {
  available: true, enabled: true, configured: true, write_enabled: true, secure: false,
  min_gems: 0, max_gems: 2_147_483_647, login_available: true,
  auto_identity: true, requires_profile_selection: false,
  profiles: [], distributions: DISTRIBUTIONS,
  session: { active: false, reason: 'none' }, problem_code: null, message: null,
}
const BACKUP = {
  id: 'c'.repeat(32), created_at: '2026-11-23T20:00:00Z', changed: true,
  original_size: 505, original_sha256: SHA, original_gems: 1001,
  candidate_size: 505, candidate_sha256: CANDIDATE, candidate_gems: 1002,
  remote_source: 'modern-cloud', remote_size: 505, remote_sha256: SHA,
}
const REPORT = {
  version: 1, game_version: 80800, serialzed_version: 1, encoding: 'json',
  fish_chips: {
    balance_path: 'gameData.fishChip', balance: 3, balance_is_integer: true,
    server_authority: 'unknown', status: 'read_only', evidence: 'E4',
    validation_level: 'E4', write_policy: 'confirmed_by_owner', transaction_validated: true,
    missing_proof: 'El propietario confirmó el saldo y el gasto en un dispositivo Android físico.',
    fields: [], distinct_collections: {},
  },
  characters: {
    items: [{
      code: 'Knight', name: 'Knight', catalog_index: 0, unlocked: true, level: 2,
      level_max: null, level_status: 'not_validated', selected_skill: 0,
      skills: [
        { key: 0, unlocked: true, name: 'Dual Wield' },
        { key: 1, unlocked: false, name: 'Superior Fire' },
        { key: 2, unlocked: false, name: 'Shield Bash' },
      ],
      skill_options: [
        { index: 0, name: 'Dual Wield' },
        { index: 1, name: 'Superior Fire' },
        { index: 2, name: 'Shield Bash' },
      ],
      skin_options: [
        { index: 0, key: 'c0_skin0', name: 'Knight', state: 'unlocked', value: 1, compatible: true },
        { index: 1, key: 'c0_skin1', name: 'Elite Knight', state: 'locked', value: 0, compatible: true },
        { index: 2, key: 'c0_skin2', name: 'Lava Knight', state: 'unknown', value: null, compatible: false },
      ],
      selected_skin: 0, equipped_skin: { key: 0, state: 1, name: 'Knight' },
      skins_recorded: 3, skins_status: 'confirmed_by_owner',
    }, ...['Ranger', 'Mage', 'Alchemist'].map((name, index) => ({
      code: name, name, catalog_index: index + 1, unlocked: false, level: 0,
      level_max: null, level_status: 'not_validated', selected_skill: 0,
      skills: name === 'Ranger' ? [
        { key: 0, unlocked: true, name: 'Arrow Rain' },
        { key: 1, unlocked: false, name: "Hunter's Mark" },
      ] : [{ key: 0, unlocked: true, name: `${name} Skill` }],
      skill_options: name === 'Ranger' ? [
        { index: 0, name: 'Arrow Rain' },
        { index: 1, name: "Hunter's Mark" },
      ] : [{ index: 0, name: `${name} Skill` }],
      skin_options: name === 'Ranger' ? [
        { index: 0, key: 'c1_skin0', name: 'Ranger', state: 'unlocked', value: 1, compatible: true },
        { index: 1, key: 'c1_skin1', name: 'Hunter', state: 'locked', value: 12000, compatible: true },
      ] : [
        { index: 0, key: `c${index + 1}_skin0`, name, state: 'unlocked', value: 1, compatible: true },
        ...(name === 'Mage'
          ? [{ index: 1, key: 'c2_skin1', name: 'Apprentice', state: 'locked', value: 5000, compatible: true }]
          : []),
      ],
      selected_skin: '<missing>', equipped_skin: null,
      skins_recorded: name === 'Ranger' ? 2 : name === 'Mage' ? 2 : 1,
      skins_status: 'confirmed_by_owner',
    }))],
    counts: { characters: 42, unlocked: 1, selected_skins: 1 },
    skills: {
      total: 7, unlocked: 4, locked: 3, selected: 4,
      characters_with_data: 4, status: 'read_only',
    },
    skins: {
      total: 8, unlocked: 4, pending: 3, selected: 1,
      incompatible: 1, characters_with_data: 4, status: 'confirmed_by_owner',
    },
    level_status: 'not_validated', skins_status: 'confirmed_by_owner',
    catalog: {
      available: true, error: null, version: '8.8.0', source: 'SKDFE', characters: 42,
    },
    notes: ['El nivel se muestra tal como aparece en la partida; no hay máximo validado.'],
    status: 'read_only',
  },
  resources: {
    groups: [{
      id: 'materials', label: 'Materiales', path: 'itemData.materials', state: 'present',
      type: 'object', entries: 1, status: 'read_only', evidence: 'E2',
      note: 'Identificadores observados.', items: [{ id: 'wood', count: 4 }], truncated: false,
    }, {
      id: 'plants', label: 'Plantas', path: 'itemData.plants', state: 'present',
      type: 'list', entries: 0, status: 'read_only', evidence: 'E2',
      note: 'Estado observado por planta.', items: [], truncated: false,
    }],
    counts: { materials: 1, plants: 0 }, status: 'read_only', notes: [],
  },
  limitations: ['No se habilita la escritura de recursos.'],
}
const PREPARED = {
  remote: { source: 'modern-cloud', size: 505, sha256: SHA }, backup: BACKUP,
  original_gems: 1001, new_gems: 1002, changed: true,
  candidate_size: 505, candidate_sha256: CANDIDATE,
  changed_fields: ['gameData.gems', 'gameData.varGems'],
  byte_diff: {
    original_size: 505, modified_size: 505, first_difference: 1, common_prefix: 1,
    common_suffix: 503, changed_original_bytes: 1, changed_modified_bytes: 1,
    original_sha256: SHA, modified_sha256: CANDIDATE,
  },
  validation: { valid: true, structure_valid: true, only_gems_changed: false, message: 'Campos modificados: gameData.gems, gameData.varGems.' },
}
const IOS_PREPARED = {
  ...PREPARED,
  field: 'unified',
  plan: { gems: 1002 },
  categories: [{ key: 'gems', label: 'Gemas', changes: 1, detail: { kind: 'explicit' } }],
  steps: ['gems'],
  change_count: 1,
  validation: { ...PREPARED.validation, atomic: true },
}
const FISH_BACKUP = {
  ...BACKUP, field: 'fish_chip', original_gems: 3, original_value: 3,
  candidate_gems: 7, candidate_value: 7,
}
const CHARACTER_BACKUP = {
  ...BACKUP, field: 'characters', original_gems: 1, original_value: 1,
  candidate_gems: 2, candidate_value: 2, character_codes: ['Ranger'],
}
function characterPrepared(codes: string[]) {
  return {
    remote: { source: 'modern-cloud', size: 505, sha256: SHA },
    backup: {
      ...CHARACTER_BACKUP,
      candidate_gems: 1 + codes.length,
      candidate_value: 1 + codes.length,
      character_codes: codes,
    },
    field: 'gameData.heroUnlock', original_unlocked_count: 1,
    new_unlocked_count: 1 + codes.length, total_characters: 42,
    selected_codes: codes, newly_unlocked_codes: codes,
    original_value: 1, new_value: 1 + codes.length, experimental: false, changed: true,
    candidate_size: 505, candidate_sha256: CANDIDATE, byte_diff: PREPARED.byte_diff,
    changed_fields: codes.map((code) => `gameData.heroUnlock.${code}`),
    validation: {
      valid: true, structure_valid: true, only_characters_changed: true,
      experimental: false, evidence_level: 'confirmed_by_owner',
      message: `Campos modificados: ${codes.map((code) => `gameData.heroUnlock.${code}`).join(', ')}.`,
    },
  }
}
const SKILL_BACKUP = {
  ...BACKUP, field: 'skills', original_gems: 4, original_value: 4,
  candidate_gems: 4, candidate_value: 4, skill_selections: [],
}
function skillPrepared(skills: Array<{ code: string; index: number }>) {
  const codes = [...new Set(skills.map((skill) => skill.code))]
  return {
    remote: { source: 'modern-cloud', size: 505, sha256: SHA },
    backup: {
      ...SKILL_BACKUP,
      candidate_gems: 4 + skills.length,
      candidate_value: 4 + skills.length,
      skill_selections: skills,
    },
    field: 'gameData.heroSkillUnlock', original_unlocked_count: 4,
    new_unlocked_count: 4 + skills.length, total_skills: 7,
    selected_skills: skills, newly_unlocked_skills: skills, affected_codes: codes,
    original_value: 4, new_value: 4 + skills.length, experimental: false, changed: true,
    candidate_size: 505, candidate_sha256: CANDIDATE, byte_diff: PREPARED.byte_diff,
    changed_fields: skills.map((skill) => `gameData.heroSkillUnlock.${skill.code}[${skill.index}]`),
    validation: {
      valid: true, structure_valid: true, only_skills_changed: true,
      experimental: false, evidence_level: 'E3',
      message: `Campos modificados: ${skills.map((skill) => `gameData.heroSkillUnlock.${skill.code}[${skill.index}]`).join(', ')}.`,
    },
  }
}
const SKIN_BACKUP = {
  ...BACKUP, field: 'skins', original_gems: 4, original_value: 4,
  candidate_gems: 4, candidate_value: 4, skin_selections: [],
}
function skinPrepared(skins: Array<{ code: string; index: number }>) {
  const codes = [...new Set(skins.map((skin) => skin.code))]
  return {
    remote: { source: 'modern-cloud', size: 505, sha256: SHA },
    backup: {
      ...SKIN_BACKUP,
      candidate_gems: 4 + skins.length,
      candidate_value: 4 + skins.length,
      skin_selections: skins,
    },
    field: 'gameData.skinLock', original_unlocked_count: 4,
    new_unlocked_count: 4 + skins.length, total_skins: 8,
    selected_skins: skins, newly_unlocked_skins: skins, affected_codes: codes,
    locked_character_codes: [],
    original_value: 4, new_value: 4 + skins.length, experimental: false, changed: true,
    candidate_size: 505, candidate_sha256: CANDIDATE, byte_diff: PREPARED.byte_diff,
    changed_fields: skins.map((skin) => `gameData.skinLock.${skin.code}[${skin.index}]`),
    validation: {
      valid: true, structure_valid: true, only_skins_changed: true,
      experimental: false, evidence_level: 'E3',
      message: `Campos modificados: ${skins.map((skin) => `gameData.skinLock.${skin.code}[${skin.index}]`).join(', ')}.`,
    },
  }
}
const FISH_PREPARED = {
  remote: { source: 'modern-cloud', size: 505, sha256: SHA }, backup: FISH_BACKUP,
  field: 'gameData.fishChip', original_fish_chip: 3, new_fish_chip: 7,
  material_fish_path: 'itemData.materials.material_fish',
  original_material_fish: 3, new_material_fish: 7,
  original_value: 3, new_value: 7, experimental: true, changed: true,
  candidate_size: 505, candidate_sha256: CANDIDATE,
  changed_fields: ['gameData.fishChip', 'itemData.materials.material_fish'],
  byte_diff: PREPARED.byte_diff,
  validation: {
    valid: true, structure_valid: true, only_fish_fields_changed: true,
    experimental: true, evidence_level: 'E2',
    message: 'Campos modificados: gameData.fishChip, itemData.materials.material_fish.',
  },
}

const PROGRESS_BACKUP = {
  ...BACKUP, field: 'fish_progress', original_gems: 42, original_value: 42,
  candidate_gems: 120, candidate_value: 120,
}
const FISH_PROGRESS_PREPARED = {
  remote: { source: 'modern-cloud', size: 505, sha256: SHA }, backup: PROGRESS_BACKUP,
  field: 'itemData.cumulativeFishCount',
  original_cumulative_fish_count: 42, new_cumulative_fish_count: 120,
  original_value: 42, new_value: 120, experimental: true, changed: true,
  candidate_size: 505, candidate_sha256: CANDIDATE,
  changed_fields: ['itemData.cumulativeFishCount'],
  byte_diff: PREPARED.byte_diff,
  validation: {
    valid: true, structure_valid: true, only_fish_progress_changed: true,
    experimental: true, evidence_level: 'E2',
    message: 'Campo modificado: itemData.cumulativeFishCount.',
  },
}

async function mockBase(page: Page, config: object = BASE_CONFIG) {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1_048_576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/version', (route) => route.fulfill({ json: {
    service: 'sk-under', api_version: '2026.11.25', commit: null,
    features: ['native_backup_history', 'native_backup_history_pagination', 'native_backup_manual'],
  } }))
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({ json: config }))
  await page.route('**/api/v1/cloud/native/session', (route) => {
    const active = (config as { session?: { active?: boolean } }).session
    if (active?.active) {
      return route.fulfill({ json: { ...active, account_id: 'primary' } })
    }
    return route.fulfill({
      status: 401,
      json: { error: { code: 'native_session_required', message: 'Inicia sesión.', issues: [] } },
    })
  })
}

async function mockEditor(page: Page, session: object = ACTIVE) {
  await page.route('**/api/v1/cloud/native/session', (route) => route.fulfill({
    json: { ...session, account_id: 'primary' },
  }))
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({
    json: { ...session, account_id: 'primary' },
  }))
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.route('**/api/v1/cloud/native/prepare', (route) => {
    expect(route.request().postDataJSON()).toEqual({ new_gems: 1002, source_sha256: SHA })
    return route.fulfill({ json: PREPARED })
  })
}

async function mockSession(page: Page, session: object = ACTIVE) {
  await page.route('**/api/v1/cloud/native/session', (route) => route.fulfill({
    json: { ...session, account_id: 'primary' },
  }))
}

async function submitLogin(page: Page, email = 'holder@example.test', password = 'fixture-password') {
  await page.getByLabel('Correo electrónico').fill(email)
  await page.getByLabel('Contraseña', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
}

async function openCategory(page: Page, title: string) {
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await page.getByRole('link', { name: `Revisar ${title}` }).click()
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1_048_576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
})

test('muestra las seis distribuciones, Android e iOS Global habilitadas y alterna la contraseña', async ({ page }) => {
  await mockBase(page)
  await page.setViewportSize({ width: 320, height: 730 })
  await page.goto('/partida')
  await expect(page.getByRole('heading', { name: 'Iniciar sesión en ChillyRoom' })).toBeVisible()
  await expect(page.getByLabel('Distribución')).toHaveValue('android-global')
  await expect(page.getByRole('option', { name: /iOS Global.*Subida pendiente/ })).toBeEnabled()
  await expect(page.getByRole('option', { name: /iOS Vietnam/ })).toBeDisabled()
  await expect(page.getByRole('option', { name: /TapTap/ })).toBeDisabled()
  const password = page.getByLabel('Contraseña', { exact: true })
  await expect(password).toHaveAttribute('type', 'password')
  await page.getByRole('button', { name: 'Mostrar contraseña' }).click()
  await expect(password).toHaveAttribute('type', 'text')
  await page.getByRole('button', { name: 'Ocultar contraseña' }).click()
  await expect(password).toHaveAttribute('type', 'password')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('rechaza credenciales sin filtrar detalles y limpia la contraseña', async ({ page }) => {
  await mockBase(page)
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({
    status: 401,
    json: { error: { code: 'native_credentials_rejected', message: 'rechazado', issues: [] } },
  }))
  await page.goto('/partida')
  await submitLogin(page)
  await expect(page.getByText('El correo o la contraseña no son correctos.', { exact: false })).toBeVisible()
  await expect(page.getByLabel('Contraseña', { exact: true })).toHaveValue('')
  await expect(page.locator('body')).not.toContainText('fixture-password')
})

test.fixme('inicia sesión, descarga, prepara, confirma y cierra sesión', async ({ page }) => {
  await mockBase(page)
  await mockEditor(page, { ...ACTIVE, save: SAVE })
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      backup_id: BACKUP.id, expected_sha256: CANDIDATE, confirmation: 'SUBIR',
    })
    return route.fulfill({ json: { action: 'confirm', backup_id: BACKUP.id, uploaded: true, accepted: true, persisted: true, already_original: false, expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505, remote_gems: 1002, status: 200, message: 'La descarga posterior coincide con el agregado subido.' } })
  })
  await page.route('**/api/v1/cloud/native/logout', (route) => route.fulfill({ status: 204 }))

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await submitLogin(page)
  await expect(page.getByLabel('Cuenta conectada')).toContainText(PROFILE.label)
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,001')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await page.getByLabel('Nueva cantidad de gemas').fill('1002')
  await page.getByRole('button', { name: 'Preparar edición' }).click()
  await expect(page.getByText('+1', { exact: true })).toBeVisible()
  await expect(page.getByText('Se ajusta la variación de gemas junto con el saldo.')).toBeVisible()
  const confirm = page.getByRole('button', { name: 'Subir y verificar' })
  await expect(confirm).toBeDisabled()
  await page.getByRole('checkbox').check()
  await confirm.click()
  await expect(page.getByText('Cambios guardados y verificados en la nube.')).toBeVisible()
  await page.getByRole('navigation').getByRole('link', { name: 'Partida' }).click()
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,002')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page.getByRole('heading', { name: 'Iniciar sesión en ChillyRoom' })).toBeVisible()
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveCount(0)
})

for (const [code, message] of [
  ['unsupported_gems_structure', 'La versión o los tipos de los campos de gemas son incompatibles con el editor.'],
  ['unknown_gems_dependencies', 'El saldo depende de contadores ausentes o fuera del intervalo compatible.'],
  ['inconsistent_gems_balance', 'Primero prepara una edición con el saldo conciliado (1000).'],
  ['network_error', 'No se pudo conectar con la API de SK-Under.'],
]) {
  test(`explica el error de preparación ${code}`, async ({ page }) => {
    await mockBase(page)
    await mockEditor(page, { ...ACTIVE, save: SAVE })
    await page.route('**/api/v1/cloud/native/prepare-unified', (route) => code === 'network_error'
      ? route.abort('connectionrefused')
      : route.fulfill({ status: 422, json: { error: { code, message } } }))
    await page.goto('/partida')
    await submitLogin(page)
    await page.getByRole('link', { name: 'Abrir Editor' }).click()
    await page.getByLabel('Gemas', { exact: true }).fill('1002')
    await page.getByRole('button', { name: 'Guardar' }).click()
    await expect(page.getByText(message, { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Guardar en la nube' })).toHaveCount(0)
  })
}

test('no pide identificadores y descarga con la identidad generada por el servidor', async ({ page }) => {
  await mockBase(page)
  await mockEditor(page, { ...ACTIVE, save: SAVE })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.goto('/partida')
  await expect(page.getByLabel('Identificador de instalación')).toHaveCount(0)
  await expect(page.getByLabel('Perfil de instalación')).toHaveCount(0)
  await submitLogin(page)
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,001')
  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await expect(page.getByRole('dialog')).toContainText('holder@example.test')
})

test('explica la espera de vinculación de un dispositivo nuevo', async ({ page }) => {
  await mockBase(page)
  const session = {
    ...ACTIVE, save: null, save_error: 'native_device_binding_throttled',
    binding_wait_until: '2026-11-25T08:00:00Z',
  }
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({ json: session }))
  await mockSession(page, session)
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.goto('/partida')
  await submitLogin(page)
  await expect(page.getByText('En espera de ChillyRoom', { exact: true })).toBeVisible()
  await expect(page.getByText('Vuelve a intentarlo después de', { exact: false })).toBeVisible()
})

test('informa sesión caducada durante una descarga y vuelve al acceso', async ({ page }) => {
  let expired = false
  await mockBase(page)
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({
    json: expired
      ? { ...BASE_CONFIG, session: { active: false, reason: 'expired', message: 'La sesión caducó. Inicia sesión de nuevo.' } }
      : BASE_CONFIG,
  }))
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({ json: { ...ACTIVE, save: SAVE } }))
  await mockSession(page, { ...ACTIVE, save: SAVE })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.route('**/api/v1/cloud/native/save', (route) => {
    expired = true
    return route.fulfill({
      status: 401,
      json: { error: { code: 'native_session_expired', message: 'La sesión caducó.', issues: [] } },
    })
  })

  await page.goto('/partida')
  await submitLogin(page)
  await page.getByRole('button', { name: 'Actualizar partida' }).click()
  await expect(page.getByRole('heading', { name: 'Renovar acceso a ChillyRoom' })).toBeVisible()
  await expect(page.getByText('La sesión de esta cuenta caducó. Solo necesitas volver a autenticarla.')).toBeVisible()
})

test('presenta el servicio no disponible sin pedir credenciales', async ({ page }) => {
  await mockBase(page, {
    ...BASE_CONFIG,
    available: false, configured: false, login_available: false,
    problem_code: 'native_auth_misconfigured',
    message: 'Falta configurar el servicio de autenticación nativa.',
    session: { active: false, reason: 'unavailable' },
  })
  await page.goto('/partida')
  await expect(page.getByRole('heading', { name: 'Servicio temporalmente no disponible' })).toBeVisible()
  await expect(page.getByLabel('Correo electrónico')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible()
})

test('permite elegir el perfil cuando hay más de uno', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, auto_identity: false, requires_profile_selection: true, profiles: [PROFILE, SECOND_PROFILE] })
  let requested = ''
  await page.route('**/api/v1/cloud/native/login', async (route) => {
    requested = String(route.request().postDataJSON().profile_id)
    const session = {
      ...ACTIVE,
      account: { label: SECOND_PROFILE.label, email: 'holder@example.test', distribution: 'android-global', distribution_label: 'Android Global (GP)', platform: 'android' },
      save: SAVE,
    }
    await route.fulfill({ json: session })
  })
  await mockSession(page, {
    ...ACTIVE,
    account: { label: SECOND_PROFILE.label, email: 'holder@example.test', distribution: 'android-global', distribution_label: 'Android Global (GP)', platform: 'android' },
    save: SAVE,
  })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.goto('/partida')
  await page.getByLabel('Perfil de instalación').selectOption(SECOND_PROFILE.id)
  await submitLogin(page)
  expect(requested).toBe(SECOND_PROFILE.id)
  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await expect(page.getByRole('dialog')).toContainText('holder@example.test')
})

test('oculta el correo y conserva la preferencia sin guardarlo en texto plano', async ({ page }) => {
  const email = 'holder@example.test'
  await mockBase(page, {
    ...BASE_CONFIG,
    session: { ...ACTIVE, save: { ...SAVE, report: REPORT, downloaded_at: '2026-11-23T20:00:00Z' } },
  })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.goto('/')
  const card = page.getByRole('article', { name: email })
  await expect(card).toContainText(email)

  await page.getByRole('button', { name: 'Ocultar correos' }).click()
  const hidden = page.getByRole('article', { name: '••••••••@••••.•••' })
  await expect(hidden).toBeVisible()
  await expect(hidden).not.toContainText(email)
  await expect(hidden.locator('strong')).not.toHaveAttribute('title', /.+/)
  await expect(page.locator(`[title*="${email}"]`)).toHaveCount(0)
  expect(await page.evaluate(() => localStorage.getItem('sk-under.hide-email'))).toBe('true')
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(email)

  await page.reload()
  await expect(page.getByRole('article', { name: '••••••••@••••.•••' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Mostrar correos' })).toBeVisible()
  await expect(page.locator('body')).not.toContainText(email)

  await page.getByRole('button', { name: 'Mostrar correos' }).click()
  await expect(page.getByRole('article', { name: email })).toContainText(email)
  await page.reload()
  await expect(page.getByRole('article', { name: email })).toContainText(email)

  await page.getByRole('button', { name: 'Ocultar correos' }).click()
  await page.goto('/partida')
  await expect(page.getByRole('heading', { name: 'Partida', exact: true })).toBeVisible()
  await expect(page.locator('body')).not.toContainText(email)
  await expect(page.locator(`[title*="${email}"]`)).toHaveCount(0)
  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await expect(page.getByRole('dialog')).not.toContainText(email)
  await expect(page.getByRole('dialog')).toContainText('••••••••@••••.•••')
  await page.keyboard.press('Escape')

  await page.goto('/editor')
  await expect(page.locator('body')).not.toContainText(email)
  await expect(page.locator(`[title*="${email}"]`)).toHaveCount(0)
})

test('permite preparar un candidato iOS y mantiene bloqueada la subida', async ({ page }) => {
  const ios = {
    ...ACTIVE, read_only: true, prepare_ready: true,
    write_state: 'write_pending_validation', write_enabled: false, write_ready: false,
    account: {
      ...ACTIVE.account, distribution: 'ios-global',
      distribution_label: 'iOS Global (IOS)', platform: 'ios', read_only: true,
    },
    save: SAVE,
  }
  const report = {
    ...REPORT, platform: 'ios', read_only: true, write_enabled: false, sha256: SHA,
    fish_chips: {
      ...REPORT.fish_chips, evidence: 'E2', validation_level: 'E2',
      write_policy: 'not_exposed', transaction_validated: false,
    },
    characters: { ...REPORT.characters, skins_status: 'not_validated' },
    limitations: ['El informe iOS es de solo lectura.'],
  }
  await mockBase(page, { ...BASE_CONFIG, write_enabled: false, session: ios })
  await mockEditor(page, ios)
  await page.route('**/api/v1/cloud/native/save', (route) => route.fulfill({
    json: { ...SAVE, report, downloaded_at: '2026-11-26T20:00:00Z' },
  }))
  let prepareBodies = 0
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    prepareBodies += 1
    return route.fulfill({ json: IOS_PREPARED })
  })
  let confirmations = 0
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    confirmations += 1
    return route.fulfill({ json: {} })
  })

  await page.goto('/editor')
  await expect(page.getByText('La subida remota está pendiente de validación', { exact: false })).toBeVisible()
  await expect(page.locator('fieldset.editor-content')).toBeEnabled()
  await page.getByRole('textbox', { name: 'Gemas', exact: true }).fill('1002')
  const prepare = page.getByRole('button', { name: 'Preparar candidato' })
  await expect(prepare).toBeEnabled()
  await prepare.click()

  await expect(page.getByRole('heading', { name: 'Revisar candidato' })).toBeVisible()
  await expect(page.getByText('Se creó un respaldo restaurable y un candidato verificado.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Subida pendiente de validación' })).toBeDisabled()
  await expect(page.getByRole('checkbox')).toHaveCount(0)
  expect(prepareBodies).toBe(1)
  await page.goto('/partida')
  await expect(page.getByText('La subida remota está pendiente de validación', { exact: false })).toBeVisible()
  expect(confirmations).toBe(0)
})

test('permite subir y verificar en el modo iOS experimental autorizado', async ({ page }) => {
  const ios = {
    ...ACTIVE, read_only: false, prepare_ready: true,
    write_state: 'write_experimental', write_enabled: true, write_ready: true,
    account: {
      ...ACTIVE.account, distribution: 'ios-global',
      distribution_label: 'iOS Global (IOS)', platform: 'ios', read_only: false,
    },
    save: SAVE,
  }
  await mockBase(page, { ...BASE_CONFIG, session: ios })
  await mockEditor(page, ios)
  let prepareBodies = 0
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    prepareBodies += 1
    return route.fulfill({ json: IOS_PREPARED })
  })
  let confirmations = 0
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    confirmations += 1
    expect(route.request().postDataJSON()).toEqual({
      backup_id: BACKUP.id, expected_sha256: CANDIDATE, confirmation: 'SUBIR',
    })
    return route.fulfill({ json: {
      action: 'confirm', backup_id: BACKUP.id, uploaded: true, accepted: true,
      persisted: true, already_original: false, expected_sha256: CANDIDATE,
      remote_sha256: CANDIDATE, remote_size: 505, remote_gems: 1002, status: 200,
      message: 'La descarga posterior coincide con el agregado subido.',
    } })
  })

  await page.goto('/editor')
  await expect(page.getByText('iOS experimental: esta cuenta de pruebas autorizada', { exact: false })).toBeVisible()
  await expect(page.locator('fieldset.editor-content')).toBeEnabled()
  await page.getByRole('textbox', { name: 'Gemas', exact: true }).fill('1002')
  await page.getByRole('button', { name: 'Guardar' }).click()

  await expect(page.getByRole('heading', { name: 'Revisar y guardar' })).toBeVisible()
  await expect(page.getByText('Modo experimental iOS limitado a esta cuenta de pruebas', { exact: false })).toBeVisible()
  const confirm = page.getByRole('checkbox')
  await expect(confirm).toBeVisible()
  await confirm.check()
  const save = page.getByRole('button', { name: 'Guardar en la nube' })
  await expect(save).toBeEnabled()
  await save.click()
  expect(prepareBodies).toBe(1)
  expect(confirmations).toBe(1)
  await expect(page.getByText('Subida confirmada.', { exact: false })).toBeVisible()
})

test('mantiene el editor iOS preparable sin desbordamiento en móvil, tablet y escritorio', async ({ page }) => {
  const ios = {
    ...ACTIVE, read_only: true, prepare_ready: true,
    write_state: 'write_pending_validation', write_enabled: false, write_ready: false,
    account: {
      ...ACTIVE.account, distribution: 'ios-global',
      distribution_label: 'iOS Global (IOS)', platform: 'ios', read_only: true,
    },
    save: SAVE,
  }
  await mockBase(page, { ...BASE_CONFIG, write_enabled: false, session: ios })
  await mockEditor(page, ios)
  await page.route('**/api/v1/cloud/native/save', (route) => route.fulfill({ json: SAVE }))

  for (const [width, height] of [[320, 730], [360, 780], [375, 812], [390, 844], [430, 932], [768, 1024], [1280, 900]]) {
    await page.setViewportSize({ width, height })
    await page.goto('/editor')
    await expect(page.getByText('La subida remota está pendiente de validación', { exact: false })).toBeVisible()
    await expect(page.locator('fieldset.editor-content')).toBeEnabled()
    await expect(page.getByTestId('editor-bar')).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `test-results/phase10-1/ios-${width}.png`, fullPage: true })
  }
})

test('explica el desafío del portal y no simula una sesión', async ({ page }) => {
  await mockBase(page)
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({
    status: 409,
    json: { error: { code: 'native_portal_challenge_required', message: 'captcha', issues: [] } },
  }))
  await page.goto('/partida')
  await submitLogin(page)
  await expect(page.getByText('ChillyRoom pidió una verificación adicional', { exact: false })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Iniciar sesión en ChillyRoom' })).toBeVisible()
})

test('informa cuando la cuenta no tiene partida en la nube', async ({ page }) => {
  await mockBase(page)
  const session = { ...ACTIVE, save: null, save_error: 'native_no_cloud_save' }
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({ json: session }))
  await mockSession(page, session)
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.goto('/partida')
  await submitLogin(page)
  await expect(page.getByText('Sin partida en la nube', { exact: true })).toBeVisible()
  await expect(page.getByText('Guarda una copia desde Soul Knight', { exact: false })).toBeVisible()
})

test.fixme('navega por el flujo de nube y mantiene el borrador solo para la cuenta activa', async ({ page }) => {
  const internalLabel = 'Cuenta ' + 'a'.repeat(12)
  let account = 0
  await mockBase(page)
  await page.route('**/api/v1/cloud/native/login', (route) => {
    account += 1
    return route.fulfill({ json: {
      ...ACTIVE,
      account: { ...ACTIVE.account, label: account === 1 ? internalLabel : SECOND_PROFILE.label },
      save: { ...SAVE, gems: account === 1 ? 1001 : 42 },
    } })
  })
  await page.route('**/api/v1/cloud/native/logout', (route) => route.fulfill({ status: 204 }))
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({
    json: { backups: account === 1 ? [{ ...BACKUP, confirmed: true }] : [] },
  }))

  await page.setViewportSize({ width: 320, height: 740 })
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Navegación principal' })
  await expect(nav.getByRole('link')).toHaveText(['Inicio', 'Partida', 'Editor'])
  await page.getByRole('link', { name: 'Conectar cuenta' }).click()
  await submitLogin(page)
  await expect(page.getByLabel('Cuenta conectada')).toContainText('ho…@example.test')
  await expect(page.locator('body')).not.toContainText(internalLabel)
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await page.getByLabel('Nueva cantidad de gemas').fill('1002')
  await nav.getByRole('link', { name: 'Inicio' }).click()
  await expect(page.getByText('Cuenta conectada', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Abrir partida' }).click()
  await expect(page.getByText('1,001 gemas', { exact: true })).toBeVisible()
  await nav.getByRole('link', { name: 'Editor' }).click()
  await expect(page.getByLabel('Nueva cantidad de gemas')).toHaveValue('1002')
  await nav.getByRole('link', { name: 'Partida' }).click()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await nav.getByRole('link', { name: 'Editor' }).click()
  await expect(page.getByLabel('Nueva cantidad de gemas')).toHaveCount(0)
  await page.getByRole('link', { name: 'Conectar cuenta' }).click()
  await submitLogin(page, 'second@example.test')
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('42')
  await expect(page.getByText('Esta cuenta todavía no tiene respaldos.')).toBeVisible()
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByLabel('Nueva cantidad de gemas')).toHaveValue('42')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320)
})

test.fixme('muestra el editor rápido con saldos y tarjetas de desbloqueo', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByTestId('native-current-fish-chip')).toHaveText('3')
  await expect(page.getByTestId('native-current-material-fish')).toHaveText('3')
  const fishSection = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Fichas de pesca' }) })
  await expect(fishSection.getByText('Experimental · E2')).toHaveCount(0)
  await expect(page.getByTestId('quick-personajes')).toContainText('1 de 42 desbloqueados')
  await expect(page.getByTestId('quick-personajes')).toContainText('3 pendientes')
  await expect(page.getByTestId('quick-habilidades')).toContainText('4 de 7 desbloqueados')
  await expect(page.getByTestId('quick-skins')).toContainText('4 de 8 desbloqueados')
  await expect(page.getByTestId('character-unlock-section')).toHaveCount(0)
  await expect(page.getByTestId('skill-unlock-section')).toHaveCount(0)
  await expect(page.getByTestId('skin-unlock-section')).toHaveCount(0)
  await expect(page.getByTestId('save-report')).toHaveCount(0)
  await expect(page.getByLabel('Nueva cantidad de gemas')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test.fixme('sincroniza la selección rápida y detallada y la conserva al navegar', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await page.getByLabel('Seleccionar todos: Personajes').check()
  await expect(page.getByTestId('quick-selected-count')).toHaveText('3')
  await expect(page.getByTestId('quick-personajes')).toContainText('Todo seleccionado')
  await page.getByRole('link', { name: 'Revisar personajes' }).click()
  await expect(page).toHaveURL(/\/editor\/personajes$/)
  await expect(page.getByLabel('Seleccionar Ranger')).toBeChecked()
  await expect(page.getByLabel('Seleccionar Mage')).toBeChecked()
  await page.getByLabel('Seleccionar Mage').uncheck()
  await page.getByRole('link', { name: '← Editor' }).click()
  await expect(page).toHaveURL(/\/editor$/)
  await expect(page.getByTestId('quick-selected-count')).toHaveText('2')
  await expect(page.getByTestId('quick-personajes')).toContainText('2 seleccionados')
  await page.getByRole('link', { name: 'Revisar personajes' }).click()
  await expect(page.getByLabel('Seleccionar Ranger')).toBeChecked()
  await expect(page.getByLabel('Seleccionar Mage')).not.toBeChecked()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test.fixme('edita y sube el saldo de fichas con el flujo autenticado', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: SAVE } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({
    json: { backups: [{ ...FISH_BACKUP, confirmed: true }] },
  }))
  await page.route('**/api/v1/cloud/native/prepare-fish-chip', (route) => {
    expect(route.request().postDataJSON()).toEqual({ new_fish_chip: 7, source_sha256: SHA })
    return route.fulfill({ json: FISH_PREPARED })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      backup_id: FISH_BACKUP.id, expected_sha256: CANDIDATE, confirmation: 'SUBIR',
    })
    return route.fulfill({ json: {
      action: 'confirm', backup_id: FISH_BACKUP.id, field: 'gameData.fishChip',
      uploaded: true, accepted: true, persisted: true, already_original: false,
      expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505,
      remote_gems: 1001, remote_value: 7, remote_material_fish: 7, status: 200,
      message: 'La descarga posterior coincide con el agregado subido de las fichas de pesca.',
    } })
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByTestId('native-current-fish-chip')).toHaveText('3')
  await expect(page.getByTestId('native-current-material-fish')).toHaveText('3')
  await expect(page.getByText('Experimental · E2')).toHaveCount(0)
  await expect(page.getByText('No modifica historiales, recompensas ni otros materiales.')).toBeVisible()
  await page.getByLabel('Nuevo saldo de fichas de pesca').fill('7')
  await page.getByRole('button', { name: 'Preparar cambio de fichas' }).click()
  await expect(page.getByRole('heading', { name: 'Revisar cambio de fichas' })).toBeVisible()
  const preview = page.locator('.cloud-preview-data')
  await expect(preview).toContainText('Fichas originales')
  await expect(preview).toContainText('Fichas nuevas')
  await expect(preview).toContainText('material_fish original')
  await expect(preview).toContainText('material_fish nuevo')
  await page.getByLabel(/cambio de fichas/).check()
  await page.getByRole('button', { name: 'Subir fichas y verificar' }).click()
  await expect(page.getByText('Fichas de pesca subidas y verificadas en la nube', { exact: false })).toBeVisible()
  await expect(page.getByTestId('native-current-fish-chip')).toHaveText('7')
  await expect(page.getByTestId('native-current-material-fish')).toHaveText('7')

  await page.getByRole('link', { name: 'Partida' }).click()
  await expect(page.getByText('3 fichas de pesca')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test.fixme('edita el progreso acumulado de fichas sin cambiar el saldo', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: SAVE } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({
    json: { backups: [{ ...PROGRESS_BACKUP, confirmed: true }] },
  }))
  await page.route('**/api/v1/cloud/native/prepare-fish-progress', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      new_cumulative_fish_count: 120, source_sha256: SHA,
    })
    return route.fulfill({ json: FISH_PROGRESS_PREPARED })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      backup_id: PROGRESS_BACKUP.id, expected_sha256: CANDIDATE, confirmation: 'SUBIR',
    })
    return route.fulfill({ json: {
      action: 'confirm', backup_id: PROGRESS_BACKUP.id, field: 'itemData.cumulativeFishCount',
      uploaded: true, accepted: true, persisted: true, already_original: false,
      expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505,
      remote_gems: 1001, remote_value: 120, status: 200,
      message: 'La descarga posterior coincide con el agregado subido del progreso acumulado.',
    } })
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByTestId('native-current-fish-progress')).toHaveText('42')
  await page.getByLabel('Nuevo progreso acumulado').fill('120')
  await page.getByRole('button', { name: 'Preparar cambio de progreso' }).click()
  await expect(page.getByRole('heading', { name: 'Revisar progreso acumulado' })).toBeVisible()
  const preview = page.locator('.fish-progress-editor')
  await expect(preview).toContainText('Progreso original')
  await expect(preview).toContainText('120')
  await page.getByLabel(/con este progreso acumulado/).check()
  await page.getByRole('button', { name: 'Subir progreso y verificar' }).click()
  await expect(page.getByText('Progreso acumulado subido y verificado en la nube', { exact: false })).toBeVisible()
  await expect(page.getByTestId('native-current-fish-progress')).toHaveText('120')
  await expect(page.getByTestId('native-current-fish-chip')).toHaveText('3')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test.fixme('rechaza valores inválidos de fichas antes de preparar la edición', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: SAVE } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  const input = page.getByLabel('Nuevo saldo de fichas de pesca')
  const prepare = page.getByRole('button', { name: 'Preparar cambio de fichas' })

  await input.fill('-1')
  await expect(input).toHaveAttribute('aria-invalid', 'true')
  await expect(prepare).toBeDisabled()
  await input.fill('2.5')
  await expect(input).toHaveAttribute('aria-invalid', 'true')
  await expect(prepare).toBeDisabled()
  await input.fill('4')
  await expect(input).toHaveAttribute('aria-invalid', 'false')
  await expect(prepare).toBeEnabled()
})

test.fixme('bloquea la preparación cuando el catálogo de personajes no está disponible',
  async ({ page }) => {
    const unavailable = {
      ...REPORT,
      characters: {
        ...REPORT.characters,
        items: [],
        counts: { characters: 0, unlocked: 0, selected_skins: 0 },
        skills: {
          total: 0, unlocked: 0, locked: 0, selected: 0,
          characters_with_data: 0, status: 'read_only',
        },
        catalog: {
          available: false, error: 'catalog_missing', version: null, source: null,
          characters: 0,
        },
      },
    }
    await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: unavailable } } })
    await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
    await page.goto('/partida')
    await openCategory(page, 'personajes')
    await expect(page.getByTestId('character-catalog-unavailable')).toBeVisible()
    await expect(page.getByTestId('character-catalog-unavailable')).toContainText(
      'Catálogo de personajes no disponible',
    )
    await expect(page.getByRole('button', { name: 'Preparar desbloqueo' }))
      .toBeDisabled()
    await expect(page.getByRole('button', { name: 'Seleccionar bloqueados' }))
      .toBeDisabled()
    await page.getByRole('link', { name: '← Editor' }).click()
    await page.getByRole('link', { name: 'Revisar habilidades' }).click()
    await expect(page.getByTestId('skill-catalog-unavailable')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Preparar desbloqueo' }))
      .toBeDisabled()
    await expect(page.getByTestId('skill-unlocked-count')).toHaveText('0 / 0')
  })

test.fixme('desbloquea un personaje individual con resumen y verificación', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  let selectedCodes: string[] = []
  await page.route('**/api/v1/cloud/native/prepare-characters', (route) => {
    const payload = route.request().postDataJSON()
    expect(payload.source_sha256).toBe(SHA)
    selectedCodes = payload.codes
    return route.fulfill({ json: characterPrepared(payload.codes) })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      backup_id: CHARACTER_BACKUP.id, expected_sha256: CANDIDATE, confirmation: 'SUBIR',
    })
    return route.fulfill({ json: {
      action: 'confirm', backup_id: CHARACTER_BACKUP.id, field: 'gameData.heroUnlock',
      uploaded: true, accepted: true, persisted: true, already_original: false,
      expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505,
      remote_gems: 1001, remote_value: 2, remote_characters: 2, status: 200,
      message: 'La descarga posterior coincide con el agregado subido de los personajes.',
    } })
  })

  await page.goto('/partida')
  await openCategory(page, 'personajes')
  await expect(page.getByTestId('character-unlock-section')).toBeVisible()
  await page.getByLabel('Seleccionar Ranger').check()
  await page.getByRole('button', { name: 'Preparar desbloqueo' }).click()
  expect(selectedCodes).toEqual(['Ranger'])
  await expect(page.getByRole('heading', { name: 'Revisar desbloqueo' })).toBeVisible()
  await expect(page.getByTestId('character-unlock-preview')).toContainText('Ranger')
  await expect(page.getByTestId('character-unlock-preview')).toContainText('gameData.heroUnlock.Ranger')
  await page.getByLabel(/Confirmo sobrescribir la partida/).check()
  await page.getByRole('button', { name: 'Desbloquear y verificar' }).click()
  await expect(page.getByText('Desbloqueo verificado en la nube', { exact: false })).toBeVisible()
  await expect(page.getByTestId('character-unlocked-count')).toHaveText('2 / 42')
  await expect(page.getByTestId('character-unlock-Ranger')).toContainText('Disponible')
  await expect(page.getByLabel('Seleccionar Knight')).toHaveCount(0)
})

test.fixme('desbloquea varios personajes seleccionados sin tocar los disponibles', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  let selectedCodes: string[] = []
  await page.route('**/api/v1/cloud/native/prepare-characters', (route) => {
    selectedCodes = route.request().postDataJSON().codes
    return route.fulfill({ json: characterPrepared(selectedCodes) })
  })

  await page.goto('/partida')
  await openCategory(page, 'personajes')
  await page.getByLabel('Seleccionar Ranger').check()
  await page.getByLabel('Seleccionar Mage').check()
  await expect(page.getByText('2 de 3 seleccionados.')).toBeVisible()
  await page.getByRole('button', { name: 'Preparar desbloqueo' }).click()
  expect(selectedCodes).toEqual(['Ranger', 'Mage'])
  const preview = page.getByTestId('character-unlock-preview')
  await expect(preview).toContainText('Ranger, Mage')
  await expect(preview).toContainText('Disponibles ahora')
  await expect(preview).toContainText('3 / 42')
  await expect(page.getByLabel('Seleccionar Knight')).toHaveCount(0)
})

test.fixme('selecciona todos, deselecciona y desbloquea el resto en masa', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  let selectedCodes: string[] = []
  await page.route('**/api/v1/cloud/native/prepare-characters', (route) => {
    selectedCodes = route.request().postDataJSON().codes
    return route.fulfill({ json: characterPrepared(selectedCodes) })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => route.fulfill({ json: {
    action: 'confirm', backup_id: CHARACTER_BACKUP.id, field: 'gameData.heroUnlock',
    uploaded: true, accepted: true, persisted: true, already_original: false,
    expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505,
    remote_gems: 1001, remote_value: 4, remote_characters: 4, status: 200,
    message: 'La descarga posterior coincide con el agregado subido de los personajes.',
  } }))

  await page.goto('/partida')
  await openCategory(page, 'personajes')
  await page.getByRole('button', { name: 'Seleccionar bloqueados' }).click()
  await expect(page.getByLabel('Seleccionar Ranger')).toBeChecked()
  await expect(page.getByLabel('Seleccionar Alchemist')).toBeChecked()
  await expect(page.getByText('3 de 3 seleccionados.')).toBeVisible()
  await page.getByRole('button', { name: 'Limpiar selección' }).click()
  await expect(page.getByLabel('Seleccionar Ranger')).not.toBeChecked()
  await expect(page.getByRole('button', { name: 'Preparar desbloqueo' })).toBeDisabled()
  await page.getByRole('button', { name: 'Seleccionar bloqueados' }).click()
  await page.getByRole('button', { name: 'Preparar desbloqueo' }).click()
  expect(selectedCodes).toEqual(['Ranger', 'Mage', 'Alchemist'])
  await page.getByLabel(/Confirmo sobrescribir la partida/).check()
  await page.getByRole('button', { name: 'Desbloquear y verificar' }).click()
  await expect(page.getByText('Desbloqueo verificado en la nube', { exact: false })).toBeVisible()
  await expect(page.getByTestId('character-unlocked-count')).toHaveText('4 / 42')
  await expect(page.getByTestId('character-unlock-Alchemist')).toContainText('Disponible')
})

test.fixme('muestra el resumen y desbloquea una skin con respaldo y verificación', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  let selectedSkins: Array<{ code: string; index: number }> = []
  await page.route('**/api/v1/cloud/native/prepare-skins', (route) => {
    const payload = route.request().postDataJSON()
    expect(payload.source_sha256).toBe(SHA)
    selectedSkins = payload.skins
    return route.fulfill({ json: skinPrepared(payload.skins) })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      backup_id: SKIN_BACKUP.id, expected_sha256: CANDIDATE, confirmation: 'SUBIR',
    })
    return route.fulfill({ json: {
      action: 'confirm', backup_id: SKIN_BACKUP.id, field: 'gameData.skinLock',
      uploaded: true, accepted: true, persisted: true, already_original: false,
      expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505,
      remote_gems: 1001, remote_value: 5, remote_skins: 5, remote_skills: null,
      remote_characters: null, status: 200,
      message: 'La descarga posterior coincide con el agregado subido de las skins.',
    } })
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await openCategory(page, 'skins')
  await expect(page.getByTestId('skin-unlock-section')).toBeVisible()
  await expect(page.getByTestId('skin-unlocked-count')).toHaveText('4 / 8')
  const skinsSection = page.locator('section').filter({
    has: page.getByRole('heading', { name: 'Skins' }),
  })
  await expect(skinsSection).toContainText('Identificadas')
  await expect(skinsSection).toContainText('Pendientes')
  await expect(skinsSection).toContainText('Incompatibles')
  await expect(page.getByTestId('skin-incompatible-count')).toHaveText('1')
  await expect(skinsSection).toContainText('Confirmado por el propietario · E3')
  await expect(page.getByTestId('skin-character-Knight')).toContainText('1 / 3 desbloqueadas')

  await page.getByTestId('skin-character-Knight').locator('summary').click()
  await expect(page.getByTestId('skin-option-Knight-1')).toContainText('Elite Knight')
  await expect(page.getByTestId('skin-option-Knight-1')).toContainText('Compatible')
  await page.getByLabel('Seleccionar Elite Knight de Knight').check()
  await page.getByRole('button', { name: 'Preparar desbloqueo' }).click()
  expect(selectedSkins).toEqual([{ code: 'Knight', index: 1 }])
  const preview = page.getByTestId('skin-unlock-preview')
  await expect(page.getByTestId('skin-unlock-summary')).toContainText('Knight: Elite Knight')
  await expect(preview).toContainText('gameData.skinLock.Knight[1]')
  await expect(preview).toContainText('currentSkinDatas')
  await expect(preview).not.toContainText('experimental E2')
  await page.getByLabel(/Confirmo sobrescribir la partida/).check()
  await page.getByRole('button', { name: 'Desbloquear y verificar' }).click()
  await expect(page.getByTestId('skin-unlock-result')).toContainText(
    'Desbloqueo verificado en la nube',
  )
  await expect(page.getByTestId('skin-unlocked-count')).toHaveText('5 / 8')
  await page.getByLabel('Mostrar skins').selectOption('all')
  await expect(page.getByTestId('skin-option-Knight-1')).toContainText('Desbloqueada')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test.fixme('selecciona todas las skins pendientes y prepara el lote sin renderizar tarjetas cerradas', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  let selectedSkins: Array<{ code: string; index: number }> = []
  await page.route('**/api/v1/cloud/native/prepare-skins', (route) => {
    selectedSkins = route.request().postDataJSON().skins
    return route.fulfill({ json: skinPrepared(selectedSkins) })
  })

  await page.goto('/partida')
  await openCategory(page, 'skins')
  await expect(page.getByTestId('skin-option-Knight-1')).toHaveCount(0)
  await page.getByTestId('skin-character-Knight').locator('summary').click()
  await page.getByRole('button', { name: 'Seleccionar pendientes de Knight' }).click()
  await expect(page.getByText('1 de 3 seleccionadas.')).toBeVisible()
  await expect(page.getByLabel('Seleccionar Elite Knight de Knight')).toBeChecked()
  await page.getByRole('button', { name: 'Limpiar selección' }).click()
  await expect(page.getByRole('button', { name: 'Preparar desbloqueo' }))
    .toBeDisabled()
  await page.getByRole('button', { name: 'Seleccionar pendientes', exact: true }).click()
  await page.getByRole('button', { name: 'Preparar desbloqueo' }).click()
  expect(selectedSkins).toEqual([
    { code: 'Knight', index: 1 },
    { code: 'Ranger', index: 1 },
    { code: 'Mage', index: 1 },
  ])
  await expect(page.getByTestId('skin-unlock-preview')).toContainText('7 / 8')
  await expect(page.getByTestId('skin-unlock-preview')).toContainText('Knight, Ranger, Mage')
})

test.fixme('busca skins, filtra estados y muestra posiciones incompatibles', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.goto('/partida')
  await openCategory(page, 'skins')

  await page.getByLabel('Buscar skin o personaje').fill('Elite')
  await expect(page.getByTestId('skin-character-Knight')).toContainText('1 coincidencias')
  await expect(page.getByTestId('skin-character-Ranger')).toHaveCount(0)
  await page.getByTestId('skin-character-Knight').locator('summary').click()
  await expect(page.getByTestId('skin-option-Knight-1')).toBeVisible()
  await expect(page.getByTestId('skin-option-Knight-0')).toHaveCount(0)

  await page.getByLabel('Buscar skin o personaje').fill('')
  await page.getByLabel('Mostrar skins').selectOption('incompatible')
  await expect(page.getByTestId('skin-character-Knight')).toBeVisible()
  await expect(page.getByTestId('skin-character-Ranger')).toHaveCount(0)
  await expect(page.getByTestId('skin-option-Knight-2')).toContainText('Sin dato')
  await expect(page.getByTestId('skin-option-Knight-2')).toContainText('No compatible')
  await expect(page.getByLabel('Seleccionar Lava Knight de Knight')).toHaveCount(0)

  await page.getByLabel('Mostrar skins').selectOption('unlocked')
  await expect(page.getByTestId('skin-character-Alchemist')).toBeVisible()
})

test.fixme('muestra el resumen y desbloquea una habilidad con respaldo y verificación', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  let selectedSkills: Array<{ code: string; index: number }> = []
  await page.route('**/api/v1/cloud/native/prepare-skills', (route) => {
    const payload = route.request().postDataJSON()
    expect(payload.source_sha256).toBe(SHA)
    selectedSkills = payload.skills
    return route.fulfill({ json: skillPrepared(payload.skills) })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      backup_id: SKILL_BACKUP.id, expected_sha256: CANDIDATE, confirmation: 'SUBIR',
    })
    return route.fulfill({ json: {
      action: 'confirm', backup_id: SKILL_BACKUP.id, field: 'gameData.heroSkillUnlock',
      uploaded: true, accepted: true, persisted: true, already_original: false,
      expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505,
      remote_gems: 1001, remote_value: 5, remote_skills: 5, remote_characters: null, status: 200,
      message: 'La descarga posterior coincide con el agregado subido de las habilidades.',
    } })
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await openCategory(page, 'habilidades')
  await expect(page.getByTestId('skill-unlock-section')).toBeVisible()
  await expect(page.getByTestId('skill-unlocked-count')).toHaveText('4 / 7')
  const skillsSection = page.locator('section').filter({
    has: page.getByRole('heading', { name: 'Habilidades' }),
  })
  await expect(skillsSection).toContainText('Conocidas')
  await expect(skillsSection).toContainText('Bloqueadas')
  await expect(page.getByTestId('skill-character-Knight')).toContainText('1 / 3 disponibles')
  await page.getByTestId('skill-character-Knight').locator('summary').click()
  await expect(page.getByTestId('skill-option-Knight-1')).toContainText('Superior Fire')
  await expect(skillsSection).toContainText('Confirmado por el propietario · E3')

  await page.getByLabel('Seleccionar Superior Fire de Knight').check()
  await page.getByRole('button', { name: 'Preparar desbloqueo' }).click()
  expect(selectedSkills).toEqual([{ code: 'Knight', index: 1 }])
  await expect(page.getByRole('heading', { name: 'Revisar desbloqueo' })).toBeVisible()
  const preview = page.getByTestId('skill-unlock-preview')
  await expect(page.getByTestId('skill-unlock-summary')).toContainText('Knight: Superior Fire')
  await expect(preview).toContainText('gameData.heroSkillUnlock.Knight[1]')
  await expect(preview).toContainText('Respaldo cifrado creado')
  await page.getByLabel(/Confirmo sobrescribir la partida/).check()
  await page.getByRole('button', { name: 'Desbloquear y verificar' }).click()
  await expect(page.getByTestId('skill-unlock-result')).toContainText(
    'Desbloqueo verificado en la nube',
  )
  await expect(page.getByTestId('skill-unlocked-count')).toHaveText('5 / 7')
  await expect(page.getByTestId('skill-option-Knight-1')).toContainText('Disponible')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test.fixme('selecciona todas las habilidades bloqueadas, deselecciona y prepara el lote', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  let selectedSkills: Array<{ code: string; index: number }> = []
  await page.route('**/api/v1/cloud/native/prepare-skills', (route) => {
    selectedSkills = route.request().postDataJSON().skills
    return route.fulfill({ json: skillPrepared(selectedSkills) })
  })

  await page.goto('/partida')
  await openCategory(page, 'habilidades')
  await page.getByLabel('Buscar personaje').fill('Ranger')
  await page.getByLabel('Filtro').selectOption('all')
  await expect(page.getByTestId('skill-character-Ranger')).toContainText('1 / 2 disponibles')
  await page.getByLabel('Buscar personaje').fill('')
  await page.getByLabel('Filtro').selectOption('pending')
  await page.getByTestId('skill-character-Knight').locator('summary').click()
  await page.getByTestId('skill-character-Ranger').locator('summary').click()

  await page.getByRole('button', { name: 'Seleccionar bloqueadas', exact: true }).click()
  await expect(page.getByText('3 de 3 seleccionadas.')).toBeVisible()
  await expect(page.getByLabel('Seleccionar Superior Fire de Knight')).toBeChecked()
  await expect(page.getByLabel('Seleccionar Shield Bash de Knight')).toBeChecked()
  await expect(page.getByLabel("Seleccionar Hunter's Mark de Ranger")).toBeChecked()
  await page.getByRole('button', { name: 'Limpiar selección' }).click()
  await expect(page.getByRole('button', { name: 'Preparar desbloqueo' }))
    .toBeDisabled()
  await page.getByRole('button', { name: 'Seleccionar bloqueadas', exact: true }).click()
  await page.getByRole('button', { name: 'Preparar desbloqueo' }).click()
  expect(selectedSkills).toEqual([
    { code: 'Knight', index: 1 },
    { code: 'Knight', index: 2 },
    { code: 'Ranger', index: 1 },
  ])
  await expect(page.getByTestId('skill-unlock-preview')).toContainText('7 / 7')
  await expect(page.getByTestId('skill-unlock-preview')).toContainText('Knight, Ranger')
})

test.fixme('filtra habilidades pendientes y muestra posiciones sin dato', async ({ page }) => {
  const withUnknown = {
    ...REPORT,
    characters: {
      ...REPORT.characters,
      items: REPORT.characters.items.map((character) => character.code === 'Mage'
        ? { ...character, skills: [], skill_options: [{ index: 0, name: 'Mage Skill' }] }
        : character),
    },
  }
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: withUnknown } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: EMPTY_NATIVE_HISTORY }))
  await page.goto('/partida')
  await openCategory(page, 'habilidades')
  await page.getByLabel('Filtro').selectOption('incomplete')
  await expect(page.getByTestId('skill-character-Mage')).toContainText('sin dato')
  await page.getByTestId('skill-character-Mage').locator('summary').click()
  await expect(page.getByTestId('skill-option-Mage-0')).toContainText('Sin dato')
  await expect(page.getByLabel('Seleccionar Mage Skill de Mage')).toHaveCount(0)
  await page.getByLabel('Buscar personaje').fill('NoExiste')
  await expect(page.getByTestId('skill-empty-filter')).toBeVisible()
})

test('las rutas antiguas llevan a Partida y no permiten cargar un archivo local', async ({ page }) => {
  await mockBase(page)
  for (const path of ['/importar', '/exportar']) {
    await page.goto(path)
    await expect(page).toHaveURL(/\/cuentas\/nueva$/)
    await expect(page.getByRole('heading', { name: 'Añadir cuenta' })).toBeVisible()
    await expect(page.locator('input[type=file]')).toHaveCount(0)
  }
})

test('verifica y restaura un respaldo desde Partida con una confirmación clara', async ({ page }) => {
  let restoreCalls = 0
  let historyCalls = 0
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, gems: 1002, downloaded_at: '2026-11-23T20:00:00Z' } } })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => {
    historyCalls += 1
    return route.fulfill({
      json: { backups: [{
        id: BACKUP.id, created_at: BACKUP.created_at, field: 'gems', kind: 'edit', status: 'verified',
        original_value: 1001, candidate_value: 1002, changed: true, original_size: BACKUP.original_size,
        restoration: restoreCalls ? 'verified' : null, integrity: 'verified', can_restore: true,
      }], total: 1, listed: 1, limit: 25, unreadable: 0, next_cursor: null },
    })
  })
  await page.route('**/api/v1/cloud/native/save', (route) => route.fulfill({
    json: { ...SAVE, downloaded_at: '2026-11-23T20:20:00Z' },
  }))
  await page.route('**/api/v1/cloud/native/verify', (route) => {
    expect(route.request().postDataJSON()).toEqual({ backup_id: BACKUP.id })
    return route.fulfill({ json: { backup_id: BACKUP.id, matches_original: false, matches_candidate: true } })
  })
  await page.route('**/api/v1/cloud/native/restore-history', (route) => {
    restoreCalls += 1
    expect(route.request().postDataJSON()).toEqual({
      backup_id: BACKUP.id, confirmation: 'RESTAURAR', expected_sha256: SHA,
    })
    return route.fulfill({ json: {
      action: 'restore', backup_id: BACKUP.id, persisted: true, remote_gems: 1001,
      historical: true, preventive_backup_id: 'd'.repeat(32),
    } })
  })
  await page.goto('/partida')
  await page.locator('.partida-backup summary').click()
  await page.getByRole('button', { name: 'Verificar contra la nube' }).click()
  await expect(page.getByText('La nube coincide con la edición guardada.')).toBeVisible()
  await page.getByRole('button', { name: 'Restaurar esta versión' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Se reemplazará el progreso actual')
  await expect(dialog).toContainText('respaldo preventivo')
  await dialog.getByRole('button', { name: 'Cancelar' }).click()
  expect(restoreCalls).toBe(0)
  await page.getByRole('button', { name: 'Restaurar esta versión' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Restaurar esta versión' }).click()
  await expect(page.getByText('Restauración verificada: la nube contiene exactamente la versión elegida.')).toBeVisible()
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,001')
  await expect(page.locator('.partida-backup-state').first()).toContainText('Restauración verificada')
  await expect(page.getByRole('region', { name: 'Partida en la nube' }).locator('time')).toHaveAttribute('datetime', '2026-11-23T20:20:00Z')
  expect(restoreCalls).toBe(1)
  expect(historyCalls).toBe(2)
})

test('permite reintentar una descarga y conserva el resultado al abrir el Editor', async ({ page }) => {
  let attempts = 0
  let finishDownload = () => {}
  const pendingDownload = new Promise<void>((resolve) => { finishDownload = resolve })
  await mockBase(page, { ...BASE_CONFIG, session: ACTIVE })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({
    json: EMPTY_NATIVE_HISTORY,
  }))
  await page.route('**/api/v1/cloud/native/save', async (route) => {
    attempts += 1
    if (attempts === 1) {
      await route.fulfill({ status: 502, json: { error: { message: 'internal diagnostic', issues: [] } } })
      return
    }
    await pendingDownload
    await route.fulfill({ json: { ...SAVE, downloaded_at: '2026-11-23T20:00:00Z' } })
  })

  await page.goto('/partida')
  await expect(page.getByRole('alert')).toContainText('No se pudo descargar la partida.')
  await expect(page.locator('body')).not.toContainText('internal diagnostic')
  await page.getByRole('button', { name: 'Descargar partida' }).click()
  await expect(page.getByRole('button', { name: 'Descargando…' })).toBeDisabled()
  finishDownload()
  await expect(page.getByText('Copia descargada')).toBeVisible()
  await expect(page.getByText('Última descarga')).toBeVisible()
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toHaveValue('1001')
})

test('descarta el historial anterior si la cuenta cambia mientras carga', async ({ page }) => {
  const firstId = 'a'.repeat(32)
  const secondId = 'b'.repeat(32)
  let firstRequested = false
  let releaseResponse = () => {}
  const pending = new Promise<void>((resolve) => { releaseResponse = resolve })
  const first = { ...ACTIVE, account_id: firstId }
  const second = {
    ...ACTIVE, account_id: secondId,
    account: { ...ACTIVE.account, email: 'other@example.test', label: SECOND_PROFILE.label },
  }
  await mockBase(page, {
    ...BASE_CONFIG,
    accounts: [{ ...first, id: firstId }, { ...second, id: secondId }],
    session: first,
  })
  await page.route('**/api/v1/cloud/native/session', (route) => {
    const selected = route.request().headers()['x-sk-account']
    return route.fulfill({ json: selected === secondId ? second : first })
  })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, async (route) => {
    if (route.request().headers()['x-sk-account'] === secondId) {
      return route.fulfill({ json: EMPTY_NATIVE_HISTORY })
    }
    firstRequested = true
    await pending
    await route.fulfill({
      json: { ...EMPTY_NATIVE_HISTORY, total: 1, listed: 1,
        backups: [{ id: BACKUP.id, created_at: BACKUP.created_at, field: 'gems', status: 'verified' }] },
    }).catch(() => undefined)
  })
  await page.goto(`/cuentas/${firstId}/partida`)
  await expect.poll(() => firstRequested).toBe(true)
  await page.goto('/')
  await page.getByRole('link', { name: 'Abrir partida de other@example.test' }).click()
  await expect(page).toHaveURL(new RegExp(`/cuentas/${secondId}/partida$`))
  releaseResponse()
  await expect(page.getByText('Esta cuenta todavía no tiene respaldos.')).toBeVisible()
  await expect(page.getByRole('img', { name: /Subida verificada/ })).toHaveCount(0)
})
