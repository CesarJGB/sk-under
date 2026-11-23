import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { expect, test } from '@playwright/test'

const original = Buffer.from('copia sintetica')
const sha256 = createHash('sha256').update(original).digest('hex')
const format = {
  id: 'sk-local-des-cbc', name: 'Guardado local de Soul Knight', version: '8.6.0 (muestras)',
  extensions: ['.data'], compatibility: 'read_only', description: 'Inspección y copia intacta.',
}
const validation = { valid: true, changes: [], output_sha256: sha256, output_byte_size: original.length }

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', access_mode: 'local', max_file_bytes: 1048576 },
  }))
  await page.route('**/api/v1/formats', (route) => route.fulfill({ json: { formats: [format] } }))
  await page.route('**/api/v1/files/inspect', (route) => route.fulfill({
    json: {
      format, sha256, byte_size: original.length,
      fields: [{
        id: 'save_type', label: 'Tipo de archivo', value: 'Inventario', type: 'string',
        category: 'Formato', editable: false, min_length: 0, max_length: 10,
      }],
    },
  }))
  await page.goto('/importar')
  const picker = page.locator('#local-file')
  await expect(picker).toBeEnabled()
  await picker.setInputFiles({ name: 'sintetico.data', mimeType: 'application/octet-stream', buffer: original })
  await page.getByRole('link', { name: 'Preparar copia intacta' }).click()
})

for (const mismatch of [
  { field: 'hash', changes: { output_sha256: '0'.repeat(64) } },
  { field: 'tamaño', changes: { output_byte_size: original.length + 1 } },
]) {
  test(`bloquea la descarga si el ${mismatch.field} informado al validar difiere`, async ({ page }) => {
    await page.route('**/api/v1/files/validate', (route) => route.fulfill({
      json: { ...validation, ...mismatch.changes },
    }))
    await page.getByRole('button', { name: 'Validar copia' }).click()
    await expect(page.getByRole('alert')).toContainText('La copia validada difiere del archivo importado.')
    await expect(page.getByRole('button', { name: 'Descargar copia' })).toHaveCount(0)
  })
}

test('bloquea los bytes alterados aunque la validación y el tamaño coincidan', async ({ page }) => {
  await page.route('**/api/v1/files/validate', (route) => route.fulfill({ json: validation }))
  await page.route('**/api/v1/files/export', (route) => route.fulfill({
    contentType: 'application/octet-stream', body: Buffer.from('Copia sintetica'),
  }))
  let downloaded = false
  page.on('download', () => { downloaded = true })
  await page.getByRole('button', { name: 'Validar copia' }).click()
  await expect(page.getByText('SHA-256 coincide con el original', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Descargar copia' }).click()
  await expect(page.getByRole('alert')).toContainText('El SHA-256 de la descarga difiere del archivo importado.')
  await expect(page.getByText('SHA-256 coincide con el original', { exact: false })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Descargar de nuevo' })).toHaveCount(0)
  expect(downloaded).toBe(false)
})

test('mantiene espacio para el nombre y muestra el estado debajo en móvil', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 760 })
  await page.getByRole('link', { name: 'Volver a la inspección' }).click()
  await expect(page.getByRole('heading', { name: 'Inspeccionar copia' })).toBeVisible()
  const name = await page.getByText('sintetico.data', { exact: true }).boundingBox()
  const badge = await page.getByRole('status').filter({ hasText: 'Solo lectura' }).boundingBox()
  assert.ok(name && badge)
  expect(name.y + name.height).toBeLessThanOrEqual(badge.y)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
})
