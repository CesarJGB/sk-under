import { expect, test, type Page } from '@playwright/test'

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
  { id: 'ios-global', label: 'iOS Global (IOS)', platform: 'ios', game_version: '8.8.0', enabled: false, validated: false, note: 'No validada.' },
  { id: 'ios-vietnam', label: 'iOS Vietnam (IOS_VNM)', platform: 'ios', game_version: '8.8.0', enabled: false, validated: false, note: 'No validada.' },
  { id: 'ios-china', label: 'iOS China (IOS_CN)', platform: 'ios', game_version: '8.8.0', enabled: false, validated: false, note: 'No validada.' },
  { id: 'taptap', label: 'TapTap', platform: 'android', game_version: '8.8.0', enabled: false, validated: false, note: 'No validada.' },
]
const SAVE = { verified: true, bytes: 505, sha256: SHA, gems: 1001, sections: 17, remote_source: 'modern-cloud' }
const ACTIVE = {
  active: true, identity_verified: true,
  account: {
    label: PROFILE.label, distribution: 'android-global',
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
    server_authority: 'unknown', status: 'read_only', evidence: 'E2',
    transaction_validated: false, missing_proof: 'Falta una transacción legítima con saldo positivo.',
    fields: [], distinct_collections: {},
  },
  characters: {
    items: [{
      code: 'Knight', name: 'Knight', catalog_index: 0, unlocked: true, level: 2,
      level_max: null, level_status: 'not_validated', selected_skill: 0,
      skills: [{ key: 0, unlocked: true, name: 'Dual Wield' }],
      skill_options: [{ index: 0, name: 'Dual Wield' }, { index: 1, name: 'Superior Fire' }],
      selected_skin: 0, equipped_skin: { key: 0, state: 1, name: 'Knight' },
      skins_recorded: 2, skins_status: 'not_validated',
    }],
    counts: { characters: 42, unlocked: 1, selected_skins: 1 },
    level_status: 'not_validated', skins_status: 'not_validated',
    catalog: { version: '8.8.0', source: 'SKDFE', characters: 42 },
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

async function mockBase(page: Page, config: object = BASE_CONFIG) {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1_048_576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({ json: config }))
}

async function mockEditor(page: Page, session: object = ACTIVE) {
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({ json: session }))
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.route('**/api/v1/cloud/native/prepare', (route) => {
    expect(route.request().postDataJSON()).toEqual({ new_gems: 1002, source_sha256: SHA })
    return route.fulfill({ json: PREPARED })
  })
}

async function submitLogin(page: Page, email = 'holder@example.test', password = 'fixture-password') {
  await page.getByLabel('Correo electrónico').fill(email)
  await page.getByLabel('Contraseña', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1_048_576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
})

test('muestra las seis distribuciones, solo Android Global habilitada y alterna la contraseña', async ({ page }) => {
  await mockBase(page)
  await page.setViewportSize({ width: 320, height: 730 })
  await page.goto('/partida')
  await expect(page.getByRole('heading', { name: 'Iniciar sesión en ChillyRoom' })).toBeVisible()
  await expect(page.getByLabel('Distribución')).toHaveValue('android-global')
  await expect(page.getByRole('option', { name: /iOS Global/ })).toBeDisabled()
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

test('inicia sesión, descarga, prepara, confirma y cierra sesión', async ({ page }) => {
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
  await expect(page.getByTestId('native-current-gems')).toHaveText('1,001')
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
  await expect(page.getByTestId('native-current-gems')).toHaveText('1,002')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page.getByRole('heading', { name: 'Iniciar sesión en ChillyRoom' })).toBeVisible()
  await expect(page.getByTestId('native-current-gems')).toHaveCount(0)
})

for (const [code, message] of [
  ['unsupported_gems_structure', 'La versión o los tipos de los campos de gemas son incompatibles con el editor.'],
  ['unknown_gems_dependencies', 'El saldo depende de contadores ausentes o fuera del intervalo compatible.'],
  ['inconsistent_gems_balance', 'Primero prepara una edición con el saldo conciliado (1000).'],
  ['network_error', 'No se pudo conectar con la API de SK-Under. Revisa tu conexión.'],
]) {
  test(`explica el error de preparación ${code}`, async ({ page }) => {
    await mockBase(page)
    await mockEditor(page, { ...ACTIVE, save: SAVE })
    await page.route('**/api/v1/cloud/native/prepare', (route) => code === 'network_error'
      ? route.abort('connectionrefused')
      : route.fulfill({ status: 422, json: { error: { code, message } } }))
    await page.goto('/partida')
    await submitLogin(page)
    await page.getByRole('link', { name: 'Abrir Editor' }).click()
    await page.getByLabel('Nueva cantidad de gemas').fill('1002')
    await page.getByRole('button', { name: 'Preparar edición' }).click()
    await expect(page.getByText(message, { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Subir y verificar' })).toHaveCount(0)
  })
}

test('no pide identificadores y descarga con la identidad generada por el servidor', async ({ page }) => {
  await mockBase(page)
  await mockEditor(page, { ...ACTIVE, save: SAVE })
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.goto('/partida')
  await expect(page.getByLabel('Identificador de instalación')).toHaveCount(0)
  await expect(page.getByLabel('Perfil de instalación')).toHaveCount(0)
  await submitLogin(page)
  await expect(page.getByTestId('native-current-gems')).toHaveText('1,001')
  await expect(page.getByLabel('Cuenta conectada')).toBeVisible()
})

test('explica la espera de vinculación de un dispositivo nuevo', async ({ page }) => {
  await mockBase(page)
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({
    json: {
      ...ACTIVE, save: null, save_error: 'native_device_binding_throttled',
      binding_wait_until: '2026-11-25T08:00:00Z',
    },
  }))
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
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
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.route('**/api/v1/cloud/native/save', (route) => {
    expired = true
    return route.fulfill({
      status: 401,
      json: { error: { code: 'native_session_expired', message: 'La sesión caducó.', issues: [] } },
    })
  })

  await page.goto('/partida')
  await submitLogin(page)
  await page.getByRole('button', { name: 'Descargar partida' }).click()
  await expect(page.getByRole('heading', { name: 'Iniciar sesión en ChillyRoom' })).toBeVisible()
  await expect(page.getByText('La sesión caducó. Inicia sesión de nuevo.')).toBeVisible()
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
    await route.fulfill({
      json: {
        ...ACTIVE,
        account: { label: SECOND_PROFILE.label, distribution: 'android-global', distribution_label: 'Android Global (GP)', platform: 'android' },
        save: SAVE,
      },
    })
  })
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.goto('/partida')
  await page.getByLabel('Perfil de instalación').selectOption(SECOND_PROFILE.id)
  await submitLogin(page)
  expect(requested).toBe(SECOND_PROFILE.id)
  await expect(page.getByText(SECOND_PROFILE.label, { exact: false }).first()).toBeVisible()
})

test('mantiene el editor en solo lectura cuando la escritura está deshabilitada', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, write_enabled: false })
  await mockEditor(page, { ...ACTIVE, write_enabled: false, write_ready: false, save: SAVE })
  await page.goto('/partida')
  await submitLogin(page)
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByText('La subida a la nube está deshabilitada.', { exact: false })).toBeVisible()
  await page.getByLabel('Nueva cantidad de gemas').fill('1002')
  await page.getByRole('button', { name: 'Preparar edición' }).click()
  await expect(page.getByText('+1', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Subir y verificar' })).toHaveCount(0)
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
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({
    json: { ...ACTIVE, save: null, save_error: 'native_no_cloud_save' },
  }))
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.goto('/partida')
  await submitLogin(page)
  await expect(page.getByText('Sin partida en la nube', { exact: true })).toBeVisible()
  await expect(page.getByText('Guarda una copia desde Soul Knight', { exact: false })).toBeVisible()
})

test('navega por el flujo de nube y mantiene el borrador solo para la cuenta activa', async ({ page }) => {
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
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({
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
  await expect(page.getByTestId('native-current-gems')).toHaveText('42')
  await expect(page.getByText('Esta cuenta todavía no tiene respaldos.')).toBeVisible()
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByLabel('Nueva cantidad de gemas')).toHaveValue('42')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320)
})

test('muestra fichas, recursos y personajes del informe en solo lectura', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, report: REPORT } } })
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByTestId('fish-chip-balance')).toHaveText('3')
  await expect(page.getByText('Falta una transacción legítima con saldo positivo.')).toBeVisible()
  await expect(page.getByTestId('resource-group-materials')).toContainText('wood × 4')
  await expect(page.getByTestId('character-row-Knight')).toContainText('Disponible')
  await expect(page.getByTestId('character-level-Knight')).toHaveText('2')
  await expect(page.getByTestId('character-row-Knight')).toContainText('Dual Wield')
  await expect(page.getByTestId('character-row-Knight')).toContainText('Knight')
  await expect(page.getByLabel('Nueva cantidad de gemas')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('las rutas antiguas llevan a Partida y no permiten cargar un archivo local', async ({ page }) => {
  await mockBase(page)
  for (const path of ['/importar', '/exportar']) {
    await page.goto(path)
    await expect(page).toHaveURL(/\/partida$/)
    await expect(page.getByRole('heading', { name: 'Partida', exact: true })).toBeVisible()
    await expect(page.locator('input[type=file]')).toHaveCount(0)
  }
})

test('verifica y restaura un respaldo desde Partida con una confirmación', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, session: { ...ACTIVE, save: { ...SAVE, gems: 1002 } } })
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({
    json: { backups: [{ ...BACKUP, confirmed: true }] },
  }))
  await page.route('**/api/v1/cloud/native/verify', (route) => {
    expect(route.request().postDataJSON()).toEqual({ backup_id: BACKUP.id })
    return route.fulfill({ json: { backup_id: BACKUP.id, matches_original: false, matches_candidate: true } })
  })
  await page.route('**/api/v1/cloud/native/restore', (route) => {
    expect(route.request().postDataJSON()).toEqual({ backup_id: BACKUP.id, confirmation: 'RESTAURAR' })
    return route.fulfill({ json: {
      action: 'restore', backup_id: BACKUP.id, persisted: true, remote_gems: 1001,
    } })
  })
  await page.goto('/partida')
  await page.getByText('1,001 gemas', { exact: true }).click()
  await page.getByRole('button', { name: 'Verificar nube' }).click()
  await expect(page.getByText('La nube coincide con la edición guardada.')).toBeVisible()
  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain('Se reemplazará la partida en la nube.')
    await dialog.accept()
  })
  await page.getByRole('button', { name: 'Restaurar respaldo' }).click()
  await expect(page.getByText('Respaldo restaurado y verificado en la nube.')).toBeVisible()
  await expect(page.getByTestId('native-current-gems')).toHaveText('1,001')
  await expect(page.getByRole('link', { name: 'Abrir Editor' })).toHaveCount(0)
})

test('permite reintentar una descarga y conserva el resultado al abrir el Editor', async ({ page }) => {
  let attempts = 0
  let finishDownload = () => {}
  const pendingDownload = new Promise<void>((resolve) => { finishDownload = resolve })
  await mockBase(page, { ...BASE_CONFIG, session: ACTIVE })
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
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
  await page.getByRole('button', { name: 'Descargar partida' }).click()
  await expect(page.getByRole('alert')).toContainText('No se pudo descargar la partida.')
  await expect(page.locator('body')).not.toContainText('internal diagnostic')
  await page.getByRole('button', { name: 'Descargar partida' }).click()
  await expect(page.getByRole('button', { name: 'Descargando…' })).toBeDisabled()
  finishDownload()
  await expect(page.getByText('Copia verificada')).toBeVisible()
  await expect(page.getByText('Última descarga')).toBeVisible()
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByLabel('Nueva cantidad de gemas')).toHaveValue('1001')
})
