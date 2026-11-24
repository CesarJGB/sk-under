import { expect, test, type Page } from '@playwright/test'

const SHA = 'a'.repeat(64)
const CANDIDATE = 'b'.repeat(64)
const BACKUP_ID = 'c'.repeat(32)
const PROFILE = {
  id: '1'.repeat(32), label: 'Instalación Android Global', distribution: 'android-global',
  installation_ready: true, bound: true, write_allowed: true,
}
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
const CONFIG = {
  available: true, enabled: true, configured: true, write_enabled: true, secure: false,
  min_gems: 0, max_gems: 2_147_483_647, login_available: true,
  auto_identity: true, requires_profile_selection: false,
  profiles: [], distributions: [],
  session: { active: false, reason: 'none' }, problem_code: null, message: null,
}
const ROW_BASE = {
  plant_id: null, value_type: 'int', path: '', reason: null,
}
const ADVANCED = {
  materials: [{
    ...ROW_BASE, id: 'material_wood', name: { en: 'Wood', es: 'Madera' }, subcategory: 'others',
    count: 4, owned: true, known: true, editable: true, insertable: true,
    path: 'itemData.materials.material_wood',
  }, {
    ...ROW_BASE, id: 'material_stone', name: { en: 'Stone', es: 'Piedra' }, subcategory: 'weapon_fragment',
    count: 2, owned: true, known: true, editable: true, insertable: true,
    path: 'itemData.materials.material_stone',
  }, {
    ...ROW_BASE, id: 'material_fish', name: { en: 'Fish Chip', es: 'Ficha de pez' }, subcategory: 'others',
    count: 3, owned: true, known: true, editable: false, insertable: false,
    reason: 'Es el espejo de gameData.fishChip; se edita desde el control de fichas de pesca.',
    path: 'itemData.materials.material_fish',
  }, {
    ...ROW_BASE, id: 'unknown_custom_item', name: {}, subcategory: null,
    count: 99, owned: true, known: false, editable: false, insertable: false,
    reason: 'Identificador desconocido; se conserva sin cambios.',
    path: 'itemData.materials.unknown_custom_item',
  }],
  seeds: [{
    ...ROW_BASE, id: 'plant_carrot_seed', name: { en: 'Carrot', es: 'Semilla de zanahoria' },
    subcategory: 'garden_seed', plant_id: 'plant_carrot', count: 0, owned: false,
    known: true, editable: true, insertable: true, path: 'itemData.seeds.plant_carrot_seed',
  }],
  season_coin: {
    value: 100, value_type: 'int', available: true, path: 'seasonData.coin',
    min: 0, max: 2_147_483_647,
    owner_reference: 'season_data:coin (guía del propietario)',
    note: 'Entero estructural; no hay tope de juego confirmado.',
  },
  reborn_card: {
    value: false, available: true, path: 'gameData.rebornCard', experimental: false,
    local_reference: 'shared_pref:reborn_card = 1',
    remote_representation: 'gameData.rebornCard (bool)',
    projection: 'CoverPlayerPref',
    limitation: 'La preferencia local no se escribe remotamente; la proyección no está confirmada en dispositivo.',
    evidence_level: 'E3',
  },
  battle_pass: {
    records: [{
      index: 0, key: 6, season_id: 6, cur_level: 40, cur_exp: 10, has_buy: true,
      free_claimed_level: 40, paid_claimed_level: 40, max_level: null, editable: true, error: null,
    }, {
      index: 1, key: 7, season_id: 7, cur_level: 10, cur_exp: 0, has_buy: false,
      free_claimed_level: 4, paid_claimed_level: 0, max_level: null, editable: true, error: null,
    }],
    selected_season_id: 7, active_season_id: 7, active_matches_selected: true,
    note: 'Se selecciona el seasonID más alto.',
  },
  pets: [{
    id: 'Cat', numeric_id: 0, name: { en: 'Chilly', es: 'Fresco' }, unlocked: true, present: true,
    value_type: 'bool', editable: true, insertable: false, path: 'gameData.petUnlock.Cat',
    skins: ['Cat1'], reason: null,
  }, {
    id: 'Cat1', numeric_id: 20, name: { en: 'Smokey', es: 'Humito' }, unlocked: false, present: true,
    value_type: 'bool', editable: true, insertable: false, path: 'gameData.petUnlock.Cat1',
    skins: [], reason: null,
  }],
  pet_skins: [{
    id: 'Cat1', pet_code: 'Cat1', base_pet: 'Cat', skin_index: 1,
    name: { en: 'Smokey', es: 'Humito' }, unlocked: false, present: true, value_type: 'bool',
    editable: true, insertable: false, path: 'gameData.petUnlock.Cat1', base_unlocked: true,
    dependency_note: 'Seleccionar esta variante también desbloquea su mascota base si está pendiente.',
  }],
  pet_food: [{
    id: 'material_grain', name: { en: 'Pet Treats', es: 'Bocadillos de mascotas' }, count: 4,
    value_type: 'int', owned: true, editable: true, insertable: false,
    path: 'itemData.materials.material_grain', field: 'itemData.materials',
    population: 'itemData.materials', reason: null,
  }, {
    id: 'material_battery', name: { en: 'Battery', es: 'Batería' }, count: null,
    value_type: null, owned: false, editable: true, insertable: true,
    path: 'itemData.materials.material_battery', field: 'itemData.materials',
    population: 'itemData.materials', reason: null,
  }],
  pet_progression: {
    available: true, path: 'statisticData.event2Count', read_only: true,
    global_full_count: 1, full_count_key: 'pet_full_intimacy',
    entries: [{
      id: 'Cat', numeric_id: 0, name: { en: 'Chilly', es: 'Fresco' }, present: true,
      intimacy: 240, full: true, action_unlocked: true, value_type: null, max: null,
      max_note: 'Máximo específico de la mascota.', path: 'statisticData.event2Count.pet_0_intimacy',
    }],
    note: 'La intimidad se muestra en solo lectura.',
  },
  pet_policy: {
    field: 'pets', experimental: true, evidence_level: 'E2', path: 'gameData.petUnlock',
    skin_note: 'No se encontró un mapa de bloqueo de skins separado.',
    food_note: 'Los alimentos comparten el escritor de itemData.materials.',
    progression_note: 'La intimidad se muestra en solo lectura.',
  },
  policy: {
    field: 'advanced', experimental: true, evidence_level: 'E2', min: 0, max: 2_147_483_647,
    max_note: 'int32 estructural, no un tope de juego confirmado.',
    material_fish_note: 'material_fish se edita desde fichas de pesca.',
    confirmed_functions: ['materials', 'seeds', 'season_coin', 'reborn_card'],
    experimental_functions: ['battle_pass', 'pets', 'pet_food'],
  },
}
const SAVE = {
  verified: true, bytes: 505, sha256: SHA, gems: 1001, fish_chip: 3,
  fish_chip_path: 'gameData.fishChip', material_fish: 3,
  material_fish_path: 'itemData.materials.material_fish',
  cumulative_fish_count: 18,
  cumulative_fish_count_path: 'itemData.cumulativeFishCount',
  fish_chip_write_policy: 'confirmed_by_owner',
  size: 505, serialzed_version: 1, report: null,
  remote: { source: 'modern-cloud', size: 505, sha256: SHA },
  advanced: ADVANCED,
}
const PLAN = {
  materials: [{ id: 'material_wood', value: 25 }, { id: 'material_stone', value: 25 }],
  seeds: [{ id: 'plant_carrot_seed', value: 7 }],
  season_coin: 100000,
  reborn_card: true,
  battle_pass: { season_id: 7, cur_level: 50, has_buy: true },
}
const PREPARED = {
  remote: { source: 'modern-cloud', size: 505, sha256: SHA },
  field: 'advanced', plan: PLAN, changed: true,
  backup: {
    id: BACKUP_ID, created_at: '2026-11-24T02:00:00Z', field: 'advanced', changed: true,
    original_size: 505, original_sha256: SHA, original_gems: 0,
    candidate_size: 505, candidate_sha256: CANDIDATE, candidate_gems: 6,
    remote_source: 'modern-cloud', remote_size: 505, remote_sha256: SHA,
    advanced_plan: PLAN,
  },
  changes: [
    { path: 'itemData.materials.material_wood', before: 4, after: 25 },
    { path: 'itemData.materials.material_stone', before: 2, after: 25 },
    { path: 'itemData.seeds.plant_carrot_seed', before: 0, after: 7 },
    { path: 'seasonData.coin', before: 100, after: 100000 },
    { path: 'gameData.rebornCard', before: false, after: true },
    { path: 'battlePassSaveData.seasonData.1.Value.curLevel', before: 10, after: 50 },
    { path: 'battlePassSaveData.seasonData.1.Value.hasBuy', before: false, after: true },
  ],
  original_value: 0, new_value: 7, experimental: true,
  candidate_size: 505, candidate_sha256: CANDIDATE,
  byte_diff: {
    original_size: 505, modified_size: 505, first_difference: 1, common_prefix: 1,
    common_suffix: 503, changed_original_bytes: 1, changed_modified_bytes: 1,
    original_sha256: SHA, modified_sha256: CANDIDATE,
  },
  changed_fields: [
    'itemData.materials.material_wood', 'itemData.materials.material_stone',
    'itemData.seeds.plant_carrot_seed', 'seasonData.coin', 'gameData.rebornCard',
    'battlePassSaveData.seasonData.1.Value.curLevel',
    'battlePassSaveData.seasonData.1.Value.hasBuy',
  ],
  validation: {
    valid: true, structure_valid: true, only_advanced_changed: true,
    experimental: true, evidence_level: 'E2',
    message: 'Solo cambiaron las rutas avanzadas autorizadas.',
  },
}

async function mockBase(page: Page, save: object = SAVE) {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1_048_576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({
    json: { ...CONFIG, session: { ...ACTIVE, save } },
  }))
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
}

test('edita materiales, semillas, monedas, renacimiento y pase en un lote confirmado', async ({ page }) => {
  await mockBase(page)
  await page.route('**/api/v1/cloud/native/prepare-advanced', (route) => {
    expect(route.request().postDataJSON()).toEqual({ ...PLAN, source_sha256: SHA })
    return route.fulfill({ json: PREPARED })
  })
  await page.route('**/api/v1/cloud/native/confirm', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      backup_id: BACKUP_ID, expected_sha256: CANDIDATE, confirmation: 'SUBIR',
    })
    return route.fulfill({ json: {
      action: 'confirm', backup_id: BACKUP_ID, field: 'advanced', uploaded: true,
      accepted: true, persisted: true, already_original: false,
      expected_sha256: CANDIDATE, remote_sha256: CANDIDATE, remote_size: 505,
      remote_gems: 1001, status: 200,
      message: 'La descarga posterior coincide con el lote avanzado.',
    } })
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByRole('heading', { name: 'Materiales, recursos y pase' })).toBeVisible()
  await expect(page.getByText('Identificador desconocido; se conserva sin cambios.')).toBeVisible()
  await expect(page.getByText('Es el espejo de gameData.fishChip')).toBeVisible()

  await page.getByLabel('Buscar materiales').fill('piedra')
  await expect(page.getByLabel('Nueva cantidad para Piedra')).toBeVisible()
  await expect(page.getByLabel('Nueva cantidad para Madera')).toHaveCount(0)
  await page.getByLabel('Buscar materiales').fill('')
  const materials = page.locator('details').filter({
    has: page.getByText('Materiales', { exact: true }),
  })
  await materials.getByRole('button', { name: 'Seleccionar 2 editables' }).click()
  await materials.getByLabel('Cantidad para seleccionados').fill('25')
  await materials.getByRole('button', { name: 'Aplicar a 2' }).click()
  await page.getByText('Semillas', { exact: true }).click()
  await expect(page.getByLabel('Nueva cantidad para Semilla de zanahoria')).toBeVisible()
  await page.getByLabel('Nueva cantidad para Semilla de zanahoria').fill('7')

  await page.getByText('Monedas y recursos', { exact: true }).click()
  await expect(page.getByLabel('Monedas de temporada (seasonData.coin)')).toBeVisible()
  await page.getByLabel('Monedas de temporada (seasonData.coin)').fill('100000')
  await page.getByText('Beneficios permanentes', { exact: true }).click()
  await expect(page.getByLabel(/Activar gameData.rebornCard/)).toBeVisible()
  await page.getByLabel(/Activar gameData.rebornCard/).check()

  await page.getByText('Pase de batalla', { exact: true }).click()
  const seasonSelect = page.getByRole('combobox', { name: /Temporada/ })
  await expect(seasonSelect).toBeVisible()
  await expect(seasonSelect).toHaveValue('7')
  await page.getByLabel('Nivel (curLevel)').fill('50')
  await page.getByLabel('Estado premium local (hasBuy)').check()
  await expect(page.getByText('No hay un campo de nivel máximo respaldado')).toBeVisible()

  await expect(page.getByTestId('advanced-change-count')).toHaveText('6')
  await page.getByRole('button', { name: 'Preparar lote de cambios' }).click()
  await expect(page.getByRole('heading', { name: 'Revisar lote preparado' })).toBeVisible()
  await expect(page.locator('.advanced-preview').getByText('seasonData.coin', { exact: true })).toBeVisible()
  await page.getByLabel(/Confirmo que quiero sobrescribir la partida/).check()
  await page.getByRole('button', { name: 'Subir lote y verificar' }).click()
  await expect(page.getByText('Lote subido y verificado en la nube', { exact: false })).toBeVisible()
  await expect(page.getByText('El pase de batalla sigue pendiente de esa prueba.')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('el control rápido de recompensas acumuladas usa 21 y conserva valores superiores', async ({ page }) => {
  const save = { ...SAVE, cumulative_fish_count: 18, advanced: null }
  await mockBase(page, save)
  const requested: number[] = []
  await page.route('**/api/v1/cloud/native/prepare-fish-progress', (route) => {
    requested.push(route.request().postDataJSON().new_cumulative_fish_count)
    return route.fulfill({ json: {
      remote: { source: 'modern-cloud', size: 505, sha256: SHA },
      backup: { ...PREPARED.backup, field: 'fish_progress', candidate_gems: 21 },
      field: 'itemData.cumulativeFishCount', original_cumulative_fish_count: 18,
      new_cumulative_fish_count: 21, original_value: 18, new_value: 21,
      experimental: true, changed: true, candidate_size: 505, candidate_sha256: CANDIDATE,
      changed_fields: ['itemData.cumulativeFishCount'], byte_diff: PREPARED.byte_diff,
      validation: {
        valid: true, structure_valid: true, only_fish_progress_changed: true,
        experimental: true, evidence_level: 'E2',
        message: 'Campo modificado: itemData.cumulativeFishCount.',
      },
    } })
  })

  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await page.getByRole('button', { name: 'Desbloquear todas las recompensas acumuladas' }).click()
  expect(requested).toEqual([21])
  await expect(page.getByRole('heading', { name: 'Revisar progreso acumulado' })).toBeVisible()
  await expect(page.getByText('no modifica el saldo de fichas')).toBeVisible()
})

test('no ofrece reducir un progreso acumulado que ya supera 20', async ({ page }) => {
  await mockBase(page, { ...SAVE, cumulative_fish_count: 42, advanced: null })
  await page.goto('/partida')
  await page.getByRole('link', { name: 'Abrir Editor' }).click()
  await expect(page.getByText('El progreso acumulado ya supera 20.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Desbloquear todas las recompensas acumuladas' })).toHaveCount(0)
})