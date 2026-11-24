import { expect, test } from '@playwright/test'

const first = { id: 'first', label: 'Cuenta A', platform: 'android-global', connected: true, write_ready: true }
const second = { id: 'second', label: 'Cuenta B', platform: 'android-global', connected: false, write_ready: false }
const status = {
  configured: true, message: null, password_login_available: false,
  login_message: 'El inicio de sesión con correo y contraseña de ChillyRoom aún no está disponible.',
  min_gems: 0, max_gems: 2147483647,
}
const sha256 = 'a'.repeat(64)
const backup = {
  id: 'backup-first', created_at: '2026-11-23T21:00:00Z',
  original_size: 1000, original_gems: 1001, candidate_gems: 1002, confirmed: false,
}

test('informa el bloqueo de ChillyRoom, conserva Android Global y protege el formulario', async ({ page }) => {
  await page.route('**/api/v1/cloud/accounts', (route) => route.fulfill({
    json: { ...status, configured: false, message: 'Configura el origen seguro para las cuentas.', accounts: [] },
  }))
  await page.setViewportSize({ width: 320, height: 730 })
  await page.goto('/partida/vinculadas')
  await expect(page.getByText(status.login_message)).toBeVisible()
  await expect(page.getByText('El acceso a cuentas vinculadas no está disponible en este momento.')).toBeVisible()
  await expect(page.getByLabel('Plataforma')).toHaveValue('android-global')
  await expect(page.getByRole('option', { name: 'iOS · No disponible' })).toBeDisabled()
  await expect(page.getByLabel('Contraseña')).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Iniciar sesión' })).toBeDisabled()
  await expect(page.locator('body')).not.toContainText('Token administrativo')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('impide enviar el formulario cuando el editor se sirve por HTTP', async ({ page }) => {
  let requests = 0
  await page.route('**/api/v1/cloud/accounts', (route) => route.fulfill({
    json: { ...status, password_login_available: true, login_message: '', accounts: [] },
  }))
  await page.route('**/api/v1/cloud/accounts/login', async (route) => {
    requests += 1
    await route.abort()
  })
  await page.goto('/partida/vinculadas')
  await page.getByLabel('Correo electrónico de ChillyRoom').fill('fixture@example.test')
  await page.getByLabel('Contraseña').fill('fixture-password')
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('El inicio de sesión requiere HTTPS en el editor y en la API.')).toBeVisible()
  await expect(page.getByLabel('Contraseña')).toHaveValue('')
  expect(requests).toBe(0)
})

test('vincula, confirma con cookie y reinicia la vista al cambiar de cuenta', async ({ page }) => {
  let linked = false
  await page.route('**/api/v1/cloud/accounts', (route) => route.fulfill({
    json: { ...status, accounts: linked ? [first, second] : [] },
  }))
  await page.route('**/api/v1/cloud/accounts/claim', async (route) => {
    linked = true
    await route.fulfill({ json: { accounts: [first, second] } })
  })
  await page.route('**/api/v1/cloud/accounts/*/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.route('**/api/v1/cloud/accounts/first/save', (route) => route.fulfill({
    json: { gems: 1001, size: 1000, sha256, downloaded_at: '2026-11-23T21:00:00Z' },
  }))
  await page.route('**/api/v1/cloud/accounts/first/prepare', (route) => {
    expect(route.request().postDataJSON()).toEqual({ new_gems: 1002, source_sha256: sha256 })
    return route.fulfill({ json: { changed: true, original_gems: 1001, new_gems: 1002, backup, candidate_sha256: sha256 } })
  })
  await page.route('**/api/v1/cloud/accounts/first/confirm', async (route) => {
    const headers = route.request().headers()
    expect(headers.authorization).toBeUndefined()
    expect(headers['x-sk-cloud-admin']).toBeUndefined()
    expect(route.request().postDataJSON()).toEqual({ backup_id: backup.id, expected_sha256: sha256, confirmation: 'SUBIR' })
    await route.fulfill({ json: { persisted: true, message: 'Candidato verificado.' } })
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida/vinculadas#vincular=synthetic-browser-fixture')
  await page.getByRole('button', { name: 'Vincular cuenta del enlace' }).click()
  expect(new URL(page.url()).hash).toBe('')
  await page.getByRole('button', { name: 'Descargar partida' }).click()
  await expect(page.getByTestId('cloud-current-gems')).toHaveText('1,001')
  await page.getByLabel('Nueva cantidad de gemas').fill('1002')
  await page.getByRole('button', { name: 'Preparar edición' }).click()
  await expect(page.getByText('+1', { exact: true })).toBeVisible()
  const confirm = page.getByRole('button', { name: 'Subir y verificar' })
  await expect(confirm).toBeDisabled()
  await page.getByRole('checkbox').check()
  await confirm.click()
  await expect(page.getByText('Cambios guardados y verificados en la nube.')).toBeVisible()
  await page.getByLabel('Cuenta seleccionada').selectOption('second')
  await expect(page.getByTestId('cloud-current-gems')).toHaveCount(0)
  await expect(page.getByText('Cambios guardados y verificados en la nube.')).toHaveCount(0)
  await expect(page.getByText('Reconexión necesaria', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Descargar partida' })).toBeDisabled()
})

test('cierra la sesión y elimina la partida cargada de la vista', async ({ page }) => {
  let active = true
  await page.route('**/api/v1/cloud/accounts', (route) => route.fulfill({
    json: { ...status, session_active: active, accounts: active ? [first] : [] },
  }))
  await page.route('**/api/v1/cloud/accounts/first/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.route('**/api/v1/cloud/accounts/first/save', (route) => route.fulfill({
    json: { gems: 1001, size: 1000, sha256, downloaded_at: '2026-11-23T21:00:00Z' },
  }))
  await page.route('**/api/v1/cloud/accounts/logout', async (route) => {
    expect(route.request().method()).toBe('POST')
    expect(route.request().headers().authorization).toBeUndefined()
    active = false
    await route.fulfill({ status: 204 })
  })

  await page.goto('/partida/vinculadas')
  await page.getByRole('button', { name: 'Descargar partida' }).click()
  await expect(page.getByTestId('cloud-current-gems')).toHaveText('1,001')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page.getByTestId('cloud-current-gems')).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('button', { name: 'Cerrar sesión' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Descargar partida' })).toHaveCount(0)
})
