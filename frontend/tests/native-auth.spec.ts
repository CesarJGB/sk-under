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
  installation_ready: true, write_enabled: true, write_ready: true,
  min_gems: 0, max_gems: 2_147_483_647, save: null, save_error: null,
}
const BASE_CONFIG = {
  available: true, enabled: true, configured: true, write_enabled: true, secure: false,
  min_gems: 0, max_gems: 2_147_483_647, login_available: true,
  profiles: [PROFILE], distributions: DISTRIBUTIONS,
  session: { active: false, reason: 'none' }, problem_code: null, message: null,
}
const BACKUP = {
  id: 'c'.repeat(32), created_at: '2026-11-23T20:00:00Z', changed: true,
  original_size: 505, original_sha256: SHA, original_gems: 1001,
  candidate_size: 505, candidate_sha256: CANDIDATE, candidate_gems: 1002,
  remote_source: 'modern-cloud', remote_size: 505, remote_sha256: SHA,
}
const PREPARED = {
  remote: { source: 'modern-cloud', size: 505, sha256: SHA }, backup: BACKUP,
  original_gems: 1001, new_gems: 1002, changed: true,
  candidate_size: 505, candidate_sha256: CANDIDATE,
  byte_diff: {
    original_size: 505, modified_size: 505, first_difference: 1, common_prefix: 1,
    common_suffix: 503, changed_original_bytes: 1, changed_modified_bytes: 1,
    original_sha256: SHA, modified_sha256: CANDIDATE,
  },
  validation: { valid: true, structure_valid: true, only_gems_changed: true, message: 'Solo cambia gameData.gems.' },
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
  await page.getByLabel('Correo electrónico de ChillyRoom').fill(email)
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
  await expect(page.getByText('Identidad verificada')).toBeVisible()
  await expect(page.getByTestId('native-current-gems')).toHaveText('1,001')
  await page.getByLabel('Nueva cantidad de gemas').fill('1002')
  await page.getByRole('button', { name: 'Preparar edición' }).click()
  await expect(page.getByText('+1', { exact: true })).toBeVisible()
  const confirm = page.getByRole('button', { name: 'Subir y verificar' })
  await expect(confirm).toBeDisabled()
  await page.getByRole('checkbox').check()
  await confirm.click()
  await expect(page.getByText('La descarga posterior coincide con el agregado subido.')).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page.getByRole('heading', { name: 'Iniciar sesión en ChillyRoom' })).toBeVisible()
  await expect(page.getByTestId('native-current-gems')).toHaveCount(0)
})

test('completa la configuración de instalación pendiente y habilita el editor', async ({ page }) => {
  let installed = false
  await mockBase(page)
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({
    json: installed ? { ...BASE_CONFIG, session: { ...ACTIVE, save: SAVE } } : BASE_CONFIG,
  }))
  await page.route('**/api/v1/cloud/native/login', (route) => route.fulfill({
    json: { ...ACTIVE, installation_ready: false, save: null, save_error: 'native_installation_required' },
  }))
  await page.route('**/api/v1/cloud/native/installation', (route) => {
    expect(route.request().postDataJSON()).toEqual({ unique_id: 'unique-owner' })
    installed = true
    return route.fulfill({ json: { ...ACTIVE, save: SAVE } })
  })
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))

  await page.goto('/partida')
  await submitLogin(page)
  await expect(page.getByRole('heading', { name: 'Configuración de instalación pendiente' })).toBeVisible()
  await page.getByLabel('Identificador de instalación').fill('unique-owner')
  await page.getByRole('button', { name: 'Completar instalación' }).click()
  await expect(page.getByTestId('native-current-gems')).toHaveText('1,001')
  await expect(page.getByRole('heading', { name: 'Configuración de instalación pendiente' })).toHaveCount(0)
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
  await expect(page.getByLabel('Correo electrónico de ChillyRoom')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible()
})

test('permite elegir el perfil cuando hay más de uno', async ({ page }) => {
  await mockBase(page, { ...BASE_CONFIG, profiles: [PROFILE, SECOND_PROFILE] })
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
  await expect(page.getByText('La escritura está deshabilitada en el servidor.', { exact: false })).toBeVisible()
  await page.getByLabel('Nueva cantidad de gemas').fill('1002')
  await page.getByRole('button', { name: 'Preparar edición' }).click()
  await expect(page.getByText('+1', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Subir y verificar' })).toHaveCount(0)
})
