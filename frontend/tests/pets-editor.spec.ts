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
const PETS = [{
  id: 'Cat', numeric_id: 0, name: { en: 'Chilly', es: 'Fresco' }, unlocked: true, present: true,
  value_type: 'bool', editable: true, insertable: false, path: 'gameData.petUnlock.Cat',
  skins: ['Cat1'], reason: null,
}, {
  id: 'Cat1', numeric_id: 20, name: { en: 'Smokey', es: 'Humito' }, unlocked: false, present: true,
  value_type: 'bool', editable: true, insertable: false, path: 'gameData.petUnlock.Cat1',
  skins: [], reason: null,
}, {
  id: 'Rabbit', numeric_id: 6, name: { en: 'BonBon', es: 'Bombón' }, unlocked: false, present: false,
  value_type: null, editable: true, insertable: true, path: 'gameData.petUnlock.Rabbit',
  skins: ['Rabbit1'], reason: null,
}]
const SKINS = [{
  id: 'Cat1', pet_code: 'Cat1', base_pet: 'Cat', skin_index: 1,
  name: { en: 'Smokey', es: 'Humito' }, unlocked: false, present: true, value_type: 'bool',
  editable: true, insertable: false, path: 'gameData.petUnlock.Cat1', base_unlocked: true,
  dependency_note: 'Seleccionar esta variante también desbloquea su mascota base si está pendiente.',
}, {
  id: 'Rabbit1', pet_code: 'Rabbit1', base_pet: 'Rabbit', skin_index: 1,
  name: { en: 'Snow', es: 'Nieve' }, unlocked: false, present: false, value_type: null,
  editable: true, insertable: true, path: 'gameData.petUnlock.Rabbit1', base_unlocked: false,
  dependency_note: 'Seleccionar esta variante también desbloquea su mascota base si está pendiente.',
}]
const ADVANCED = {
  materials: [], seeds: [],
  season_coin: {
    value: 100, value_type: 'int', available: true, path: 'seasonData.coin', min: 0,
    max: 2_147_483_647, owner_reference: 'season_data:coin', note: '',
  },
  reborn_card: {
    value: true, available: true, path: 'gameData.rebornCard', experimental: false,
    local_reference: 'shared_pref:reborn_card = 1', remote_representation: 'gameData.rebornCard (bool)',
    projection: 'CoverPlayerPref', limitation: 'Confirmado por el propietario.', evidence_level: 'E3',
  },
  battle_pass: {
    records: [], selected_season_id: null, active_season_id: null,
    active_matches_selected: null, note: '',
  },
  pets: PETS,
  pet_skins: SKINS,
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
    skin_note: 'No se encontró un mapa de bloqueo separado.',
    food_note: 'Los alimentos comparten el escritor de itemData.materials.',
    progression_note: 'La intimidad se muestra en solo lectura.',
  },
  policy: {
    field: 'advanced', experimental: true, evidence_level: 'E2', min: 0, max: 2_147_483_647,
    max_note: '', material_fish_note: '',
    confirmed_functions: ['materials', 'seeds', 'season_coin', 'reborn_card'],
    experimental_functions: ['battle_pass', 'pets', 'pet_food'],
  },
}
const SAVE = {
  verified: true, bytes: 505, sha256: SHA, gems: 1001, fish_chip: 3,
  fish_chip_path: 'gameData.fishChip', material_fish: 3,
  material_fish_path: 'itemData.materials.material_fish', cumulative_fish_count: 18,
  cumulative_fish_count_path: 'itemData.cumulativeFishCount', size: 505,
  serialzed_version: 1, report: null,
  remote: { source: 'modern-cloud', size: 505, sha256: SHA }, advanced: ADVANCED,
}
const PLAN = {
  materials: [], seeds: [],
  pets: ['Cat1', 'Rabbit', 'Rabbit1'],
  pet_food: [{ id: 'material_grain', value: 1_000 }],
}
const PREPARED = {
  remote: { source: 'modern-cloud', size: 505, sha256: SHA },
  field: 'advanced', plan: PLAN, changed: true,
  backup: {
    id: BACKUP_ID, created_at: '2026-11-24T02:00:00Z', field: 'advanced', changed: true,
    original_size: 505, original_sha256: SHA, original_gems: 0, candidate_size: 505,
    candidate_sha256: CANDIDATE, candidate_gems: 6, remote_source: 'modern-cloud',
    remote_size: 505, remote_sha256: SHA, advanced_plan: PLAN,
  },
  changes: [
    { path: 'itemData.materials.material_grain', before: 4, after: 1_000 },
    { path: 'gameData.petUnlock.Cat1', before: false, after: true },
    { path: 'gameData.petUnlock.Rabbit', before: null, after: true },
    { path: 'gameData.petUnlock.Rabbit1', before: null, after: true },
  ],
  original_value: 0, new_value: 4, experimental: true,
  candidate_size: 505, candidate_sha256: CANDIDATE,
  byte_diff: {
    original_size: 505, modified_size: 505, first_difference: 1, common_prefix: 1,
    common_suffix: 503, changed_original_bytes: 1, changed_modified_bytes: 1,
    original_sha256: SHA, modified_sha256: CANDIDATE,
  },
  changed_fields: [
    'itemData.materials.material_grain', 'gameData.petUnlock.Cat1',
    'gameData.petUnlock.Rabbit', 'gameData.petUnlock.Rabbit1',
  ],
  validation: {
    valid: true, structure_valid: true, only_advanced_changed: true,
    experimental: true, evidence_level: 'E2', message: 'Solo cambiaron las rutas autorizadas.',
  },
}

async function mockBase(page: Page) {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1_048_576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [] } }))
  await page.route('**/api/v1/cloud/native/config', (route) => route.fulfill({
    json: { ...CONFIG, session: { ...ACTIVE, save: SAVE } },
  }))
  await page.route('**/api/v1/cloud/native/backups', (route) => route.fulfill({ json: { backups: [] } }))
}

test.fixme('desbloquea mascotas y variantes, edita alimento y conserva la progresión de solo lectura', async ({ page }) => {
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
  await page.goto('/editor/mascotas')
  await expect(page.getByRole('heading', { name: 'Mascotas' })).toBeVisible()
  await expect(page.getByText('Experimental E2')).toBeVisible()
  await expect(page.getByText('1 / 3', { exact: true })).toBeVisible()

  await page.getByLabel('Cantidad de Bocadillos de mascotas').fill('1000')
  await page.getByText('Skins de mascota', { exact: true }).click()
  await page.getByLabel('Seleccionar skin Humito').check()
  await page.getByLabel('Seleccionar skin Nieve').check()
  await expect(page.getByTestId('pets-change-count')).toHaveText('4')

  await page.getByText('Progresión de mascotas', { exact: true }).click()
  await expect(page.getByText('Completa').first()).toBeVisible()
  await expect(page.getByText('El máximo no se escribe ni se simula')).toBeVisible()

  await page.getByRole('button', { name: 'Preparar lote de mascotas' }).click()
  await expect(page.getByRole('heading', { name: 'Revisar lote preparado' })).toBeVisible()
  await expect(page.locator('.advanced-preview').getByText('gameData.petUnlock.Rabbit1')).toBeVisible()
  await expect(page.getByText('Las variantes de skin seleccionadas incluyen su mascota base')).toBeVisible()
  await page.getByLabel(/Confirmo que quiero sobrescribir la partida/).check()
  await page.getByRole('button', { name: 'Subir lote y verificar' }).click()
  await expect(page.getByText('Lote subido y verificado en la nube')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test.fixme('filtra mascotas bloqueadas y no permite cantidades inválidas de alimento', async ({ page }) => {
  await mockBase(page)
  await page.goto('/editor/mascotas')
  const pets = page.locator('details').filter({ has: page.getByText('Catálogo de mascotas', { exact: true }) })
  await pets.getByLabel('Estado').selectOption('locked')
  await expect(pets.getByText('Humito')).toBeVisible()
  await expect(pets.getByText('Fresco', { exact: true })).toHaveCount(0)
  await page.getByLabel('Cantidad de Bocadillos de mascotas').fill('999999999999')
  await expect(page.getByText('formato inválido')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Preparar lote de mascotas' })).toBeDisabled()
})