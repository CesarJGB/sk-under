import { expect, test, type Page, type Route } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import type { NativeBackup } from '../src/api'

const SHA = 'a'.repeat(64)
const CANDIDATE = 'b'.repeat(64)
const PROFILE = {
  id: '1'.repeat(32), label: 'Instalación Android Global', distribution: 'android-global',
  installation_ready: true, bound: true, write_allowed: true,
}
const SAVE = {
  verified: true, bytes: 505, sha256: SHA, gems: 1001, fish_chip: 3,
  material_fish: 3, cumulative_fish_count: 42, sections: 17, remote_source: 'modern-cloud',
}
const REPORT = {
  version: 1, game_version: 80800, serialzed_version: 1, encoding: 'json',
  fish_chips: { balance_path: null, balance: 3, balance_is_integer: true, server_authority: 'unknown', status: 'read_only', evidence: 'E4', fields: [], distinct_collections: {} },
  characters: {
    items: [{
      code: 'Knight', name: 'Knight', catalog_index: 0, unlocked: true, level: 2,
      level_max: null, level_status: 'not_validated', selected_skill: 0,
      skills: [{ key: 0, unlocked: true, name: 'Dual Wield' }],
      skill_options: [{ index: 0, name: 'Dual Wield' }],
      skin_options: [{ index: 0, key: 'c0', name: 'Knight', state: 'unlocked', value: 1, compatible: true }],
      selected_skin: 0, equipped_skin: null, skins_recorded: 1, skins_status: 'confirmed_by_owner',
    }, ...['Ranger', 'Mage', 'Alchemist'].map((name, index) => ({
      code: name, name, catalog_index: index + 1, unlocked: false, level: 0,
      level_max: null, level_status: 'not_validated', selected_skill: 0,
      skills: [{ key: 0, unlocked: true, name: `${name} Skill` }, { key: 1, unlocked: false, name: `${name} 2` }],
      skill_options: [{ index: 0, name: `${name} Skill` }, { index: 1, name: `${name} 2` }],
      skin_options: [
        { index: 0, key: `c${index + 1}`, name, state: 'unlocked', value: 1, compatible: true },
        { index: 1, key: `c${index + 1}_1`, name: `${name} Alt`, state: 'locked', value: 0, compatible: true },
      ],
      selected_skin: 0, equipped_skin: null, skins_recorded: 2, skins_status: 'confirmed_by_owner',
    }))],
    counts: { characters: 42, unlocked: 1, selected_skins: 1 },
    skills: { total: 7, unlocked: 4, locked: 3, selected: 4, characters_with_data: 4, status: 'read_only' },
    skins: { total: 7, unlocked: 4, pending: 3, selected: 1, incompatible: 0, characters_with_data: 4, status: 'confirmed_by_owner' },
    level_status: 'not_validated', skins_status: 'confirmed_by_owner',
    catalog: { available: true, error: null, version: '8.8.0', source: 'SKDFE', characters: 42 },
    notes: [], status: 'read_only',
  },
  resources: { groups: [], counts: {}, status: 'read_only', notes: [] },
  limitations: [],
}
const row = (id: string, label: string, count: number) => ({
  id, name: { es: label, en: label }, subcategory: 'basic', plant_id: null, count,
  value_type: 'int', owned: true, known: true, editable: true, insertable: false, reason: null,
  path: `itemData.materials.${id}`,
})
const ADVANCED = {
  materials: [row('wood', 'Madera', 4), row('iron', 'Hierro', 2)],
  seeds: [{ ...row('plant_banboo_seed', 'Semilla de bambú', 2), path: 'itemData.seeds.plant_banboo_seed' }],
  season_coin: { value: 100, value_type: 'int', available: true, path: 'seasonData.coin', min: 0, max: 2147483647, owner_reference: '', note: '' },
  reborn_card: { value: false, available: true, present: true, intimacy: 0, full: false, action_unlocked: false, value_type: 'bool', max: 1, max_note: '', path: 'gameData.rebornCard' },
  battle_pass: { records: [{ season_id: 8, cur_level: 2, cur_exp: 4, has_buy: false, free_claimed_level: 2, paid_claimed_level: 0, max_level: 50, editable: true, error: null }], selected_season_id: 8 },
  pets: [
    { id: 'Cat', numeric_id: 1, name: { es: 'Gato', en: 'Cat' }, unlocked: false, present: true, editable: true, insertable: false, skins: [], reason: null },
    { id: 'Dog', numeric_id: 2, name: { es: 'Perro', en: 'Dog' }, unlocked: true, present: true, editable: true, insertable: false, skins: [], reason: null },
  ],
  pet_skins: [{ id: 'Cat1', pet_code: 'Cat', base_pet: 'Cat', skin_index: 1, name: { es: 'Gato negro', en: 'Black cat' }, unlocked: false, present: true, editable: true, base_unlocked: false, dependency_note: '' }],
  pet_food: [
    { id: 'material_grain', name: { es: 'Bocadillos', en: 'Treats' }, count: 10, owned: true, editable: true, path: 'itemData.materials.material_grain' },
    { id: 'material_battery', name: { es: 'Batería', en: 'Battery' }, count: 5, owned: true, editable: true, path: 'itemData.materials.material_battery' },
  ],
  pet_progression: { available: false, path: '', read_only: true, global_full_count: null, full_count_key: '', entries: [], note: '' },
  pet_policy: { field: 'pets', experimental: false, evidence_level: 'E3', path: '', skin_note: '', food_note: '', progression_note: '' },
  policy: { field: 'advanced', experimental: true, evidence_level: 'E3', min: 0, max: 2147483647, max_note: '', material_fish_note: '', confirmed_functions: [], experimental_functions: ['battle_pass'] },
}
const SESSION_SAVE = { ...SAVE, report: REPORT, advanced: ADVANCED }
const ACTIVE = {
  active: true, identity_verified: true,
  account: { label: PROFILE.label, email: 'holder@example.test', distribution: 'android-global', distribution_label: 'Android Global (GP)', platform: 'android' },
  write_enabled: true, write_ready: true, installation_ready: true, auto_identity: true,
  min_gems: 0, max_gems: 2147483647, save: SESSION_SAVE, save_error: null,
}
const CONFIG = {
  available: true, enabled: true, configured: true, write_enabled: true, secure: false,
  min_gems: 0, max_gems: 2147483647, login_available: true, auto_identity: true,
  requires_profile_selection: false, profiles: [PROFILE],
  distributions: [{ id: 'android-global', label: 'Android Global (GP)', platform: 'android', game_version: '8.8.0', enabled: true, validated: true, note: '' }],
  session: { active: false, reason: 'none' }, problem_code: null, message: null,
}
const BACKUP = {
  id: 'c'.repeat(32), created_at: '2026-11-23T20:00:00Z', changed: true,
  original_size: 505, original_sha256: SHA, original_gems: 0, original_value: 0,
  candidate_size: 505, candidate_sha256: CANDIDATE, candidate_gems: 0, candidate_value: 0,
  remote_source: 'modern-cloud', remote_size: 505, remote_sha256: SHA,
}

function historyFixture(backups: NativeBackup[], total = backups.length, cursor: string | null = null) {
  return {
    backups, total, listed: backups.length, limit: 25,
    unreadable: backups.filter(({ status }) => status === 'unreadable').length,
    next_cursor: cursor,
  }
}

const UNIFIED_BACKUP: NativeBackup = {
  id: BACKUP.id, created_at: BACKUP.created_at, field: 'unified', status: 'prepared',
  original_size: BACKUP.original_size, changed: true, changes: 2, categories: ['gems', 'fish_chip'],
}

function downloaded(save: Record<string, unknown>) {
  const { verified: _verified, bytes, remote_source, sections: _sections, ...data } = save
  return { ...data, remote: { source: remote_source, size: bytes, sha256: data.sha256 },
    size: bytes, serialzed_version: 1, downloaded_at: '2026-11-24T20:00:00Z' }
}

async function open(page: Page, options: {
  save?: Record<string, unknown>
  sessionSave?: Record<string, unknown> | null
  download?: (route: Route) => Promise<void>
  path?: string
  width?: number
  limits?: { max_gems?: number }
  history?: boolean
  email?: string
} = {}) {
  const save = options.save ?? SESSION_SAVE
  const sessionSave = options.sessionSave === undefined ? save : options.sessionSave
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: { status: 'ok', access_mode: 'local', max_file_bytes: 1048576 } }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/version', (route) => route.fulfill({ json: {
    service: 'sk-under', api_version: '2026.11.25', commit: null,
    features: ['native_backup_history', 'native_backup_history_pagination', 'native_backup_manual'],
  } }))
  const session = {
    ...ACTIVE, ...options.limits, save: sessionSave, account_id: 'primary',
    account: options.email ? { ...ACTIVE.account, email: options.email } : ACTIVE.account,
  }
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({ json: {
    ...CONFIG,
    session,
  } }))
  await page.route('**/api/v1/cloud/native/session', (route) => route.fulfill({ json: session }))
  if (options.history !== false) await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ json: historyFixture([]) }))
  await page.route('**/api/v1/cloud/native/save', options.download ?? ((route) => route.fulfill({ json: downloaded(save) })))
  await page.setViewportSize({ width: options.width ?? 390, height: 844 })
  await page.goto(options.path ?? '/editor')
  if (!options.path && sessionSave) await expect(page.getByTestId('quick-edit')).toBeVisible()
}

async function openDrawer(page: Page) {
  await page.getByRole('button', { name: 'Abrir menú de cuenta' }).click()
  return page.getByRole('dialog')
}

async function goToPartida(page: Page) {
  const drawer = await openDrawer(page)
  await drawer.getByRole('link', { name: 'Partida', exact: true }).click()
}

async function openCategory(page: Page, name: string) {
  const back = page.getByRole('button', { name: '← Categorías' })
  if (await back.count()) await back.click()
  await page.getByRole('tab', { name: 'Categorías' }).click()
  await page.getByRole('button', { name: new RegExp(`^${name}($| Cambios pendientes)`) }).click()
}

async function goToQuick(page: Page) {
  const reviewBack = page.getByTestId('unified-preview').getByRole('button', { name: 'Volver' })
  if (await reviewBack.count()) await reviewBack.click()
  const back = page.getByRole('button', { name: '← Categorías' })
  if (await back.count()) await back.click()
  await page.getByRole('tab', { name: 'Rápida' }).click()
}

function prepared(plan: Record<string, unknown>, categories: Array<[string, string, number]>) {
  const changes = categories.reduce((sum, [, , count]) => sum + count, 0)
  return {
    remote: { source: 'modern-cloud', size: 505, sha256: SHA },
    backup: { ...BACKUP, field: 'unified', unified_plan: plan, candidate_gems: changes, candidate_value: changes },
    field: 'unified', plan,
    categories: categories.map(([key, label, count]) => ({ key, label, changes: count, detail: { kind: 'explicit' } })),
    steps: categories.map(([key]) => key), change_count: changes, original_value: 0, new_value: changes,
    changed: true, candidate_size: 505, candidate_sha256: CANDIDATE,
    byte_diff: { original_size: 505, modified_size: 505, first_difference: 1, common_prefix: 1, common_suffix: 503, changed_original_bytes: 1, changed_modified_bytes: 1, original_sha256: SHA, modified_sha256: CANDIDATE },
    changed_fields: Array.from({ length: changes }, (_, index) => `gameData.campo${index}`),
    validation: { valid: true, structure_valid: true, atomic: true, message: 'Candidato compuesto.' },
  }
}

for (const width of [320, 360, 375, 390, 430, 768, 1280]) {
  test(`Partida muestra tres bloques y respeta el ancho de ${width} px`, async ({ page }) => {
    await open(page, { path: '/partida', width, save: { ...SESSION_SAVE, downloaded_at: '2026-11-25T20:30:00Z' } })
    await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({
      json: historyFixture([
        { ...UNIFIED_BACKUP, created_at: '2026-11-25T20:26:00Z', status: 'verified' },
        { id: '3'.repeat(32), field: 'characters', created_at: '2026-11-25T19:45:00Z', status: 'prepared',
          changed: true, original_size: 11240, original_value: 12, candidate_value: 13 },
        { id: '4'.repeat(32), field: 'gems', created_at: '2026-11-25T18:20:00Z', status: 'unverified' },
        { id: '5'.repeat(32), field: 'fish_chip', created_at: '2026-11-25T17:21:00Z', status: 'verified',
          restoration: 'verified', original_value: 3, candidate_value: 5 },
      ], 28, 'cursor-de-prueba'),
    }))
    await page.getByRole('button', { name: 'Actualizar historial' }).click()
    const cloud = page.getByRole('region', { name: 'Partida en la nube' })
    const backups = page.getByRole('region', { name: 'Respaldos' })
    const drawer = await openDrawer(page)
    await expect(drawer).toContainText('holder@example.test')
    await expect(drawer).toContainText('Android · Global')
    await expect(drawer).not.toContainText('Conectada')
    await expect(drawer.getByRole('button', { name: 'Cerrar sesión' })).toHaveCount(0)
    await page.keyboard.press('Escape')
    await expect(cloud.locator('.partida-stat-page').first().locator('.partida-stat')).toHaveCount(4)
    await expect(cloud.locator('.partida-stat-page').first().locator('.partida-stat-value'))
      .toHaveText(['1,001', '3', '100', '1 / 42'])
    await expect(cloud.locator('time')).toHaveAttribute('datetime', '2026-11-25T20:30:00Z')
    await expect(cloud.getByRole('link', { name: 'Abrir editor' })).toBeVisible()
    await expect(backups.getByText('28 respaldos', { exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Acceso por enlace privado' })).toHaveCount(0)
    await expect(backups.locator('.partida-backup-warning')).toHaveCount(1)
    await expect(backups.locator('.partida-backup-warning')).toHaveAttribute('aria-label', /Subida no verificada/)
    await backups.locator('summary').first().click()
    await expect(backups.locator('.partida-backup-state').first()).toContainText('Subida verificada')
    await backups.locator('summary').nth(3).click()
    await expect(backups.locator('.partida-backup-state').nth(3)).toContainText('Restauración verificada')
    await expect(backups.getByText('2 cambios registrados')).toBeVisible()
    await expect(backups.getByText('Gemas · Fichas de pesca')).toBeVisible()
    if (width <= 430) {
      expect(await cloud.locator('.partida-stat-page').first().evaluate((element) =>
        getComputedStyle(element).gridTemplateColumns.split(' ').length)).toBe(2)
      const heading = backups.getByRole('heading', { name: 'Respaldos' })
      const box = (await heading.boundingBox())!
      const create = (await backups.getByRole('button', { name: 'Crear respaldo' }).boundingBox())!
      expect(box.height).toBeLessThan(36)
      if (width <= 340) expect(create.y).toBeGreaterThanOrEqual(box.y + box.height)
      expect(await heading.evaluate((element) => getComputedStyle(element).whiteSpace)).toBe('nowrap')
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    const destination = process.env.SK_PARTIDA_SCREENSHOTS_DIR
    if (destination) {
      await mkdir(destination, { recursive: true })
      await page.screenshot({ path: join(destination, `partida-${width}.png`), fullPage: true, animations: 'disabled' })
    }
  })
}

test('el carrusel genera páginas dinámicas y navega sin descargar de nuevo', async ({ page }) => {
  let downloads = 0
  await open(page, {
    path: '/partida', width: 1280, save: { ...SESSION_SAVE, downloaded_at: '2026-11-25T20:30:00Z' },
    download: (route) => {
      downloads += 1
      return route.fulfill({ json: downloaded(SESSION_SAVE) })
    },
  })
  const cloud = page.getByRole('region', { name: 'Partida en la nube' })
  const pages = cloud.locator('.partida-stat-page')
  await expect(pages).toHaveCount(4)
  await expect(cloud.getByRole('button', { name: /^Ir a la página/ })).toHaveCount(4)
  await expect(cloud.getByText('Página 1 de 4', { exact: true })).toBeVisible()
  await expect(pages.first().locator('.partida-stat').first()).toHaveAttribute('data-metric', 'gems')
  await expect(pages.first().locator('.partida-stat')).toHaveCount(4)
  await cloud.getByRole('button', { name: 'Ir a la página 2' }).click()
  await expect(cloud.getByText('Página 2 de 4', { exact: true })).toBeVisible()
  await expect(pages.nth(1).locator('.partida-stat')).toHaveCount(4)
  await expect(pages.nth(1).locator('.partida-stat').first()).toHaveAttribute('data-metric', 'skills')
  await expect(pages.first()).toHaveAttribute('aria-hidden', 'true')
  const viewport = cloud.getByRole('group', { name: /Estadísticas, página/ })
  await viewport.focus()
  await page.keyboard.press('End')
  await expect(cloud.getByText('Página 4 de 4', { exact: true })).toBeVisible()
  await page.keyboard.press('Home')
  await expect(cloud.getByText('Página 1 de 4', { exact: true })).toBeVisible()
  expect(downloads).toBe(0)
})

test('distingue un cero real de un dato desconocido y actualiza el carrusel al descargar', async ({ page }) => {
  let downloads = 0
  await open(page, {
    path: '/partida', sessionSave: null,
    download: (route) => {
      downloads += 1
      const payload = downloads === 1
        ? { ...SAVE, gems: 0, fish_chip: 0, cumulative_fish_count: 0, report: null, advanced: null }
        : downloads === 2
          ? { ...SAVE, report: REPORT, advanced: ADVANCED }
          : { ...SAVE, report: REPORT, advanced: { available: false, error: 'No se pudo leer el editor avanzado' } }
      return route.fulfill({ json: downloaded(payload) })
    },
  })
  const cloud = page.getByRole('region', { name: 'Partida en la nube' })
  const firstPage = cloud.locator('.partida-stat-page').first()
  await expect(firstPage.locator('.partida-stat-value')).toHaveText(['0', '0', '—', '—'])
  await expect(cloud.getByTestId('stat-gems')).toHaveAttribute('data-state', 'count')
  await expect(cloud.getByTestId('stat-season_coin')).toHaveAttribute('data-state', 'unavailable')
  await expect(cloud.getByTestId('stat-characters')).toHaveAttribute('data-state', 'unavailable')
  expect(downloads).toBe(1)
  await cloud.getByRole('button', { name: 'Actualizar partida' }).click()
  await expect(firstPage.locator('.partida-stat-value')).toHaveText(['1,001', '3', '100', '1 / 42'])
  expect(downloads).toBe(2)
  await cloud.getByRole('button', { name: 'Actualizar partida' }).click()
  await expect(cloud.getByTestId('stat-materials')).toHaveAttribute('data-state', 'error')
  await expect(cloud.getByTestId('stat-materials').locator('.partida-stat-value')).toHaveText('Error')
  expect(downloads).toBe(3)
})

test('mantiene legibles correos y cantidades grandes en 320 px sin desbordar', async ({ page }) => {
  const email = 'cuenta.con.un.correo.extremadamente.largo@example-domain.test'
  await open(page, {
    path: '/partida', width: 320, email,
    save: { ...SESSION_SAVE, gems: 2_147_483_647, downloaded_at: '2026-11-25T20:30:00Z' },
  })
  const cloud = page.getByRole('region', { name: 'Partida en la nube' })
  await expect(cloud.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('2,147,483,647')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
  expect(await cloud.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
  let drawer = await openDrawer(page)
  await expect(drawer).toContainText(email)
  expect(await drawer.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
  await page.keyboard.press('Escape')
  await page.evaluate(() => localStorage.setItem('sk-under.hide-email', 'true'))
  await page.reload()
  await expect(cloud.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('2,147,483,647')
  drawer = await openDrawer(page)
  await expect(drawer).toContainText('••••••••@••••.•••')
  await expect(drawer).not.toContainText(email)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
  expect(await drawer.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
})

test('Partida conserva la última descarga y muestra datos desconocidos como ausentes', async ({ page }) => {
  let downloads = 0
  await open(page, {
    path: '/partida', sessionSave: null,
    download: (route) => {
      downloads += 1
      return downloads === 1
        ? route.fulfill({ json: downloaded({ ...SAVE, fish_chip: null }) })
        : route.fulfill({ status: 502, json: { error: { code: 'native_save_error', message: 'fixture', issues: [] } } })
    },
  })
  const cloud = page.getByRole('region', { name: 'Partida en la nube' })
  await expect(cloud.locator('.partida-stat-page').first().locator('.partida-stat-value')).toHaveText(['1,001', '—', '—', '—'])
  await expect(cloud.locator('dd')).toHaveCount(1)
  await cloud.getByRole('button', { name: 'Actualizar partida' }).click()
  await expect(cloud.getByRole('alert')).toBeVisible()
  await expect(cloud.locator('time')).toHaveAttribute('datetime', '2026-11-24T20:00:00Z')
  await expect(cloud.locator('.partida-stat-page').first().locator('.partida-stat-value')).toHaveText(['1,001', '—', '—', '—'])
  await cloud.getByRole('link', { name: 'Abrir editor' }).click()
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toHaveValue('1001')
  expect(downloads).toBe(2)
})

test('Partida diferencia el historial vacío, ilegible y el almacén indisponible', async ({ page }) => {
  await open(page, { path: '/partida' })
  const list = page.getByRole('region', { name: 'Respaldos' })
  await expect(list.getByText('Esta cuenta todavía no tiene respaldos.')).toBeVisible()
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({
    json: historyFixture([{ id: BACKUP.id, created_at: null, field: null, status: 'unreadable', problem: 'authentication' }]),
  }))
  await list.getByRole('button', { name: 'Actualizar historial' }).click()
  await expect(list.getByRole('img', { name: 'Respaldo ilegible' })).toBeVisible()
  await list.locator('summary').click()
  await expect(list.getByText('Respaldo ilegible', { exact: true })).toBeVisible()
  await expect(list.getByText('No se pudo autenticar el respaldo', { exact: false })).toBeVisible()
  await expect(list.getByRole('button', { name: 'Restaurar respaldo' })).toHaveCount(0)
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({
    status: 503, json: { error: { code: 'native_backup_unavailable', message: 'fixture', issues: [] } },
  }))
  await list.getByRole('button', { name: 'Actualizar historial' }).click()
  await expect(list.getByRole('alert')).toContainText('El almacén de respaldos no está disponible')
  await expect(list.getByText('Esta cuenta todavía no tiene respaldos.')).toHaveCount(0)
})

test('actualiza el historial tras preparar, subir y volver de Editor a Partida', async ({ page }) => {
  await open(page, { path: '/partida' })
  let status: NativeBackup['status'] | null = null
  const requested: Array<NativeBackup['status'] | null> = []
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => {
    requested.push(status)
    return route.fulfill({ json: historyFixture(status ? [{ ...UNIFIED_BACKUP, status }] : []) })
  })
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    status = 'prepared'
    return route.fulfill({ json: prepared(route.request().postDataJSON(), [['gems', 'Gemas', 2]]) })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    status = 'verified'
    return route.fulfill({ json: { action: 'confirm', backup_id: BACKUP.id, uploaded: true, persisted: true } })
  })
  await page.route('**/api/v1/cloud/native/save', (route) => route.fulfill({
    json: downloaded({ ...SESSION_SAVE, gems: status === 'verified' ? 1201 : 1001 }),
  }))
  await expect(page.getByText('Esta cuenta todavía no tiene respaldos.')).toBeVisible()
  await page.getByRole('link', { name: 'Abrir editor' }).click()
  await page.getByRole('textbox', { name: 'Gemas', exact: true }).fill('1201')
  await page.getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  await expect.poll(() => requested).toContain('prepared')
  await goToPartida(page)
  await page.getByRole('button', { name: 'Descartar y salir' }).click()
  const backups = page.getByRole('region', { name: 'Respaldos' })
  await expect(backups.locator('.partida-backup-warning')).toHaveCount(0)
  await backups.locator('summary').first().click()
  await expect(backups.locator('.partida-backup-state').first()).toHaveText('Edición preparada')
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,001')

  await page.getByRole('link', { name: 'Abrir editor' }).click()
  await page.getByRole('textbox', { name: 'Gemas', exact: true }).fill('1201')
  await page.getByRole('button', { name: 'Guardar', exact: true }).click()
  await page.getByLabel(/Confirmo subir el candidato/).check()
  await page.getByRole('button', { name: 'Guardar en la nube' }).click()
  await expect(page.getByText(/Guardado y verificado/)).toBeVisible()
  await expect.poll(() => requested).toContain('verified')
  await goToPartida(page)
  await expect(backups.locator('.partida-backup-warning')).toHaveCount(0)
  await backups.locator('summary').first().click()
  await expect(backups.locator('.partida-backup-state').first()).toHaveText('Subida verificada')
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,201')
})

test('permite una segunda edición con el hash confirmado tras subir', async ({ page }) => {
  const sourceShas: string[] = []
  await open(page, { path: '/partida' })
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    const body = route.request().postDataJSON()
    sourceShas.push(body.source_sha256)
    return route.fulfill({ json: prepared(body, [['gems', 'Gemas', 100]]) })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => route.fulfill({
    json: { action: 'confirm', backup_id: BACKUP.id, uploaded: true, persisted: true },
  }))
  await page.route('**/api/v1/cloud/native/save', (route) => route.fulfill({
    json: downloaded({ ...SESSION_SAVE, sha256: CANDIDATE, gems: 1201 }),
  }))

  await page.getByRole('link', { name: 'Abrir editor' }).click()
  const gems = page.getByRole('textbox', { name: 'Gemas', exact: true })
  const bar = page.getByTestId('editor-bar')
  await gems.fill('1201')
  await bar.getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  await page.getByLabel(/Confirmo subir el candidato/).check()
  await page.getByRole('button', { name: 'Guardar en la nube' }).click()
  await expect(page.getByText(/Guardado y verificado/)).toBeVisible()
  await expect(gems).toHaveValue('1201')
  await expect(bar).toContainText('0 cambios')

  await gems.fill('1202')
  await bar.getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  expect(sourceShas).toEqual([SHA, CANDIDATE])
})

test('descarga una sola vez al abrir Inicio y comparte la partida', async ({ page }) => {
  let downloads = 0
  await open(page, {
    path: '/', sessionSave: null,
    download: (route) => {
      downloads += 1
      return route.fulfill({ json: downloaded(SESSION_SAVE) })
    },
  })
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Abrir partida de holder@example.test' })).toBeVisible()
  expect(downloads).toBe(0)

  await page.getByRole('link', { name: 'Abrir partida de holder@example.test' }).click()
  await expect(page.getByTestId('stat-gems').locator('.partida-stat-value')).toHaveText('1,001')
  expect(downloads).toBe(1)

  await page.getByRole('link', { name: 'Abrir editor' }).click()
  await expect(page.getByTestId('quick-edit')).toContainText('1/4 desbloqueados')
  expect(downloads).toBe(1)
})

test('si la subida persiste pero falla la descarga, solo reintenta la descarga', async ({ page }) => {
  let confirmations = 0
  let downloads = 0
  await open(page)
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) =>
    route.fulfill({ json: prepared(route.request().postDataJSON(), [['gems', 'Gemas', 100]]) }))
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    confirmations += 1
    return route.fulfill({ json: { action: 'confirm', backup_id: BACKUP.id, uploaded: true, persisted: true } })
  })
  await page.route('**/api/v1/cloud/native/save', (route) => {
    downloads += 1
    return downloads === 1
      ? route.fulfill({ status: 502, json: { error: { code: 'native_save_error', message: 'fixture', issues: [] } } })
      : route.fulfill({ json: downloaded({ ...SESSION_SAVE, sha256: CANDIDATE, gems: 1201 }) })
  })

  const gems = page.getByRole('textbox', { name: 'Gemas', exact: true })
  await gems.fill('1201')
  await page.getByTestId('editor-bar').getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  await page.getByLabel(/Confirmo subir el candidato/).check()
  await page.getByRole('button', { name: 'Guardar en la nube' }).click()
  await expect(page.getByText(/Subida confirmada\. No se pudo descargar la partida actualizada/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reintentar descarga' })).toBeVisible()
  expect(confirmations).toBe(1)

  await page.getByRole('button', { name: 'Reintentar descarga' }).click()
  await expect(gems).toHaveValue('1201')
  await expect(page.getByText(/Guardado y verificado/)).toBeVisible()
  expect(confirmations).toBe(1)
  expect(downloads).toBe(2)
})

test('la edición rápida es la pantalla inicial y comparte el borrador con categorías', async ({ page }) => {
  await open(page)
  await expect(page.getByRole('tab', { name: 'Rápida' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
  await page.getByLabel('Activar Todos los personajes').check()
  await expect(page.getByTestId('editor-bar')).toContainText('3 cambios')
  await page.getByRole('tab', { name: 'Categorías' }).click()
  await page.getByRole('button', { name: /Personajes/ }).click()
  await expect(page.getByRole('tab', { name: 'Rápida' })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: 'Categorías' })).toHaveCount(0)
  await page.getByRole('checkbox', { name: 'Mage' }).uncheck()
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  await goToQuick(page)
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('los acordeones de skins conservan selección y búsqueda sin expandir todo', async ({ page }) => {
  await open(page)
  await openCategory(page, 'Skins')
  const ranger = page.getByTestId('unlock-group-Ranger')
  const header = ranger.getByRole('button', { name: /Ranger/ })
  await expect(header).toHaveAttribute('aria-expanded', 'false')
  await expect(ranger.getByRole('checkbox')).toHaveCount(0)
  await header.click()
  await expect(header).toHaveAttribute('aria-expanded', 'true')
  await ranger.getByRole('checkbox', { name: 'Ranger Alt' }).check()
  await expect(page.getByTestId('editor-bar')).toContainText('1 cambio')
  await header.click()
  await expect(header).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByTestId('editor-bar')).toContainText('1 cambio')
  const search = page.getByRole('searchbox', { name: 'Buscar desbloqueos' })
  await search.fill('Alt')
  await expect(ranger.getByRole('checkbox', { name: 'Ranger Alt' })).toBeVisible()
  await expect(page.getByTestId('unlock-group-Knight')).toHaveCount(0)
  await search.clear()
  await expect(header).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByTestId('editor-bar')).toContainText('1 cambio')
})

test('compone gemas y desbloqueos en un candidato y una sola subida', async ({ page }) => {
  await open(page)
  let payload: Record<string, unknown> | null = null
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    payload = route.request().postDataJSON()
    return route.fulfill({ json: prepared(payload!, [['gems', 'Gemas', 1], ['characters', 'Personajes', 3]]) })
  })
  let uploads = 0
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    uploads += 1
    return route.fulfill({ json: { action: 'confirm', backup_id: BACKUP.id, field: 'unified', uploaded: true, accepted: true, persisted: true, already_original: false, expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505, remote_gems: 1201, remote_characters: 4, status: 200, message: 'Verificado.' } })
  })
  const gems = page.getByRole('textbox', { name: 'Gemas', exact: true })
  await expect(gems).toHaveValue('1001')
  await gems.click()
  await gems.press('Home')
  await gems.press('ArrowRight')
  await gems.press('Shift+ArrowRight')
  await gems.press('2')
  await expect(gems).toHaveValue('1201')
  expect(await gems.evaluate((input: HTMLInputElement) => input.selectionStart)).toBe(2)
  await page.getByLabel('Activar Todos los personajes').check()
  await expect(page.getByTestId('editor-bar')).toContainText('4 cambios')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByTestId('unified-preview')).toContainText('Gemas')
  expect(payload).toEqual({ gems: 1201, characters: ['Ranger', 'Mage', 'Alchemist'], source_sha256: SHA })
  await page.getByLabel(/Confirmo subir el candidato/).check()
  await page.getByRole('button', { name: 'Guardar en la nube' }).click()
  await expect(page.getByText('Guardado y verificado', { exact: false })).toBeVisible()
  expect(uploads).toBe(1)
})

test('compone categorías detalladas en el mismo borrador', async ({ page }) => {
  await open(page)
  let payload: Record<string, any> | null = null
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    payload = route.request().postDataJSON()
    return route.fulfill({ json: prepared(payload!, [['advanced', 'Avanzado', 7]]) })
  })
  const openCategory = async (name: RegExp) => {
    await page.getByRole('tab', { name: 'Categorías' }).click()
    await page.getByRole('button', { name }).click()
  }
  const back = () => page.getByRole('button', { name: '← Categorías' }).click()

  await openCategory(/Mascotas/)
  await page.getByRole('checkbox', { name: 'Mascota Gato' }).check()
  await page.getByRole('checkbox', { name: 'Skin Gato negro' }).check()
  await page.getByLabel('Cantidad de Bocadillos').fill('1000')
  await back()

  await openCategory(/Materiales/)
  await page.getByLabel('Nueva cantidad para Madera').fill('25')
  await back()

  await openCategory(/Semillas/)
  await page.getByLabel('Nueva cantidad para Semilla de bambú').fill('9')
  await back()

  await openCategory(/Temporada/)
  await page.locator('.number-row').filter({ hasText: 'Monedas de temporada' }).locator('input').fill('5000')
  await page.getByText('Tarjeta de renacimiento permanente').click()
  await back()

  await openCategory(/Pase de batalla/)
  await page.getByRole('button', { name: 'Nivel máximo' }).click()

  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  expect(payload!.advanced).toMatchObject({
    materials: [{ id: 'wood', value: 25 }, { id: 'material_grain', value: 1000 }],
    seeds: [{ id: 'plant_banboo_seed', value: 9 }],
    season_coin: 5000,
    reborn_card: true,
    pets: ['Cat', 'Cat1'],
    battle_pass: { season_id: 8, cur_level: 50 },
  })
})

test('los mínimos no reducen cantidades y el descarte pide confirmación', async ({ page }) => {
  await open(page)
  const materials = page.getByRole('textbox', { name: 'Materiales', exact: true })
  await materials.fill('10')
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  page.once('dialog', (dialog) => dialog.dismiss())
  await page.getByRole('button', { name: 'Descartar' }).click()
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Descartar' }).click()
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
  await expect(materials).toHaveValue('')
  await expect(materials).toHaveAttribute('placeholder', 'Mínimo')
})

test('un conflicto remoto conserva el borrador', async ({ page }) => {
  await open(page)
  await page.getByLabel('Activar Todos los personajes').check()
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => route.fulfill({ status: 409, json: { error: { code: 'cloud_remote_changed', message: 'La partida cambió.', issues: [] } } }))
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('La partida cambió en la nube', { exact: false })).toBeVisible()
  await expect(page.getByTestId('editor-bar')).toContainText('3 cambios')
})

test('precarga los importes en ambos modos y solo conserva casillas para acciones sin entrada numérica', async ({ page }) => {
  await open(page)
  const quick = page.getByTestId('quick-edit')
  for (const [label, value] of [
    ['Gemas', '1001'], ['Fichas de pesca', '3'], ['Recompensas de pesca', '42'],
    ['Monedas de temporada', '100'], ['Semillas', '2'], ['Baterías', '5'],
  ]) {
    const input = quick.getByRole('textbox', { name: label, exact: true })
    await expect(input).toBeEnabled()
    await expect(input).toHaveValue(value)
    await expect(input).toHaveAttribute('inputmode', 'numeric')
  }
  for (const name of ['Materiales', 'Alimento de mascotas']) {
    const input = quick.getByRole('textbox', { name, exact: true })
    await expect(input).toBeEnabled()
    await expect(input).toHaveValue('')
    await expect(input).toHaveAttribute('placeholder', 'Mínimo')
  }
  for (const name of ['Recursos', 'Cantidades mínimas']) {
    await expect(quick.getByRole('region', { name }).getByRole('checkbox')).toHaveCount(0)
  }
  await expect(quick.getByText(/^Actual /)).toHaveCount(0)
  await expect(quick.getByRole('region', { name: 'Desbloqueos' })).toContainText('1/4 desbloqueados')
  await expect(quick.getByRole('region', { name: 'Desbloqueos' }).getByRole('checkbox')).toHaveCount(5)
  await expect(quick.getByRole('region', { name: 'Beneficios' }).getByRole('checkbox')).toHaveCount(2)
  await openCategory(page, 'Mascotas')
  await expect(page.getByRole('textbox', { name: 'Cantidad de Bocadillos' })).toHaveValue('10')
  await expect(page.getByRole('textbox', { name: 'Cantidad de Batería' })).toHaveValue('5')
  await openCategory(page, 'Recursos')
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toHaveValue('1001')
  await openCategory(page, 'Semillas')
  await expect(page.getByRole('textbox', { name: 'Cantidad mínima', exact: true })).toHaveValue('2')
  await expect(page.getByLabel('Nueva cantidad para Semilla de bambú')).toHaveValue('2')
  await expect(page.getByRole('button', { name: 'Aplicar mínimo' })).toBeDisabled()
  await openCategory(page, 'Pase de batalla')
  await expect(page.getByRole('textbox', { name: 'Nivel', exact: true })).toHaveValue('2')
  await expect(page.getByRole('textbox', { name: 'Experiencia', exact: true })).toHaveValue('4')
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
  await expect(page.getByRole('button', { name: 'Guardar', exact: true })).toBeDisabled()
})

test('carga el informe después de entrar desde una vista previa de inicio de sesión', async ({ page }) => {
  const { report: _report, ...preview } = SESSION_SAVE
  let release!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  await open(page, { sessionSave: preview, download: async (route) => {
    await pending
    await route.fulfill({ json: downloaded(SESSION_SAVE) })
  } })
  await expect(page.getByTestId('editor-bar')).toContainText('Descargando partida…')
  await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toHaveCount(0)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Editor')
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toBeDisabled()
  const drawer = await openDrawer(page)
  await expect(drawer).toContainText('holder@example.test')
  await expect(drawer).toContainText('Android · Global')
  await page.keyboard.press('Escape')
  release()
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toHaveValue('1001')
  await expect(page.getByLabel('Activar Todos los personajes')).toBeEnabled()
  await expect(page.getByTestId('quick-edit')).toContainText('1/4 desbloqueados')
})

test('precarga los ceros reales sin generar operaciones', async ({ page }) => {
  const zero = (item: ReturnType<typeof row>) => ({ ...item, count: 0 })
  const save = {
    ...SESSION_SAVE, gems: 0, fish_chip: 0, material_fish: 0, cumulative_fish_count: 0,
    advanced: { ...ADVANCED, season_coin: { ...ADVANCED.season_coin, value: 0 },
      materials: ADVANCED.materials.map(zero), seeds: ADVANCED.seeds.map(zero),
      pet_food: ADVANCED.pet_food.map((item) => ({ ...item, count: 0 })) },
  }
  await open(page, { save, sessionSave: null })
  const amounts = page.getByTestId('quick-edit').getByRole('textbox')
  await expect(amounts).toHaveCount(8)
  expect(await amounts.evaluateAll((inputs: HTMLInputElement[]) => inputs.map((input) => input.value))).toEqual(Array(8).fill('0'))
  await expect(page.getByRole('button', { name: 'Guardar', exact: true })).toBeDisabled()
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
})

test('solo envía el cero explícito y omite valores restaurados, intactos y vacíos', async ({ page }) => {
  await open(page)
  let payload: Record<string, unknown> | undefined
  let uploads = 0
  let preparations = 0
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    preparations++
    payload = route.request().postDataJSON()
    return route.fulfill({ json: prepared(payload!, [['fish_progress', 'Recompensas de pesca', 1]]) })
  })
  await page.route('**/api/v1/cloud/native/confirm', async (route) => {
    uploads++
    await page.route('**/api/v1/cloud/native/save', (load) => load.fulfill({
      json: downloaded({ ...SESSION_SAVE, sha256: CANDIDATE, cumulative_fish_count: 0 }),
    }))
    await route.fulfill({ json: { backup_id: BACKUP.id, persisted: true, remote_sha256: CANDIDATE } })
  })
  const gems = page.getByRole('textbox', { name: 'Gemas', exact: true })
  await gems.fill('900')
  await expect(page.getByTestId('editor-bar')).toContainText('1 cambio')
  await gems.fill('1001')
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
  await expect(page.getByRole('button', { name: 'Descartar', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Guardar', exact: true })).toBeDisabled()
  await page.getByRole('textbox', { name: 'Monedas de temporada', exact: true }).clear()
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
  await expect(page.getByRole('button', { name: 'Descartar', exact: true })).toBeEnabled()
  await openCategory(page, 'Temporada')
  await expect(page.getByRole('textbox', { name: 'Monedas de temporada', exact: true })).toHaveValue('')
  await page.getByLabel('Recompensas de pesca', { exact: true }).fill('0')
  await page.getByRole('button', { name: 'Guardar', exact: true }).evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
  })
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  expect(preparations).toBe(1)
  expect(payload).toEqual({ fish_progress: 0, source_sha256: SHA })
  await page.getByLabel(/Confirmo subir el candidato/).check()
  await page.getByRole('button', { name: 'Guardar en la nube' }).evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
  })
  await expect(page.getByTestId('editor-bar')).toContainText('Verificado')
  expect(uploads).toBe(1)
  await goToQuick(page)
  const quick = page.getByTestId('quick-edit')
  await expect(quick.getByRole('textbox', { name: 'Gemas', exact: true })).toHaveValue('1001')
  await expect(quick.getByRole('textbox', { name: 'Recompensas de pesca', exact: true })).toHaveValue('0')
  await expect(quick.getByRole('textbox', { name: 'Monedas de temporada', exact: true })).toHaveValue('100')
})

test('distingue colecciones completas de datos ausentes o incompatibles', async ({ page }) => {
  const completeCharacters = REPORT.characters.items.map((item, index) => ({
    ...item, unlocked: true, skills: item.skills.map((skill) => ({ ...skill, unlocked: true })),
    skin_options: index > 0 ? [] : Array.from({ length: 142 }, (_, index) => ({
      index, key: `skin-${index}`, name: `Skin ${index + 1}`, state: 'unlocked', value: 1, compatible: true,
    })),
  }))
  const complete = {
    ...SESSION_SAVE,
    report: { ...REPORT, characters: { ...REPORT.characters, items: completeCharacters } },
    advanced: { ...ADVANCED, pets: ADVANCED.pets.map((pet) => ({ ...pet, unlocked: true })),
      pet_skins: ADVANCED.pet_skins.map((skin) => ({ ...skin, unlocked: true })) },
  }
  await open(page, { save: complete })
  const unlocks = page.getByRole('region', { name: 'Desbloqueos' })
  await expect(unlocks).toContainText('142/142 desbloqueadas')
  await expect(unlocks.locator('.unlock-status.complete')).toHaveCount(5)
  await expect(unlocks.getByRole('button', { name: 'Seleccionar pendientes' })).toBeDisabled()
  await expect(unlocks.getByLabel('Activar Todas las skins')).toBeDisabled()
  await openCategory(page, 'Skins')
  await expect(page.getByTestId('category-skins')).toContainText('Completo')
  await expect(page.getByTestId('category-skins').getByRole('checkbox')).toHaveCount(0)

  const unknown = {
    ...SESSION_SAVE, gems: null, fish_chip: null, cumulative_fish_count: null, report: null,
    advanced: { available: false, error: 'Estructura incompatible.' },
  }
  await open(page, { save: unknown, sessionSave: null })
  await expect(unlocks.getByText('No disponible', { exact: true })).toHaveCount(5)
  await expect(unlocks.locator('.unlock-status.complete')).toHaveCount(0)
  const quick = page.getByTestId('quick-edit')
  for (const name of ['Gemas', 'Fichas de pesca', 'Recompensas de pesca', 'Monedas de temporada', 'Materiales', 'Semillas', 'Alimento de mascotas', 'Baterías']) {
    const input = quick.getByRole('textbox', { name, exact: true })
    await expect(input).toBeDisabled()
    await expect(input).toHaveValue('')
    await expect(input).toHaveAccessibleDescription('No disponible')
  }
  await openCategory(page, 'Recursos')
  await expect(page.getByTestId('category-recursos').getByText('Sin dato', { exact: true })).toHaveCount(4)
  await expect(page.getByLabel('Gemas', { exact: true })).toBeDisabled()
})

test('los mínimos simultáneos se aplican por elemento e ignoran cantidades incompatibles', async ({ page }) => {
  const advanced = {
    ...ADVANCED, materials: [...ADVANCED.materials, row('steel', 'Acero', 30),
      row('material_fish', 'Espejo de fichas', 3), { ...row('odd', 'Dato incompatible', 0), count: null, editable: false }],
    seeds: [...ADVANCED.seeds, row('plant_carrot_seed', 'Semilla de zanahoria', 12)],
  }
  await open(page, { save: { ...SESSION_SAVE, advanced } })
  let payload: Record<string, unknown> | undefined
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    payload = route.request().postDataJSON()
    return route.fulfill({ json: prepared(payload!, [['advanced', 'Materiales y semillas', 5]]) })
  })
  const seeds = page.getByRole('textbox', { name: 'Semillas', exact: true })
  await expect(seeds).toBeEnabled()
  await expect(seeds).toHaveValue('')
  await expect(seeds).toHaveAttribute('placeholder', 'Mínimo')
  await seeds.fill('0')
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
  for (const [label, requested] of [['Materiales', '15'], ['Alimento de mascotas', '20'], ['Baterías', '25'], ['Semillas', '3']]) {
    await page.getByLabel(label, { exact: true }).fill(requested)
  }
  await openCategory(page, 'Materiales')
  await expect(page.getByLabel('Nueva cantidad para Espejo de fichas')).toBeDisabled()
  const incompatible = page.getByLabel('Nueva cantidad para Dato incompatible')
  await expect(incompatible).toBeDisabled()
  await expect(incompatible).toHaveValue('')
  await expect(incompatible).toHaveAccessibleDescription('Sin dato')
  await page.getByLabel('Cantidad mínima').fill('12')
  await page.getByRole('button', { name: 'Aplicar mínimo' }).click()
  await expect(page.getByLabel('Nueva cantidad para Acero')).toHaveValue('30')
  await expect(page.getByLabel('Nueva cantidad para Hierro')).toHaveValue('15')
  await expect(page.getByLabel('Nueva cantidad para Madera')).toHaveValue('15')
  await page.getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  expect(payload).toEqual({ source_sha256: SHA, advanced: { seeds: [{ id: 'plant_banboo_seed', value: 3 }], materials: [
    { id: 'wood', value: 15 }, { id: 'iron', value: 15 }, { id: 'material_grain', value: 20 },
    { id: 'material_battery', value: 25 },
  ] } })
})

test('restaurar una cantidad detallada retira la edición exacta y conserva el mínimo solicitado por separado', async ({ page }) => {
  const missing = { ...row('bronze', 'Bronce', 0), count: null, owned: false, insertable: true }
  await open(page, { save: { ...SESSION_SAVE, advanced: { ...ADVANCED, materials: [...ADVANCED.materials, missing] } } })
  const bar = page.getByTestId('editor-bar')
  await page.getByRole('textbox', { name: 'Materiales', exact: true }).fill('8')
  await openCategory(page, 'Materiales')
  const wood = page.getByLabel('Nueva cantidad para Madera')
  await expect(wood).toHaveValue('8')
  await wood.fill('0')
  await expect(wood).toHaveAccessibleDescription('Anterior 4')
  await wood.fill('4')
  await expect(wood).toHaveAccessibleDescription('Pendiente 8')
  await wood.clear()
  await expect(wood).toHaveValue('')
  await expect(wood).toHaveAccessibleDescription('Pendiente 8')
  const bronze = page.getByLabel('Nueva cantidad para Bronce')
  await expect(bronze).toBeEnabled()
  await expect(bronze).toHaveValue('')
  await expect(bronze).toHaveAccessibleDescription('Sin registro')
  await bronze.fill('0')
  await expect(bar).toContainText('3 cambios')

  let payload: Record<string, unknown> | undefined
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    payload = route.request().postDataJSON()
    return route.fulfill({ json: prepared(payload!, [['advanced', 'Materiales', 3]]) })
  })
  await bar.getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  expect(payload).toEqual({ source_sha256: SHA, advanced: { seeds: [], materials: [
    { id: 'wood', value: 8 }, { id: 'iron', value: 8 }, { id: 'bronze', value: 0 },
  ] } })
})

test('protege el borrador al salir por el encabezado y por el historial', async ({ page }) => {
  await open(page, { path: '/partida' })
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await page.getByLabel('Activar Todos los personajes').check()
  const leave = page.getByRole('dialog', { name: '¿Salir del editor?' })
  await goToPartida(page)
  await expect(leave).toBeVisible()
  await leave.getByRole('button', { name: 'Seguir editando' }).click()
  await expect(leave).not.toBeVisible()
  await expect(page.getByTestId('editor-bar')).toContainText('3 cambios')
  await page.getByRole('tab', { name: 'Rápida' }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: 'Categorías' })).toBeFocused()
  await page.evaluate(() => history.back())
  await expect(page.getByRole('tab', { name: 'Rápida' })).toHaveAttribute('aria-selected', 'true')
  await page.evaluate(() => history.back())
  await expect(leave).toBeVisible()
  await leave.getByRole('button', { name: 'Descartar y salir' }).click()
  await expect(page).toHaveURL(/\/partida$/)
  await expect(page.getByRole('button', { name: 'Abrir menú de cuenta' })).toBeVisible()
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
})

test('distingue un saldo de solo lectura y rechaza valores inválidos o fuera de los límites', async ({ page }) => {
  await open(page, { save: {
    ...SESSION_SAVE, fish_chip: null,
    report: { ...REPORT, fish_chips: { ...REPORT.fish_chips, balance: 17, balance_path: 'gameData.fishChip' } },
  }, limits: { max_gems: 2000 } })
  const fish = page.getByRole('textbox', { name: 'Fichas de pesca', exact: true })
  await expect(fish).toHaveValue('17')
  await expect(fish).toBeDisabled()
  await expect(fish).toHaveAccessibleDescription('Solo lectura')
  const gems = page.getByRole('textbox', { name: 'Gemas', exact: true })
  const bar = page.getByTestId('editor-bar')
  for (const value of ['-5', '1.5', '1e3', 'abc', ' ', '2147483648', '2001']) {
    await gems.fill(value)
    await expect(gems).toHaveAttribute('aria-invalid', 'true')
    await expect(bar).toContainText('Revisa las cantidades')
    await expect(bar).toContainText('0 cambios')
    await expect(bar.getByRole('button', { name: 'Guardar', exact: true })).toBeDisabled()
  }
  await gems.fill('2000')
  await expect(gems).not.toHaveAttribute('aria-invalid', 'true')
  await expect(bar).toContainText('1 cambio')
  await gems.fill('01001')
  await expect(bar).toContainText('0 cambios')
  await expect(bar.getByRole('button', { name: 'Guardar', exact: true })).toBeDisabled()
})

test('reinicializa el borrador y las cantidades al descargar otra partida tras un conflicto', async ({ page }) => {
  const fresh = { ...SESSION_SAVE, sha256: CANDIDATE, gems: 90256, fish_chip: 0,
    advanced: { ...ADVANCED, seeds: [], materials: ADVANCED.materials.map((item) => ({ ...item, count: 7 })) } }
  await open(page, { download: (route) => route.fulfill({ json: downloaded(fresh) }) })
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => route.fulfill({
    status: 409, json: { error: { code: 'cloud_remote_changed', message: 'La partida cambió.', issues: [] } },
  }))
  const bar = page.getByTestId('editor-bar')
  await page.getByRole('textbox', { name: 'Gemas', exact: true }).fill('1200')
  await page.getByLabel('Activar Todos los personajes').check()
  await openCategory(page, 'Materiales')
  const wood = page.getByLabel('Nueva cantidad para Madera')
  await wood.fill('19')
  await page.getByLabel('Cantidad mínima', { exact: true }).fill('40')
  await bar.getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByText('La partida cambió en la nube', { exact: false })).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Descargar de nuevo' }).click()
  await expect(wood).toHaveValue('7')
  await expect(page.getByLabel('Cantidad mínima', { exact: true })).toHaveValue('7')
  await expect(bar).toContainText('0 cambios')
  await goToQuick(page)
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toHaveValue('90256')
  await expect(page.getByRole('textbox', { name: 'Fichas de pesca', exact: true })).toHaveValue('0')
  await expect(page.getByRole('textbox', { name: 'Materiales', exact: true })).toHaveValue('7')
  await expect(page.getByRole('textbox', { name: 'Semillas', exact: true })).toBeDisabled()
  await expect(page.getByLabel('Activar Todos los personajes')).not.toBeChecked()
  await expect(bar.getByRole('button', { name: 'Guardar', exact: true })).toBeDisabled()
})

test('mantiene visible la barra y desplaza el campo enfocado cuando se reduce la altura visible', async ({ page }) => {
  await open(page)
  const input = page.getByLabel('Baterías', { exact: true })
  await input.focus()
  const bar = page.getByTestId('editor-bar')
  await page.evaluate(() => {
    const viewport = window.visualViewport!
    Object.defineProperty(viewport, 'height', { configurable: true, value: window.innerHeight - 280 })
    viewport.dispatchEvent(new Event('resize'))
  })
  await expect.poll(async () => {
    const field = (await input.boundingBox())!
    const footer = (await bar.boundingBox())!
    return field.y + field.height < footer.y
  }).toBe(true)
  const footer = (await bar.boundingBox())!
  expect(footer.y + footer.height).toBeCloseTo(844 - 280)
  await input.fill('50')
  await expect(bar).toContainText('1 cambio')
  await page.evaluate(() => {
    const viewport = window.visualViewport!
    Reflect.deleteProperty(viewport, 'height')
    viewport.dispatchEvent(new Event('resize'))
  })
  await expect.poll(async () => {
    const footer = (await bar.boundingBox())!
    return footer.y + footer.height
  }).toBe(844)
})

test('muestra los estados de guardado y conserva el borrador si la subida queda sin verificar', async ({ page }) => {
  await open(page)
  let allowUpload!: () => void
  const uploadPending = new Promise<void>((resolve) => { allowUpload = resolve })
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => route.fulfill({
    json: prepared(route.request().postDataJSON(), [['characters', 'Personajes', 3]]),
  }))
  await page.route('**/api/v1/cloud/native/confirm', async (route) => {
    await uploadPending
    await route.fulfill({ json: { backup_id: BACKUP.id, uploaded: true, accepted: true, persisted: false } })
  })
  await page.getByLabel('Activar Todos los personajes').check()
  await page.getByRole('button', { name: 'Guardar', exact: true }).click()
  await page.getByLabel(/Confirmo subir el candidato/).check()
  await page.getByRole('button', { name: 'Guardar en la nube' }).click()
  const bar = page.getByTestId('editor-bar')
  await expect(bar).toContainText('Guardando y verificando…')
  await expect(bar.getByRole('button', { name: 'Guardar en la nube' })).toBeDisabled()
  await expect(bar.getByRole('button', { name: 'Descartar' })).toBeDisabled()
  await goToPartida(page)
  const leave = page.getByRole('dialog', { name: 'Operación en curso' })
  await expect(leave).toBeVisible()
  await expect(leave.getByRole('button', { name: 'Descartar y salir' })).toHaveCount(0)
  await leave.getByRole('button', { name: 'Seguir editando' }).click()
  allowUpload()
  await expect(bar).toContainText('Revisa el resultado')
  await expect(bar).toContainText('3 cambios')
  await expect(page.getByText('Subida sin confirmar. Actualiza la partida', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Actualizar partida' })).toBeVisible()
  await expect(page.getByTestId('editor-bar').getByRole('button', { name: 'Guardar', exact: true })).toBeDisabled()
})

test('capturas móviles, tableta y escritorio sin desbordamiento', async ({ page }) => {
  await open(page)
  const sizes = [
    { width: 320, height: 568 }, { width: 360, height: 800 }, { width: 375, height: 812 },
    { width: 390, height: 844 }, { width: 430, height: 932 },
    { width: 768, height: 1024 }, { width: 1280, height: 800 },
  ]
  const screenshot = async (name: string) => {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), name).toBe(true)
    await expect(page.getByTestId('editor-bar')).toBeInViewport()
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: `test-results/edicion-numerica/${name}.png` })
  }
  const fits = (input: HTMLInputElement) => {
    const styles = getComputedStyle(input)
    const canvas = document.createElement('canvas').getContext('2d')!
    canvas.font = styles.font
    const available = input.clientWidth - parseFloat(styles.paddingLeft) - parseFloat(styles.paddingRight)
    return input.offsetHeight >= 44 && canvas.measureText(input.value).width <= available
  }
  await page.getByLabel('Activar Todos los personajes').check()
  const gems = page.getByRole('textbox', { name: 'Gemas', exact: true })
  await gems.fill('2147483647')
  for (const size of sizes) {
    await page.setViewportSize(size)
    await page.getByRole('tab', { name: 'Rápida' }).click()
    expect(await gems.evaluate(fits), `cantidad de diez dígitos a ${size.width} px`).toBe(true)
    await screenshot(`rapida-${size.width}`)
    await page.getByRole('tab', { name: 'Categorías' }).click()
    await expect(page.getByTestId('category-grid').getByRole('button')).toHaveCount(11)
    if (size.width <= 430) {
      expect(await page.locator('.category-grid').evaluate((grid) => getComputedStyle(grid).gridTemplateColumns.split(' ').length)).toBe(3)
    }
    expect(await page.locator('.category-icon').evaluateAll((icons) =>
      Promise.all(icons.map((icon) => icon instanceof HTMLImageElement ? icon.decode() : true)).then(() => true))).toBe(true)
    await screenshot(`categorias-${size.width}`)
    await page.getByRole('button', { name: 'Materiales' }).click()
    const minimum = page.getByRole('textbox', { name: 'Cantidad mínima', exact: true })
    await minimum.fill('2147483647')
    expect(await minimum.evaluate(fits), `mínimo de diez dígitos a ${size.width} px`).toBe(true)
    await minimum.clear()
    await minimum.blur()
    await screenshot(`materiales-${size.width}`)
    await goToQuick(page)
    const lastRow = page.getByLabel('Activar Pase de batalla al nivel máximo')
    await expect(lastRow).toBeVisible()
    await expect.poll(async () => {
      await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight))
      const control = (await lastRow.boundingBox())!
      const footer = (await page.getByTestId('editor-bar').boundingBox())!
      return control.y + control.height < footer.y
    }, { message: `fila final en ${size.width}` }).toBe(true)
    if (size.width === 390) await screenshot('rapida-desbloqueos-390')
  }
  await page.setViewportSize({ width: 390, height: 844 })
  for (const [category, slug] of [
    ['Recursos', 'recursos'], ['Personajes', 'personajes'], ['Habilidades', 'habilidades'],
    ['Skins', 'skins'], ['Mascotas', 'mascotas'], ['Semillas', 'semillas'], ['Temporada', 'temporada'], ['Pase de batalla', 'pase'],
  ]) {
    await openCategory(page, category)
    await expect(page.getByTestId(`category-${slug}`)).toBeVisible()
    await screenshot(`${slug}-390`)
  }
})

const MANUAL_BACKUP: NativeBackup = {
  id: '6'.repeat(32), created_at: '2026-11-25T21:10:00Z', field: 'snapshot', kind: 'manual',
  status: 'available', changed: false, original_size: 11240, integrity: 'verified', can_restore: true,
  summary: { gems: 1234, fish_chip: 7, characters: 12, save_size: 11240, game_version: '8.8.0' },
}

test('crea un respaldo manual verificado y lo muestra como copia independiente', async ({ page }) => {
  await open(page, { path: '/partida', history: false })
  let posts = 0
  let gets = 0
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => {
    if (route.request().method() === 'POST') {
      posts += 1
      expect(route.request().postDataJSON()).toEqual({ confirmation: 'RESPALDAR' })
      return route.fulfill({ json: { message: 'Respaldo manual creado y verificado.' } })
    }
    gets += 1
    return route.fulfill({ json: historyFixture([MANUAL_BACKUP]) })
  })
  await page.getByRole('button', { name: 'Crear respaldo' }).click()
  await expect(page.getByText('Respaldo creado', { exact: true })).toBeVisible()
  await expect(page.getByText('Respaldo manual creado y verificado.')).toHaveCount(0)
  await expect(page.getByText('Respaldo creado', { exact: true })).toHaveCount(0, { timeout: 6000 })
  expect(posts).toBe(1)
  await expect.poll(() => gets).toBeGreaterThanOrEqual(2)
  const item = page.locator('.partida-backup').first()
  await expect(item.getByText('Respaldo manual', { exact: true })).toBeVisible()
  await expect(item.locator('summary')).not.toContainText('Manual')
  await expect(item.getByText('Preventivo antes de restaurar')).toHaveCount(0)
  await item.locator('summary').click()
  await expect(item.getByText('Preventivo antes de restaurar')).toHaveCount(0)
  await expect(item.getByText('Integridad del respaldo verificada')).toBeVisible()
  await expect(item.getByText('Copia creada a voluntad; no se escribió nada en ChillyRoom.')).toBeVisible()
  await expect(item.getByText('1,234')).toBeVisible()
  await expect(item.getByText('11 KiB')).toBeVisible()
})

test('pagina el historial con cursor estable y muestra todos los respaldos', async ({ page }) => {
  await open(page, { path: '/partida', history: false })
  const cursors: Array<string | null> = []
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => {
    const cursor = new URL(route.request().url()).searchParams.get('cursor')
    cursors.push(cursor)
    if (cursor === 'siguiente-pagina') {
      return route.fulfill({
        json: historyFixture(Array.from({ length: 3 }, (_, index) => ({
          ...UNIFIED_BACKUP, id: (index + 26).toString(16).padStart(32, '0'),
          created_at: `2026-11-2${index}T10:00:00Z`, status: 'verified' as const,
        })), 28),
      })
    }
    return route.fulfill({
      json: historyFixture(Array.from({ length: 25 }, (_, index) => ({
        ...UNIFIED_BACKUP, id: (index + 1).toString(16).padStart(32, '0'),
        created_at: `2026-11-24T${String(23 - index).padStart(2, '0')}:00:00Z`, status: 'verified' as const,
      })), 28, 'siguiente-pagina'),
    })
  })
  const list = page.getByRole('region', { name: 'Respaldos' })
  await expect(list.getByText('28 respaldos', { exact: true })).toBeVisible()
  await expect(list.locator('.partida-backup')).toHaveCount(25)
  await list.getByRole('button', { name: 'Cargar más respaldos' }).click()
  await expect(list.locator('.partida-backup')).toHaveCount(28)
  await expect(list.getByText('28 respaldos', { exact: true })).toBeVisible()
  await expect(list.getByRole('button', { name: 'Cargar más respaldos' })).toHaveCount(0)
  expect(cursors).toEqual([null, 'siguiente-pagina'])
})

test('muestra el respaldo preventivo y permite deshacer la restauración', async ({ page }) => {
  await open(page, { path: '/partida' })
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({
    json: historyFixture([{
      ...MANUAL_BACKUP, kind: 'preventive', created_at: '2026-11-25T21:20:00Z',
      summary: { gems: 1001, save_size: 11240 },
    }]),
  }))
  await page.getByRole('button', { name: 'Actualizar historial' }).click()
  const item = page.locator('.partida-backup').first()
  await expect(item.getByText('Respaldo preventivo', { exact: true })).toBeVisible()
  await item.locator('summary').click()
  await expect(item.getByText('Se creó automáticamente antes de restaurar otra versión.')).toBeVisible()
  await item.getByRole('button', { name: 'Deshacer restauración' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading', { name: 'Restaurar respaldo preventivo' })).toBeVisible()
  await expect(dialog).toContainText('podrás restaurar para deshacer este cambio')
  await dialog.getByRole('button', { name: 'Cancelar' }).click()
  await expect(dialog).toHaveCount(0)
})

test('distingue un backend sin historial de un historial vacío', async ({ page }) => {
  await open(page, { path: '/partida' })
  await page.route('**/api/v1/version', (route) => route.fulfill({ status: 404, json: { detail: 'Not Found' } }))
  await page.route(/\/api\/v1\/cloud\/native\/backups(?:\?.*)?$/, (route) => route.fulfill({ status: 404, json: { detail: 'Not Found' } }))
  await page.getByRole('button', { name: 'Actualizar historial' }).click()
  const list = page.getByRole('region', { name: 'Respaldos' })
  await expect(list.getByRole('alert').first()).toContainText('no incluye el historial de respaldos')
  await expect(list.getByText('Esta cuenta todavía no tiene respaldos.')).toHaveCount(0)
})

const PROGRESS_ADVANCED = {
  ...ADVANCED,
  hero_levels: {
    available: true, path: 'gameData.heroLevel', min: 0, max: 7,
    max_note: 'Máximo clásico documentado; el máximo por personaje no se recuperó.',
    experimental: true, evidence_level: 'E3',
    note: 'Solo subidas dentro del intervalo documentado.', entries: [
      { id: 'Knight', name: 'Knight', level: 2, value_type: 'int', present: true, editable: true, unlocked: true, path: 'gameData.heroLevel.Knight', reason: null },
      { id: 'Ranger', name: 'Ranger', level: 0, value_type: 'int', present: true, editable: true, unlocked: false, path: 'gameData.heroLevel.Ranger', reason: null },
      { id: 'Mage', name: 'Mage', level: 7, value_type: 'int', present: true, editable: false, unlocked: true, path: 'gameData.heroLevel.Mage', reason: 'Nivel máximo documentado' },
    ],
  },
  pet_progression: {
    available: true, path: 'statisticData.event2Count', read_only: false, global_full_count: 1,
    full_count_key: 'pet_full_intimacy', note: '', limitation: 'Máximos observados por mascota.', experimental: true, evidence_level: 'E2',
    entries: [
      { id: 'Cat', numeric_id: 0, name: { es: 'Gato', en: 'Cat' }, present: true, intimacy: 200, full: false, action_unlocked: false, value_type: 'int', max: 240, max_note: '', path: 'statisticData.event2Count.pet_0_intimacy', editable: true, reason: null, full_path: 'statisticData.event2Count.pet_0_full_intimacy' },
      { id: 'Pig', numeric_id: 2, name: { es: 'Cerdo', en: 'Pig' }, present: true, intimacy: 240, full: true, action_unlocked: true, value_type: 'int', max: 240, max_note: '', path: 'statisticData.event2Count.pet_2_intimacy', editable: false, reason: 'Afinidad máxima', full_path: 'statisticData.event2Count.pet_2_full_intimacy' },
      { id: 'Serenade', numeric_id: 27, name: { es: 'Serenata', en: 'Serenade' }, present: true, intimacy: 240, full: false, action_unlocked: false, value_type: 'int', max: null, max_note: '', path: 'statisticData.event2Count.pet_27_intimacy', editable: false, reason: 'Máximo no confirmado', full_path: 'statisticData.event2Count.pet_27_full_intimacy' },
    ],
  },
  blueprints: {
    available: true, path: 'itemData.blueprints', statuses: ['Got', 'Researched'],
    experimental: true, evidence_level: 'E2', note: '', limitation: 'Solo claves existentes.', unmatched: ['legacy_unknown'],
    entries: [
      { id: 'blueprint_multi_room_skin_0', key: 'blueprint_multi_room_skin_0', name: { es: 'Sala múltiple', en: 'Multi room' }, subcategory: 'multi', blueprint_type: 1, target: 'multi_room_skin_0', research_materials: [], status: 'Got', value_type: 'enum', present: true, editable: true, bulk_eligible: true, path: 'itemData.blueprints.blueprint_multi_room_skin_0' },
      { id: 'blueprint_garden_skin_0', key: 'garden_skin_0', name: { es: 'Jardín', en: 'Garden' }, subcategory: 'others', blueprint_type: 2, target: 'garden_skin_0', research_materials: [], status: 'Researched', value_type: 'enum', present: true, editable: true, bulk_eligible: false, path: 'itemData.blueprints.garden_skin_0' },
      { id: 'blueprint_weapon_0', key: null, name: { es: 'Arma', en: 'Weapon' }, subcategory: 'weapon', blueprint_type: 7, target: 'weapon_0', research_materials: [], status: null, value_type: null, present: false, editable: false, bulk_eligible: false, path: null },
    ],
  },
  decorations: {
    available: true, experimental: true, evidence_level: 'E2', note: '', limitation: 'Selección no editable.',
    objects: [
      { id: 'ItemEggMachine', label: 'Máquina de huevos', unlocked: true, value: [0], editable: false, reason: 'Ya desbloqueado; no se elimina.', path: 'itemData.roomDecorateDic.ItemEggMachine' },
      { id: 'ObjectSafe', label: 'Caja fuerte', unlocked: false, value: null, editable: true, reason: 'No desbloqueado; se puede crear la clave con [0].', path: null },
      { id: 'PetFood', label: 'Zona de alimentación de mascotas', unlocked: false, value: null, editable: true, reason: 'No desbloqueado; se puede crear la clave con [0].', path: null },
    ],
    levels: [
      { id: 'Book', level: 2, max_observed: 5, editable: true, reason: 'Se puede subir hasta el máximo observado (5).', path: 'gameData.roomObjectLevel.Book' },
      { id: 'Safe', level: 5, max_observed: 5, editable: false, reason: 'Ya está en el máximo observado (5).', path: 'gameData.roomObjectLevel.Safe' },
    ],
    appearances: [
      { id: 'blueprint_multi_room_skin_1', key: 'multi_room_skin_1', name: { es: 'Sala uno', en: 'Room one' }, subcategory: 'multi', status: 'Got', obtained: true, researched: false, path: 'itemData.blueprints.multi_room_skin_1' },
    ],
    unknown_objects: ['CustomObject'], unknown_levels: ['CustomLevel'],
    room: { current: 'Common', current_type: 'str', room_level: 1, unlock_list: [], selection_editable: false, selection_reason: 'El mapa de selección no está determinado.' },
  },
}
const PROGRESS_SAVE = { ...SESSION_SAVE, advanced: PROGRESS_ADVANCED }

test('integra niveles, afinidad y planos en un solo borrador móvil', async ({ page }) => {
  const plans: Array<Record<string, unknown>> = []
  await open(page, { save: PROGRESS_SAVE, width: 320 })
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    const plan = route.request().postDataJSON()
    plans.push(plan)
    return route.fulfill({ json: prepared(plan, [
      ['hero_levels', 'Niveles de personaje', 1],
      ['pet_affinity', 'Afinidad de mascotas', 1],
      ['blueprints', 'Planos', 1],
    ]) })
  })

  await expect(page.getByRole('region', { name: 'Progreso' })).toContainText('Niveles de personaje')
  await expect(page.getByRole('region', { name: 'Progreso' })).toContainText('Afinidad de mascotas')

  await openCategory(page, 'Personajes')
  await page.getByLabel('Mejorar 2 elegibles al máximo').check()
  await page.getByLabel('Incluir Ranger en la mejora masiva').uncheck()
  await page.getByLabel('Nivel o progreso de Knight').fill('5')
  await expect(page.getByTestId('editor-bar')).toContainText('1 cambio')
  await page.screenshot({ path: 'test-results/edicion-numerica/niveles-320.png' })

  await openCategory(page, 'Mascotas')
  await page.getByLabel('Nivel o progreso de Gato').fill('220')
  await page.screenshot({ path: 'test-results/edicion-numerica/afinidad-320.png' })

  await openCategory(page, 'Planos')
  await page.getByLabel('Estado de Sala múltiple').selectOption('Researched')
  await expect(page.getByTestId('editor-bar')).toContainText('3 cambios')
  await page.screenshot({ path: 'test-results/edicion-numerica/planos-320.png' })

  await page.getByTestId('editor-bar').getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  expect(plans).toHaveLength(1)
  expect(plans[0].hero_levels).toEqual([{ code: 'Knight', level: 5 }])
  expect(plans[0].pet_affinity).toEqual([{ code: 'Cat', value: 220 }])
  expect(plans[0].blueprints).toEqual([{ id: 'blueprint_multi_room_skin_0', status: 'Researched' }])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})


test('integra decoraciones en el borrador global sin controles ficticios', async ({ page }) => {
  const plans: Array<Record<string, unknown>> = []
  await open(page, { save: PROGRESS_SAVE, width: 320 })
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => {
    const plan = route.request().postDataJSON()
    plans.push(plan)
    return route.fulfill({ json: prepared(plan, [
      ['decorations', 'Decoraciones', 3],
    ]) })
  })

  await openCategory(page, 'Decoraciones')
  await expect(page.getByText('Vestíbulo actual: Common')).toBeVisible()
  await page.getByText('multi · 1/1 obtenidas').click()
  await expect(page.getByText('Sala uno')).toBeVisible()
  await expect(page.getByText('Obtenida', { exact: false }).first()).toBeVisible()
  await page.getByLabel('Desbloquear Caja fuerte').check()
  await page.getByLabel('Desbloquear Zona de alimentación de mascotas').check()
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  await page.getByLabel('Nivel o progreso de Book').fill('5')
  await expect(page.getByTestId('editor-bar')).toContainText('3 cambios')
  await expect(page.locator('input[aria-label="Desbloquear Máquina de huevos"]')).toBeDisabled()
  await page.screenshot({ path: 'test-results/edicion-numerica/decoraciones-320.png' })

  await page.getByTestId('editor-bar').getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(page.getByTestId('unified-preview')).toBeVisible()
  expect(plans).toHaveLength(1)
  expect(plans[0].decorations).toEqual({ objects: ['ObjectSafe', 'PetFood'], levels: [{ id: 'Book', level: 5 }] })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
