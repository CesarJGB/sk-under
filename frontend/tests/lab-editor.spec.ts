import { expect, test, type Page } from '@playwright/test'

const CURRENT_SHA = '1'.repeat(64)
const CANDIDATE_SHA = '2'.repeat(64)
const ADMIN = 'a'.repeat(32)
const BACKUP_ID = 'b'.repeat(32)
const backup = {
  id: BACKUP_ID,
  created_at: '2026-11-23T20:00:00Z',
  changed: true,
  original_size: 505,
  original_sha256: CURRENT_SHA,
  original_gems: 1000,
  candidate_size: 505,
  candidate_sha256: CANDIDATE_SHA,
  candidate_gems: 1001,
  remote_source: 'modern-cloud',
  remote_size: 505,
  remote_sha256: CURRENT_SHA,
}
const status = {
  mode: 'live', read_ready: true, write_enabled: true, write_ready: true,
  admin_configured: true, admin_required: true, backup_count: 1,
  min_gems: 0, max_gems: 2_147_483_647,
  message: 'Laboratorio real con escritura administrativa habilitada.',
}

async function mockLab(page: Page, overrides: { status?: object; backups?: object[] } = {}) {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1048576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/cloud/lab/status', (route) => route.fulfill({
    json: { ...status, ...overrides.status },
  }))
  await page.route('**/api/v1/cloud/lab/backups', (route) => route.fulfill({
    json: { backups: overrides.backups ?? [backup] },
  }))
  await page.route('**/api/v1/cloud/lab/save', (route) => route.fulfill({
    json: {
      remote: { source: 'modern-cloud', size: 505, sha256: CURRENT_SHA },
      gems: 1000, size: 505, sha256: CURRENT_SHA, serialzed_version: 1,
    },
  }))
  await page.route('**/api/v1/cloud/lab/prepare', (route) => route.fulfill({
    json: {
      remote: { source: 'modern-cloud', size: 505, sha256: CURRENT_SHA },
      backup,
      original_gems: 1000,
      new_gems: 1001,
      changed: true,
      candidate_size: 505,
      candidate_sha256: CANDIDATE_SHA,
      byte_diff: {
        original_size: 505, modified_size: 505, first_difference: 2419,
        common_prefix: 2419, common_suffix: 334, changed_original_bytes: 1,
        changed_modified_bytes: 1, original_sha256: CURRENT_SHA, modified_sha256: CANDIDATE_SHA,
      },
      validation: {
        valid: true, structure_valid: true, only_gems_changed: true,
        message: 'Solo cambia gameData.gems.',
      },
    },
  }))
  await page.route('**/api/v1/cloud/lab/verify', (route) => route.fulfill({
    json: {
      backup_id: BACKUP_ID, matches_candidate: true, matches_original: false,
      remote_sha256: CANDIDATE_SHA, remote_size: 505, remote_gems: 1001,
      expected_candidate_sha256: CANDIDATE_SHA, expected_original_sha256: CURRENT_SHA,
      message: 'La nube conserva exactamente el candidato respaldado.',
    },
  }))
}

test('carga, prepara, confirma y verifica una modificación de gemas', async ({ page }) => {
  await mockLab(page)
  const seen: { headers?: Record<string, string>; body?: unknown } = {}
  await page.route('**/api/v1/cloud/lab/confirm', async (route) => {
    const request = route.request()
    seen.headers = request.headers()
    seen.body = request.postDataJSON()
    await route.fulfill({
      json: {
        action: 'confirm', backup_id: BACKUP_ID, uploaded: true, accepted: true,
        persisted: true, already_original: false, expected_sha256: CANDIDATE_SHA,
        remote_sha256: CANDIDATE_SHA, remote_size: 505, remote_gems: 1001,
        status: 200, message: 'La descarga posterior coincide con el agregado subido.',
      },
    })
  })

  await page.goto('/partida')
  await expect(page.getByRole('heading', { name: 'Editor de partida' })).toBeVisible()
  await expect(page.getByText('Laboratorio real · escritura habilitada')).toBeVisible()

  await page.getByRole('button', { name: 'Cargar partida de laboratorio' }).click()
  await expect(page.getByTestId('lab-current-gems')).toHaveText('1,000')
  await page.locator('#lab-new-gems').fill('1001')
  await page.getByRole('button', { name: 'Preparar modificación y respaldo' }).click()

  await expect(page.getByText('Solo cambia gameData.gems.')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Edición y vista previa' }).getByText('1000 → 1001', { exact: true })).toBeVisible()
  await expect(page.getByText(BACKUP_ID).first()).toBeVisible()

  const confirm = page.getByRole('button', { name: 'Subir partida modificada y verificar' })
  await expect(confirm).toBeDisabled()
  await page.locator('#lab-admin-token').fill(ADMIN)
  await page.locator('#lab-confirm-phrase').fill('SUBIR')
  await page.getByRole('checkbox').check()
  await expect(confirm).toBeEnabled()
  await confirm.click()

  await expect(page.getByText('La descarga posterior coincide con el agregado subido.')).toBeVisible()
  await expect(page.getByText('Gemas remotas: 1001.', { exact: false })).toBeVisible()
  expect(seen.headers?.['x-sk-cloud-admin']).toBe(ADMIN)
  expect(seen.body).toMatchObject({ backup_id: BACKUP_ID, expected_sha256: CANDIDATE_SHA, confirmation: 'SUBIR' })

  await page.getByRole('button', { name: 'Verificar persistencia' }).click()
  await expect(page.getByText('La nube conserva exactamente el candidato respaldado.', { exact: false })).toBeVisible()
})

test('la vista previa bloquea la escritura cuando el laboratorio es de solo lectura', async ({ page }) => {
  await mockLab(page, {
    status: { mode: 'read_only', write_enabled: false, write_ready: false },
  })
  await page.goto('/partida')
  await page.getByRole('button', { name: 'Cargar partida de laboratorio' }).click()
  await page.locator('#lab-new-gems').fill('1001')
  await page.getByRole('button', { name: 'Preparar modificación y respaldo' }).click()
  await expect(page.getByText('Solo cambia gameData.gems.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Confirmar subida administrativa' })).toBeVisible()
  await expect(page.getByText('El servidor tiene la escritura deshabilitada', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Subir partida modificada y verificar' })).toBeDisabled()
})

test('mantiene el editor dentro del ancho móvil', async ({ page }) => {
  await mockLab(page)
  await page.setViewportSize({ width: 320, height: 760 })
  await page.goto('/partida')
  await page.getByRole('button', { name: 'Cargar partida de laboratorio' }).click()
  await expect(page.getByTestId('lab-current-gems')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
})

test('no permite confirmar sin frase y sin autorización administrativa', async ({ page }) => {
  await mockLab(page)
  await page.goto('/partida')
  await page.getByRole('button', { name: 'Cargar partida de laboratorio' }).click()
  await page.locator('#lab-new-gems').fill('1001')
  await page.getByRole('button', { name: 'Preparar modificación y respaldo' }).click()
  const confirm = page.getByRole('button', { name: 'Subir partida modificada y verificar' })
  await page.locator('#lab-confirm-phrase').fill('SUBIR')
  await page.getByRole('checkbox').check()
  await expect(confirm).toBeDisabled()
  await page.locator('#lab-admin-token').fill(ADMIN)
  await expect(confirm).toBeEnabled()
  await page.locator('#lab-confirm-phrase').fill('NO')
  await expect(confirm).toBeDisabled()
})

test('pide el token de acceso antes de consultar el laboratorio', async ({ page }) => {
  let statusCalls = 0
  let authorization = ''
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'token', max_file_bytes: 1048576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/cloud/lab/status', (route) => {
    statusCalls += 1
    authorization = route.request().headers()['authorization'] ?? ''
    return route.fulfill({ json: status })
  })
  await page.route('**/api/v1/cloud/lab/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.goto('/partida')
  await expect(page.locator('#lab-access-token')).toBeVisible()
  expect(statusCalls).toBe(0)
  await page.locator('#lab-access-token').fill('t'.repeat(32))
  await expect(page.getByText('Laboratorio real · escritura habilitada')).toBeVisible()
  expect(statusCalls).toBe(1)
  expect(authorization).toBe(`Bearer ${'t'.repeat(32)}`)
})

test('muestra el laboratorio no configurado sin bloquear el estado', async ({ page }) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1048576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/cloud/lab/status', (route) => route.fulfill({
    json: {
      mode: 'disabled', read_ready: false, write_enabled: false, write_ready: false,
      admin_configured: false, admin_required: true, backup_count: 0,
      min_gems: 0, max_gems: 2_147_483_647,
      message: 'El laboratorio de nube no está configurado en el servidor.',
    },
  }))
  await page.route('**/api/v1/cloud/lab/backups', (route) => route.fulfill({
    status: 503, json: { error: { code: 'cloud_lab_not_configured', message: 'Sin configurar.', issues: [] } },
  }))
  await page.goto('/partida')
  await expect(page.getByText('Laboratorio no configurado', { exact: true })).toBeVisible()
  await expect(page.getByText('El laboratorio de nube no está configurado en el servidor.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cargar partida de laboratorio' })).toBeDisabled()
})
