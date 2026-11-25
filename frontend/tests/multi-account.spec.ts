import { expect, test, type Page } from '@playwright/test'

const ID_A = 'a'.repeat(32)
const ID_B = 'b'.repeat(32)
const EMAIL_A = 'one@example.test'
const EMAIL_B = 'two@example.test'
const EMPTY_HISTORY = { backups: [], total: 0, listed: 0, limit: 25, unreadable: 0 }

type Session = ReturnType<typeof accountSession>
type State = {
  accounts: Session[]
  sessions: Record<string, Session>
  logins: Record<string, Session>
  saves: Record<string, ReturnType<typeof saveFor>>
}

function saveFor(gems: number) {
  return {
    verified: true, bytes: 505, sha256: (gems === 1000 ? 'a' : 'b').repeat(64), gems,
    fish_chip: 3, fish_chip_path: 'gameData.fishChip', material_fish: 3,
    material_fish_path: 'itemData.materials.material_fish', cumulative_fish_count: 42,
    cumulative_fish_count_path: 'itemData.cumulativeFishCount',
    fish_chip_write_policy: 'confirmed_by_owner', sections: 17, remote_source: 'modern-cloud',
    downloaded_at: '2026-11-23T20:00:00Z',
    report: {}, advanced: { available: false },
  }
}

function accountSession(id: string, email: string, label: string) {
  return {
    id, account_id: id, active: true, expired: false, identity_verified: true,
    account: {
      label, email, distribution: 'android-global',
      distribution_label: 'Android Global (GP)', platform: 'android',
    },
    session_expires_at: '2026-12-01T00:05:40Z', idle_expires_at: '2026-11-24T02:00:00Z',
    installation_ready: true, auto_identity: true, binding_wait_until: null,
    write_enabled: true, write_ready: true, min_gems: 0, max_gems: 2_147_483_647,
    save: null, save_error: null,
  }
}

function newState(): State {
  const a = accountSession(ID_A, EMAIL_A, 'Instalación A')
  const b = accountSession(ID_B, EMAIL_B, 'Instalación B')
  return {
    accounts: [],
    sessions: { [ID_A]: a, [ID_B]: b },
    logins: { [EMAIL_A]: a, [EMAIL_B]: b },
    saves: { [ID_A]: saveFor(1000), [ID_B]: saveFor(2000) },
  }
}

function publicConfig(state: State) {
  return {
    available: true, enabled: true, configured: true, write_enabled: true, secure: false,
    min_gems: 0, max_gems: 2_147_483_647, login_available: true,
    auto_identity: true, requires_profile_selection: false,
    profiles: [],
    distributions: [{
      id: 'android-global', label: 'Android Global (GP)', platform: 'android',
      game_version: '8.8.0', enabled: true, validated: true, note: 'Validada.',
    }],
    accounts: state.accounts.map((account) => ({
      ...account, ...(state.saves[account.id] ? { save: state.saves[account.id] } : {}),
    })),
    session: state.accounts[0] ?? { active: false, reason: 'none' },
    problem_code: null, message: null,
  }
}

async function mockApp(page: Page, state: State) {
  const saveAccounts: string[] = []
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1_048_576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/version', (route) => route.fulfill({ json: {
    service: 'sk-under', api_version: '2026.11.25', commit: null,
    features: ['native_backup_history', 'native_backup_history_pagination', 'native_backup_manual'],
  } }))
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({ json: publicConfig(state) }))
  await page.route('**/api/v1/cloud/native/session', (route) => {
    const id = route.request().headers()['x-sk-account'] ?? ''
    if (state.accounts.some((account) => account.id === id) && state.sessions[id]) {
      return route.fulfill({ json: state.sessions[id] })
    }
    return route.fulfill({
      status: 403,
      json: { error: { code: 'native_account_denied', message: 'Cuenta ajena.', issues: [] } },
    })
  })
  await page.route('**/api/v1/cloud/native/login', (route) => {
    const body = route.request().postDataJSON() as { email: string }
    const session = state.logins[body.email]
    if (!session) {
      return route.fulfill({
        status: 401,
        json: { error: { code: 'native_credentials_rejected', message: 'rechazado', issues: [] } },
      })
    }
    state.sessions[session.id] = session
    const index = state.accounts.findIndex((account) => account.id === session.id)
    if (index >= 0) state.accounts[index] = session
    else state.accounts.push(session)
    return route.fulfill({ json: session })
  })
  await page.route(/\/api\/v1\/cloud\/native\/accounts\/([0-9a-f]{32})\/logout$/, (route) => {
    const id = route.request().url().match(/accounts\/([0-9a-f]{32})\/logout$/)?.[1]
    state.accounts = state.accounts.filter((account) => account.id !== id)
    return route.fulfill({ status: 204 })
  })
  await page.route('**/api/v1/cloud/native/save', (route) => {
    const id = route.request().headers()['x-sk-account'] ?? ''
    saveAccounts.push(id)
    const save = state.saves[id]
    if (!save) {
      return route.fulfill({
        status: 404,
        json: { error: { code: 'native_no_cloud_save', message: 'Sin partida.', issues: [] } },
      })
    }
    return route.fulfill({ json: save })
  })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => {
    return route.fulfill({ json: EMPTY_HISTORY })
  })
  return saveAccounts
}

test('dashboard vacío permite añadir la primera cuenta y abrir su partida', async ({ page }) => {
  const state = newState()
  const saveAccounts = await mockApp(page, state)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Añadir cuenta' })).toBeVisible()
  await expect(page.getByText('Cuenta conectada')).toHaveCount(0)
  expect(saveAccounts).toHaveLength(0)

  await page.getByRole('link', { name: 'Añadir cuenta' }).click()
  await expect(page).toHaveURL(/\/cuentas\/nueva$/)
  await expect(page.getByRole('heading', { name: 'Añadir cuenta' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Iniciar sesión en ChillyRoom' })).toBeVisible()
  await page.getByLabel('Correo electrónico').fill(EMAIL_A)
  await page.getByLabel('Contraseña', { exact: true }).fill('fixture-password')
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()

  await expect(page).toHaveURL(new RegExp(`/cuentas/${ID_A}/partida$`))
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,000')
  expect(saveAccounts).toEqual([ID_A])

  await page.goto('/')
  await expect(page.getByRole('article', { name: EMAIL_A })).toContainText('Android')
  await expect(page.getByRole('article', { name: EMAIL_A })).toContainText('Global')
  expect(saveAccounts).toEqual([ID_A])
})

test('añadir una segunda cuenta conserva la primera y abre solo la nueva', async ({ page }) => {
  const state = newState()
  state.accounts = [state.sessions[ID_A]]
  const saveAccounts = await mockApp(page, state)
  await page.goto('/')
  await expect(page.getByRole('article', { name: EMAIL_A })).toBeVisible()

  await page.getByRole('link', { name: 'Añadir cuenta' }).click()
  await page.getByLabel('Correo electrónico').fill(EMAIL_B)
  await page.getByLabel('Contraseña', { exact: true }).fill('fixture-password')
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()

  await expect(page).toHaveURL(new RegExp(`/cuentas/${ID_B}/partida$`))
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('2,000')
  expect(saveAccounts).toEqual([ID_B])

  await page.goto('/')
  await expect(page.getByRole('article', { name: EMAIL_A })).toBeVisible()
  await expect(page.getByRole('article', { name: EMAIL_B })).toBeVisible()
  await expect(page.getByRole('button', { name: `Desvincular ${EMAIL_A}` })).toBeVisible()

  await page.getByRole('link', { name: `Abrir partida de ${EMAIL_A}` }).click()
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,000')
  expect(saveAccounts).toEqual([ID_B, ID_A])
})

test('cada cuenta conserva su partida y el editor reutiliza la copia descargada', async ({ page }) => {
  const state = newState()
  state.accounts = [state.sessions[ID_A], state.sessions[ID_B]]
  const saveAccounts = await mockApp(page, state)

  await page.goto(`/cuentas/${ID_A}/partida`)
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,000')
  expect(saveAccounts).toEqual([ID_A])
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toHaveValue('1000')
  expect(saveAccounts).toEqual([ID_A])

  await page.goto('/')
  expect(saveAccounts).toEqual([ID_A])
  await page.getByRole('link', { name: `Abrir partida de ${EMAIL_B}` }).click()
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('2,000')
  expect(saveAccounts).toEqual([ID_A, ID_B])
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toHaveValue('2000')
  expect(saveAccounts).toEqual([ID_A, ID_B])
})

test('rechaza abrir una cuenta que no pertenece al navegador', async ({ page }) => {
  const state = newState()
  state.accounts = [state.sessions[ID_A]]
  await mockApp(page, state)
  await page.goto(`/cuentas/${ID_B}/partida`)
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('article', { name: EMAIL_A })).toBeVisible()
  await expect(page.getByRole('article', { name: EMAIL_B })).toHaveCount(0)
})

test('desvincular una cuenta no afecta a las demás', async ({ page }) => {
  const state = newState()
  state.accounts = [state.sessions[ID_A], state.sessions[ID_B]]
  await mockApp(page, state)
  await page.goto('/')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: `Desvincular ${EMAIL_B}` }).click()
  await expect(page.getByRole('article', { name: EMAIL_B })).toHaveCount(0)
  await expect(page.getByRole('article', { name: EMAIL_A })).toBeVisible()
  await expect(page).toHaveURL(/\/$/)

  await page.getByRole('link', { name: `Abrir partida de ${EMAIL_A}` }).click()
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,000')
})

test('la privacidad del correo se mantiene en dashboard, cuenta y editor', async ({ page }) => {
  const state = newState()
  state.accounts = [state.sessions[ID_A], state.sessions[ID_B]]
  await mockApp(page, state)
  await page.goto('/')
  await expect(page.getByRole('article', { name: EMAIL_A })).toBeVisible()

  await page.getByRole('button', { name: 'Ocultar correos' }).click()
  await expect(page.getByRole('article', { name: 'Cuenta 1' })).toBeVisible()
  await expect(page.getByRole('article', { name: 'Cuenta 2' })).toBeVisible()
  await expect(page.locator('body')).not.toContainText(EMAIL_A)
  await expect(page.locator('body')).not.toContainText(EMAIL_B)
  await expect(page.locator(`[title*="${EMAIL_A}"]`)).toHaveCount(0)
  expect(await page.evaluate(() => localStorage.getItem('sk-under.hide-email'))).toBe('true')
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(EMAIL_A)
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(EMAIL_B)

  await page.reload()
  await expect(page.getByRole('article', { name: 'Cuenta 1' })).toBeVisible()
  await expect(page.locator('body')).not.toContainText(EMAIL_A)

  await page.getByRole('link', { name: 'Abrir partida de Cuenta 1' }).click()
  await expect(page.locator('body')).not.toContainText(EMAIL_A)
  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await expect(page.getByRole('dialog')).toContainText('Cuenta 1')
  await expect(page.getByRole('dialog')).not.toContainText(EMAIL_A)
  await page.keyboard.press('Escape')

  await page.goto(`/cuentas/${ID_A}/editor`)
  await expect(page.locator('body')).not.toContainText(EMAIL_A)
  await expect(page.locator(`[title*="${EMAIL_A}"]`)).toHaveCount(0)

  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await page.getByRole('link', { name: 'Volver al inicio' }).click()
  await page.getByRole('button', { name: 'Mostrar correos' }).click()
  await expect(page.getByRole('article', { name: EMAIL_A })).toBeVisible()
})

test('el menú de cuenta cierra con Escape, fuera, botón y navega resaltando la sección', async ({ page }) => {
  const state = newState()
  state.accounts = [state.sessions[ID_A], state.sessions[ID_B]]
  await mockApp(page, state)
  await page.goto(`/cuentas/${ID_A}/partida`)

  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cerrar menú' })).toBeFocused()
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe('hidden')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Abrir menú de cuenta' })).toBeFocused()
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe('')

  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await page.mouse.click(1000, 400)
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await page.getByRole('link', { name: 'Editor', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`/cuentas/${ID_A}/editor$`))
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await expect(page.getByRole('link', { name: 'Editor', exact: true })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('link', { name: 'Partida', exact: true })).not.toHaveAttribute('aria-current', 'page')
  await page.getByRole('button', { name: 'Cerrar menú' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  await page.getByRole('link', { name: 'Volver al inicio' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
})

for (const width of [375, 390]) {
  test(`dashboard y menú caben sin desbordar a ${width}px`, async ({ page }) => {
    const state = newState()
    state.accounts = [state.sessions[ID_A], state.sessions[ID_B]]
    await mockApp(page, state)
    await page.setViewportSize({ width, height: 812 })
    await page.goto('/')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByRole('link', { name: `Abrir partida de ${EMAIL_A}` }).click()
    await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const drawer = await page.getByRole('dialog').boundingBox()
    expect(drawer?.width ?? 0).toBeLessThanOrEqual(width)
    await page.getByRole('button', { name: 'Cerrar menú' }).click()
  })
}