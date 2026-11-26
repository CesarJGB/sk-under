import { expect, test, type Page } from '@playwright/test'

const ID_A = 'a'.repeat(32)
const EMAIL_A = 'one@example.test'
const EMPTY_HISTORY = { backups: [], total: 0, listed: 0, limit: 25, unreadable: 0 }

function saveFor(gems: number) {
  return {
    verified: true, bytes: 505, sha256: 'a'.repeat(64), gems,
    fish_chip: 3, fish_chip_path: 'gameData.fishChip', material_fish: 3,
    material_fish_path: 'itemData.materials.material_fish', cumulative_fish_count: 42,
    cumulative_fish_count_path: 'itemData.cumulativeFishCount',
    fish_chip_write_policy: 'confirmed_by_owner', sections: 17, remote_source: 'modern-cloud',
    downloaded_at: '2026-11-23T20:00:00Z',
    report: {}, advanced: { available: false },
  }
}

function accountSession() {
  return {
    id: ID_A, account_id: ID_A, active: true, expired: false, identity_verified: true,
    account: {
      label: 'Instalación A', email: EMAIL_A, distribution: 'android-global',
      distribution_label: 'Android Global (GP)', platform: 'android',
    },
    session_expires_at: '2026-12-01T00:05:40Z', idle_expires_at: '2026-11-24T02:00:00Z',
    installation_ready: true, auto_identity: true, binding_wait_until: null,
    write_enabled: true, write_ready: true, min_gems: 0, max_gems: 2_147_483_647,
    save: null, save_error: null,
  }
}

async function mockApp(page: Page, accounts: ReturnType<typeof accountSession>[]) {
  const session = accountSession()
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1_048_576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/version', (route) => route.fulfill({ json: {
    service: 'sk-under', api_version: '2026.11.25', commit: null,
    features: ['native_backup_history', 'native_backup_history_pagination', 'native_backup_manual'],
  } }))
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({ json: {
    available: true, enabled: true, configured: true, write_enabled: true, secure: false,
    min_gems: 0, max_gems: 2_147_483_647, login_available: true,
    auto_identity: true, requires_profile_selection: false,
    profiles: [],
    distributions: [{
      id: 'android-global', label: 'Android Global (GP)', platform: 'android',
      game_version: '8.8.0', enabled: true, validated: true, note: 'Validada.',
    }],
    accounts: accounts.map((account) => ({ ...account, save: saveFor(1000) })),
    session: accounts[0] ?? { active: false, reason: 'none' },
    problem_code: null, message: null,
  } }))
  await page.route('**/api/v1/cloud/native/session', (route) => {
    if (route.request().headers()['x-sk-account'] === ID_A) {
      return route.fulfill({ json: session })
    }
    return route.fulfill({
      status: 403,
      json: { error: { code: 'native_account_denied', message: 'Cuenta ajena.', issues: [] } },
    })
  })
  await page.route('**/api/v1/cloud/native/save', (route) => route.fulfill({ json: saveFor(1000) }))
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => {
    return route.fulfill({ json: EMPTY_HISTORY })
  })
}

async function themeOf(page: Page) {
  return page.evaluate(() => ({
    theme: document.documentElement.dataset.theme,
    colorScheme: document.documentElement.style.colorScheme,
    meta: document.querySelector('meta[name="theme-color"]')?.getAttribute('content'),
    stored: window.localStorage.getItem('sk-under.theme'),
  }))
}

test('el tema por defecto sigue al sistema y responde en caliente', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await mockApp(page, [])
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()

  expect(await themeOf(page)).toEqual({
    theme: 'dark', colorScheme: 'dark', meta: '#0C120F', stored: null,
  })

  await page.emulateMedia({ colorScheme: 'light' })
  await expect.poll(async () => (await themeOf(page)).theme).toBe('light')
  expect(await themeOf(page)).toMatchObject({ meta: '#112820' })
})

test('el selector del dashboard persiste y actualiza el color del navegador', async ({ page }) => {
  await mockApp(page, [])
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()

  await page.getByRole('button', { name: 'Apariencia: Sistema' }).click()
  await expect(page.getByRole('menuitemradio', { name: 'Sistema' })).toHaveAttribute('aria-checked', 'true')
  await page.getByRole('menuitemradio', { name: 'Oscuro' }).click()

  expect(await themeOf(page)).toEqual({
    theme: 'dark', colorScheme: 'dark', meta: '#0C120F', stored: 'dark',
  })
  await expect(page.getByRole('button', { name: 'Apariencia: Oscuro' })).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  expect(await themeOf(page)).toMatchObject({ theme: 'dark', stored: 'dark' })

  await page.getByRole('button', { name: 'Apariencia: Oscuro' }).click()
  await page.getByRole('menuitemradio', { name: 'Sistema' }).click()
  await page.emulateMedia({ colorScheme: 'light' })
  await expect.poll(async () => (await themeOf(page)).theme).toBe('light')
  expect(await themeOf(page)).toMatchObject({ stored: 'system', meta: '#112820' })
})

test('cambiar el tema conserva los datos escritos en el formulario', async ({ page }) => {
  await mockApp(page, [])
  await page.goto('/cuentas/nueva')
  const email = page.getByLabel('Correo electrónico')
  const password = page.getByLabel('Contraseña', { exact: true })
  await email.fill('borrador@example.test')
  await password.fill('borrador-secreto')

  await page.getByRole('button', { name: 'Apariencia: Sistema' }).click()
  await page.getByRole('menuitemradio', { name: 'Oscuro' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  await expect(email).toHaveValue('borrador@example.test')
  await expect(password).toHaveValue('borrador-secreto')
  await expect(page.getByRole('heading', { name: 'Añadir cuenta' })).toBeVisible()
})

test('el menú lateral cambia la apariencia sin romper el cierre ni el foco', async ({ page }) => {
  const session = accountSession()
  await mockApp(page, [session])
  await page.goto(`/cuentas/${ID_A}/partida`)
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,000')

  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  const drawer = page.getByRole('dialog')
  await expect(drawer).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ocultar correo' })).toBeFocused()

  await page.getByRole('button', { name: 'Apariencia: Sistema' }).click()
  await expect(page.getByRole('menuitemradio', { name: 'Sistema' })).toHaveAttribute('aria-checked', 'true')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu')).toHaveCount(0)
  await expect(drawer).toBeVisible()

  await page.getByRole('button', { name: 'Apariencia: Sistema' }).click()
  await page.getByRole('menuitemradio', { name: 'Oscuro' }).click()
  expect(await themeOf(page)).toMatchObject({ theme: 'dark', stored: 'dark' })
  await expect(drawer).toBeVisible()
  await expect(page.getByRole('button', { name: 'Apariencia: Oscuro' })).toBeFocused()

  await page.keyboard.press('Escape')
  await expect(drawer).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Abrir menú de cuenta' })).toBeFocused()
})

test('cambiar la apariencia desde el editor conserva el borrador pendiente', async ({ page }) => {
  const session = accountSession()
  await mockApp(page, [session])
  await page.goto(`/cuentas/${ID_A}/editor`)
  const gems = page.getByRole('textbox', { name: 'Gemas', exact: true })
  await expect(gems).toHaveValue('1000')
  await gems.fill('1234')
  await expect(page.getByText('1 cambio')).toBeVisible()

  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await page.getByRole('button', { name: 'Apariencia: Sistema' }).click()
  await page.getByRole('menuitemradio', { name: 'Oscuro' }).click()
  await page.keyboard.press('Escape')

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(gems).toHaveValue('1234')
  await expect(page.getByText('1 cambio')).toBeVisible()
})

test('el dashboard no desborda horizontalmente en móvil en ambos temas', async ({ page }) => {
  await mockApp(page, [accountSession()])
  for (const width of [320, 360, 375, 390, 430]) {
    await page.setViewportSize({ width, height: 780 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
    for (const preference of ['light', 'dark'] as const) {
      await page.getByRole('button', { name: /^Apariencia:/ }).click()
      await page.getByRole('menuitemradio', { name: preference === 'light' ? 'Claro' : 'Oscuro' }).click()
      const overflow = await page.evaluate(() => ({
        viewport: window.innerWidth,
        root: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
      }))
      expect(overflow.root, `root a ${width}px en ${preference}`).toBeLessThanOrEqual(overflow.viewport)
      expect(overflow.body, `body a ${width}px en ${preference}`).toBeLessThanOrEqual(overflow.viewport)
    }
  }
})