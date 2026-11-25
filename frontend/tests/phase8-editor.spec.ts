import { expect, test, type Page, type Route } from '@playwright/test'

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
  account: { label: PROFILE.label, distribution: 'android-global', distribution_label: 'Android Global (GP)', platform: 'android' },
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
  limits?: { max_gems?: number }
} = {}) {
  const save = options.save ?? SESSION_SAVE
  const sessionSave = options.sessionSave === undefined ? save : options.sessionSave
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: { status: 'ok', access_mode: 'local', max_file_bytes: 1048576 } }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({ json: { ...CONFIG, session: { ...ACTIVE, ...options.limits, save: sessionSave } } }))
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.route('**/api/v1/cloud/native/save', options.download ?? ((route) => route.fulfill({ json: downloaded(save) })))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(options.path ?? '/editor')
  if (!options.path && sessionSave) await expect(page.getByTestId('quick-edit')).toBeVisible()
}

async function openCategory(page: Page, name: string) {
  await page.getByRole('tab', { name: 'Categorías' }).click()
  await page.getByRole('button', { name: new RegExp(`^${name}($| Cambios pendientes)`) }).click()
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

test('la edición rápida es la pantalla inicial y comparte el borrador con categorías', async ({ page }) => {
  await open(page)
  await expect(page.getByRole('tab', { name: 'Rápida' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
  await page.getByLabel('Activar Todos los personajes').check()
  await expect(page.getByTestId('editor-bar')).toContainText('3 cambios')
  await page.getByRole('tab', { name: 'Categorías' }).click()
  await page.getByRole('button', { name: /Personajes/ }).click()
  await page.getByRole('checkbox', { name: 'Mage' }).uncheck()
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  await page.getByRole('tab', { name: 'Rápida' }).click()
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
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
  const header = page.locator('.editor-top')
  await expect(header).toContainText('Descargando partida…')
  await expect(header).toContainText(PROFILE.label)
  await expect(header).toContainText('Android Global · 8.8.0')
  await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toHaveCount(0)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Editor')
  await expect(page.getByRole('textbox', { name: 'Gemas', exact: true })).toBeDisabled()
  release()
  await expect(header).toContainText('Partida cargada')
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
  await expect(page.locator('.editor-top')).toContainText('Partida pendiente de descargar')
  await page.getByRole('button', { name: 'Descargar partida' }).click()
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
  await page.getByRole('tab', { name: 'Rápida' }).click()
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
  await page.getByRole('button', { name: 'Descargar partida' }).click()
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
  await page.getByRole('link', { name: 'Volver a Partida' }).click()
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
  await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toBeVisible()
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
  await page.getByRole('tab', { name: 'Rápida' }).click()
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
    await route.fulfill({ json: { backup_id: BACKUP.id, accepted: true, persisted: false } })
  })
  await page.getByLabel('Activar Todos los personajes').check()
  await page.getByRole('button', { name: 'Guardar', exact: true }).click()
  await page.getByLabel(/Confirmo subir el candidato/).check()
  await page.getByRole('button', { name: 'Guardar en la nube' }).click()
  const bar = page.getByTestId('editor-bar')
  await expect(bar).toContainText('Guardando y verificando…')
  await expect(bar.getByRole('button', { name: 'Guardar en la nube' })).toBeDisabled()
  await expect(bar.getByRole('button', { name: 'Descartar' })).toBeDisabled()
  await page.getByRole('link', { name: 'Volver a Partida' }).click()
  const leave = page.getByRole('dialog', { name: 'Operación en curso' })
  await expect(leave).toBeVisible()
  await expect(leave.getByRole('button', { name: 'Descartar y salir' })).toHaveCount(0)
  await leave.getByRole('button', { name: 'Seguir editando' }).click()
  allowUpload()
  await expect(bar).toContainText('Revisa el resultado')
  await expect(bar).toContainText('3 cambios')
  await expect(page.getByText('No se pudo verificar la subida.', { exact: false })).toBeVisible()
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
    await expect(page.getByTestId('category-grid').getByRole('button')).toHaveCount(9)
    if (size.width <= 430) {
      expect(await page.locator('.category-grid').evaluate((grid) => getComputedStyle(grid).gridTemplateColumns.split(' ').length)).toBe(3)
    }
    expect(await page.locator('.category-icon').evaluateAll((icons) =>
      Promise.all(icons.map((icon) => (icon as HTMLImageElement).decode())).then(() => true))).toBe(true)
    await screenshot(`categorias-${size.width}`)
    await page.getByRole('button', { name: 'Materiales' }).click()
    const minimum = page.getByRole('textbox', { name: 'Cantidad mínima', exact: true })
    await minimum.fill('2147483647')
    expect(await minimum.evaluate(fits), `mínimo de diez dígitos a ${size.width} px`).toBe(true)
    await minimum.clear()
    await minimum.blur()
    await screenshot(`materiales-${size.width}`)
    await page.getByRole('tab', { name: 'Rápida' }).click()
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
