import { expect, test, type Page } from '@playwright/test'

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

async function open(page: Page) {
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: { status: 'ok', access_mode: 'local', max_file_bytes: 1048576 } }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({ json: { ...CONFIG, session: ACTIVE } }))
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
  await page.route('**/api/v1/cloud/native/save', (route) => route.fulfill({ json: SESSION_SAVE }))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/editor')
  await expect(page.getByTestId('quick-edit')).toBeVisible()
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
    return route.fulfill({ json: { action: 'confirm', backup_id: BACKUP.id, field: 'unified', uploaded: true, accepted: true, persisted: true, already_original: false, expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505, remote_gems: 1200, remote_characters: 4, status: 200, message: 'Verificado.' } })
  })
  await page.getByLabel('Activar Gemas').check()
  await page.getByLabel('Gemas', { exact: true }).fill('1200')
  await page.getByLabel('Activar Todos los personajes').check()
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByTestId('unified-preview')).toContainText('Gemas')
  expect(payload).toMatchObject({ gems: 1200 })
  expect((payload as unknown as { characters: string[] }).characters.sort()).toEqual(['Alchemist', 'Mage', 'Ranger'])
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
  await page.getByLabel('Activar Materiales').check()
  await page.getByLabel('Materiales', { exact: true }).fill('10')
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  page.once('dialog', (dialog) => dialog.dismiss())
  await page.getByRole('button', { name: 'Descartar' }).click()
  await expect(page.getByTestId('editor-bar')).toContainText('2 cambios')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Descartar' }).click()
  await expect(page.getByTestId('editor-bar')).toContainText('0 cambios')
})

test('un conflicto remoto conserva el borrador', async ({ page }) => {
  await open(page)
  await page.getByLabel('Activar Todos los personajes').check()
  await page.route('**/api/v1/cloud/native/prepare-unified', (route) => route.fulfill({ status: 409, json: { error: { code: 'cloud_remote_changed', message: 'La partida cambió.', issues: [] } } }))
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('La partida cambió en la nube', { exact: false })).toBeVisible()
  await expect(page.getByTestId('editor-bar')).toContainText('3 cambios')
})

test('capturas móviles sin desbordamiento horizontal', async ({ page }) => {
  await open(page)
  const sizes = [
    { width: 320, height: 568 }, { width: 360, height: 800 }, { width: 375, height: 812 },
    { width: 390, height: 844 }, { width: 430, height: 932 },
    { width: 768, height: 1024 }, { width: 1280, height: 800 },
  ]
  for (const size of sizes) {
    await page.setViewportSize(size)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${size.width}`).toBe(true)
    await expect(page.getByTestId('editor-bar')).toBeVisible()
    await page.screenshot({ path: `test-results/phase8-quick-${size.width}.png`, fullPage: true })
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'test-results/phase8-quick.png', fullPage: true })
  await page.getByRole('tab', { name: 'Categorías' }).click()
  await page.screenshot({ path: 'test-results/phase8-categories.png', fullPage: true })
  for (const size of sizes) {
    await page.setViewportSize(size)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${size.width}`).toBe(true)
    await expect(page.getByTestId('editor-bar')).toBeVisible()
    await page.screenshot({ path: `test-results/phase8-categories-${size.width}.png`, fullPage: true })
  }
})
