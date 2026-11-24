import { ChevronDown, Search, WandSparkles } from 'lucide-react'
import { useState } from 'react'
import {
  ApiProblem, nativeAuth,
  type LabAdvanced, type LabAdvancedPlan, type LabAdvancedPrepared,
  type LabItemRow, type LabWriteResult,
} from '../api'
import { Loading, Notice, Problem } from '../ui'
import { useOperation } from '../useOperation'

const numberFormat = new Intl.NumberFormat('es-MX')
const MAX_VALUE = 2_147_483_647

const CATEGORY_LABELS: Record<string, string> = {
  weapon_fragment: 'Fragmentos de armas',
  skin_fragment: 'Fragmentos de skin',
  tape: 'Cintas',
  activity: 'Actividad',
  skill: 'Habilidades',
  others: 'Otros',
  garden_seed: 'Semillas de jardín',
}

function itemLabel(row: LabItemRow) {
  return row.name.es?.trim() || row.name.en?.trim() || row.id
}

function categoryLabel(value: string | null) {
  if (!value) return 'Sin categoría'
  return CATEGORY_LABELS[value] ?? value
}

function parseQuantity(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) && parsed >= 0 && parsed <= MAX_VALUE ? parsed : null
}

type ItemCollectionProps = {
  title: string
  description: string
  rows: LabItemRow[]
  query: string
  onQuery: (value: string) => void
  category: string
  onCategory: (value: string) => void
  categories: string[]
  selected: Set<string>
  onSelected: (next: Set<string>) => void
  edits: Record<string, string>
  onEdit: (id: string, value: string) => void
  disabled: boolean
}

function ItemCollection({
  title, description, rows, query, onQuery, category, onCategory, categories,
  selected, onSelected, edits, onEdit, disabled,
}: ItemCollectionProps) {
  const [showAll, setShowAll] = useState(false)
  const [bulk, setBulk] = useState('')
  const needle = query.trim().toLowerCase()
  const filtered = rows.filter((row) => {
    if (category && row.subcategory !== category) return false
    if (!needle) return true
    return row.id.toLowerCase().includes(needle)
      || (row.name.es ?? '').toLowerCase().includes(needle)
      || (row.name.en ?? '').toLowerCase().includes(needle)
  })
  const editableRows = filtered.filter((row) => row.editable)
  const visible = showAll ? filtered : filtered.slice(0, 40)
  const allSelected = editableRows.length > 0 && editableRows.every((row) => selected.has(row.id))
  const bulkValue = parseQuantity(bulk)
  const owned = rows.filter((row) => row.owned).length
  const planned = Object.entries(edits).filter(([id, value]) => {
    const row = rows.find((candidate) => candidate.id === id)
    const parsed = parseQuantity(value)
    return row && parsed != null && parsed !== row.count
  }).length

  function toggle(id: string) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelected(next)
  }

  function toggleAll() {
    const next = new Set(selected)
    for (const row of editableRows) {
      if (allSelected) next.delete(row.id)
      else next.add(row.id)
    }
    onSelected(next)
  }

  function applyBulk() {
    if (bulkValue == null) return
    onSelected(new Set(selected))
    for (const id of selected) onEdit(id, String(bulkValue))
  }

  return <details className="advanced-panel" open={title === 'Materiales'}>
    <summary>
      <span><strong>{title}</strong><small>{description}</small></span>
      <span className="advanced-count">{numberFormat.format(owned)} en la partida · {planned} por cambiar</span>
      <ChevronDown size={17} aria-hidden="true" />
    </summary>
    <div className="advanced-panel-body">
      <div className="advanced-toolbar">
        <label className="advanced-search"><Search size={15} aria-hidden="true" />
          <input value={query} disabled={disabled} placeholder="Buscar por nombre o ID"
            aria-label={`Buscar ${title.toLowerCase()}`}
            onChange={(event) => onQuery(event.target.value)} />
        </label>
        <label className="cloud-field advanced-filter"><span>Categoría</span>
          <select value={category} disabled={disabled} onChange={(event) => onCategory(event.target.value)}>
            <option value="">Todas</option>
            {categories.map((value) => <option key={value} value={value}>{categoryLabel(value)}</option>)}
          </select>
        </label>
      </div>
      <div className="advanced-bulk">
        <button type="button" className="button quiet" disabled={disabled || editableRows.length === 0} onClick={toggleAll}>
          {allSelected ? 'Quitar selección' : `Seleccionar ${numberFormat.format(editableRows.length)} editables`}
        </button>
        <label className="advanced-bulk-value"><span>Cantidad para seleccionados</span>
          <input inputMode="numeric" value={bulk} disabled={disabled} placeholder="Ej. 100"
            onChange={(event) => setBulk(event.target.value)} />
        </label>
        <button type="button" className="button quiet" disabled={disabled || selected.size === 0 || bulkValue == null}
          onClick={applyBulk}>Aplicar a {numberFormat.format(selected.size)}</button>
      </div>
      {rows.length === 0 ? <p className="cloud-note">No hay elementos en esta colección.</p>
        : filtered.length === 0 ? <p className="cloud-note">Ningún elemento coincide con el filtro.</p>
        : <div className="advanced-list">
          {visible.map((row) => {
            const value = edits[row.id] ?? ''
            const parsed = value ? parseQuantity(value) : null
            const pending = parsed != null && parsed !== row.count
            return <div key={row.id} className={`advanced-item${row.editable ? '' : ' read-only'}`}>
              <label className="advanced-check">
                <input type="checkbox" checked={selected.has(row.id)} disabled={disabled || !row.editable}
                  aria-label={`Seleccionar ${itemLabel(row)}`} onChange={() => toggle(row.id)} />
              </label>
              <div className="advanced-item-name">
                <strong>{itemLabel(row)}</strong>
                <code>{row.id}</code>
                <small>
                  {categoryLabel(row.subcategory)}
                  {!row.known && ' · Desconocido, se conserva'}
                  {row.reason && ` · ${row.reason}`}
                </small>
              </div>
              <div className="advanced-item-current">
                <span>{row.owned ? 'Actual' : 'No poseído'}</span>
                <strong>{row.owned ? (row.count == null ? 'Tipo no válido' : numberFormat.format(row.count)) : '—'}</strong>
              </div>
              <label className="advanced-item-input"><span>Nuevo</span>
                <input inputMode="numeric" value={value} disabled={disabled || !row.editable}
                  placeholder={row.owned && row.count != null ? String(row.count) : 'Cantidad'}
                  aria-label={`Nueva cantidad para ${itemLabel(row)}`}
                  aria-invalid={value !== '' && parsed == null}
                  onChange={(event) => onEdit(row.id, event.target.value)} />
              </label>
              {pending && <span className="advanced-pending">{numberFormat.format(parsed)}</span>}
            </div>
          })}
        </div>}
      {filtered.length > visible.length && <button type="button" className="button quiet advanced-more"
        onClick={() => setShowAll(true)}>Mostrar los {numberFormat.format(filtered.length)} resultados</button>}
    </div>
  </details>
}

function BattlePassEditor({
  advanced, disabled, level, onLevel, exp, onExp, buy, onBuy, season, onSeason,
}: {
  advanced: LabAdvanced
  disabled: boolean
  level: string
  onLevel: (value: string) => void
  exp: string
  onExp: (value: string) => void
  buy: boolean
  onBuy: (value: boolean) => void
  season: number | null
  onSeason: (value: number) => void
}) {
  const battlePass = advanced.battle_pass
  const record = battlePass.records.find((row) => row.season_id === season) ?? null
  const levelValue = parseQuantity(level)
  const expValue = parseQuantity(exp)
  const claimed = record ? Math.max(record.free_claimed_level ?? 0, record.paid_claimed_level ?? 0) : 0
  const levelInvalid = levelValue == null || levelValue < claimed
  const expInvalid = expValue == null
  const maxLevel = record?.max_level ?? null
  return <details className="advanced-panel">
    <summary>
      <span><strong>Pase de batalla</strong><small>Progreso local del pase seleccionado</small></span>
      <span className="advanced-count">{battlePass.records.length} temporada(s)</span>
      <ChevronDown size={17} aria-hidden="true" />
    </summary>
    <div className="advanced-panel-body">
      {battlePass.records.length === 0 ? <p className="cloud-note">
        Este guardado no contiene temporadas de pase. No se crean temporadas nuevas.
      </p> : <>
        <label className="cloud-field"><span>Temporada</span>
          <select value={season ?? ''} disabled={disabled}
            onChange={(event) => onSeason(Number(event.target.value))}>
            {battlePass.records.filter((row) => row.season_id != null).map((row) => (
              <option key={`${row.index}-${row.season_id}`} value={row.season_id ?? ''}>
                seasonID {row.season_id}{row.season_id === battlePass.selected_season_id ? ' · más reciente' : ''}
              </option>
            ))}
          </select>
          <small>Se elige por defecto el seasonID más alto. No se modifican temporadas históricas.</small>
        </label>
        {battlePass.active_season_id != null && battlePass.active_matches_selected === false && <Notice tone="warning">
          La temporada activa detectada es {battlePass.active_season_id}, distinta de la seleccionada.
          Revisa antes de preparar el cambio.
        </Notice>}
        {record && record.season_id !== battlePass.selected_season_id && <Notice tone="warning">
          Estás editando una temporada anterior a la más reciente detectada. Las demás temporadas
          se conservarán intactas.
        </Notice>}
        {!record ? <p className="cloud-note">No hay un pase editable para la temporada seleccionada.</p> : <>
          <div className="advanced-current-grid">
            <div><span>Nivel actual</span><strong>{record.cur_level ?? '—'}</strong></div>
            <div><span>Experiencia</span><strong>{record.cur_exp ?? '—'}</strong></div>
            <div><span>Premium local</span><strong>{record.has_buy ? 'Sí' : 'No'}</strong></div>
            <div><span>Gratis reclamado</span><strong>{record.free_claimed_level ?? '—'}</strong></div>
            <div><span>Premium reclamado</span><strong>{record.paid_claimed_level ?? '—'}</strong></div>
          </div>
          {!record.editable ? <p className="cloud-note">{record.error ?? 'Este registro no es editable.'}</p> : <>
            <div className="advanced-bp-fields">
              <label className="cloud-field"><span>Nivel (curLevel)</span>
                <input inputMode="numeric" value={level} disabled={disabled}
                  aria-invalid={levelInvalid} onChange={(event) => onLevel(event.target.value)} />
                <small>No puede ser menor que el progreso ya reclamado ({claimed}).</small>
              </label>
              <label className="cloud-field"><span>Experiencia (curExp)</span>
                <input inputMode="numeric" value={exp} disabled={disabled}
                  aria-invalid={expInvalid} onChange={(event) => onExp(event.target.value)} />
                <small>Entero no negativo; no se conoce una relación pública nivel-experiencia.</small>
              </label>
            </div>
            <div className="advanced-bp-actions">
              {maxLevel != null ? <button type="button" className="button quiet" disabled={disabled}
                onClick={() => onLevel(String(maxLevel))}>Nivel máximo respaldado: {maxLevel}</button>
                : <span className="cloud-note">No hay un campo de nivel máximo respaldado; no se inventa un tope.</span>}
              <label className="cloud-check"><input type="checkbox" checked={buy} disabled={disabled
                || (record.paid_claimed_level ?? 0) > 0}
                onChange={(event) => onBuy(event.target.checked)} />
                <span>Estado premium local (hasBuy)</span>
              </label>
            </div>
            {(record.paid_claimed_level ?? 0) > 0 && <p className="cloud-note">
              hasBuy no puede desactivarse mientras existan recompensas premium reclamadas.
            </p>}
            <p className="cloud-note">
              freeClaimedLevel y paidClaimedLevel nunca se modifican aquí. Cambiar hasBuy no compra
              el pase ni altera recibos, facturación o derechos del servidor.
            </p>
          </>}
        </>}
      </>}
    </div>
  </details>
}

function changeLabel(value: unknown) {
  if (value == null) return '—'
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function AdvancedEditorSection({
  saveSha, advanced, writeReady, disabled, accountLabel, formatProblem, onExpired, onPrepared,
}: {
  saveSha: string
  advanced: LabAdvanced
  writeReady: boolean
  disabled: boolean
  accountLabel: string
  formatProblem: (error: ApiProblem, fallback: string) => ApiProblem
  onExpired: () => void
  onPrepared: () => void
}) {
  const [materialQuery, setMaterialQuery] = useState('')
  const [materialCategory, setMaterialCategory] = useState('')
  const [materialSelected, setMaterialSelected] = useState<Set<string>>(new Set())
  const [materialEdits, setMaterialEdits] = useState<Record<string, string>>({})
  const [seedQuery, setSeedQuery] = useState('')
  const [seedCategory, setSeedCategory] = useState('')
  const [seedSelected, setSeedSelected] = useState<Set<string>>(new Set())
  const [seedEdits, setSeedEdits] = useState<Record<string, string>>({})
  const [coin, setCoin] = useState(advanced.season_coin.value == null ? '' : String(advanced.season_coin.value))
  const [activateReborn, setActivateReborn] = useState(false)
  const initialSeason = advanced.battle_pass.selected_season_id
  const initialRecord = advanced.battle_pass.records.find((row) => row.season_id === initialSeason)
  const [season, setSeason] = useState<number | null>(initialSeason)
  const [level, setLevel] = useState(initialRecord?.cur_level == null ? '' : String(initialRecord.cur_level))
  const [exp, setExp] = useState(initialRecord?.cur_exp == null ? '' : String(initialRecord.cur_exp))
  const [buy, setBuy] = useState(Boolean(initialRecord?.has_buy))
  const [candidate, setCandidate] = useState<LabAdvancedPrepared | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LabWriteResult | null>(null)
  const operation = useOperation()

  const materialCategories = [...new Set(advanced.materials.map((row) => row.subcategory).filter((value): value is string => Boolean(value)))].sort()
  const seedCategories = [...new Set(advanced.seeds.map((row) => row.subcategory).filter((value): value is string => Boolean(value)))].sort()
  const coinValue = parseQuantity(coin)
  const coinValid = advanced.season_coin.available && coinValue != null
  const coinChanged = coinValid && coinValue !== advanced.season_coin.value
  const rebornChanged = advanced.reborn_card.available && advanced.reborn_card.value === false && activateReborn
  const record = advanced.battle_pass.records.find((row) => row.season_id === season) ?? null
  const claimed = record ? Math.max(record.free_claimed_level ?? 0, record.paid_claimed_level ?? 0) : 0
  const levelValue = parseQuantity(level)
  const expValue = parseQuantity(exp)
  const levelChanged = Boolean(record && levelValue != null && levelValue !== record.cur_level)
  const expChanged = Boolean(record && expValue != null && expValue !== record.cur_exp)
  const buyChanged = Boolean(record && buy !== record.has_buy)
  const bpValid = levelValue != null && expValue != null && levelValue >= claimed
  const materialPlan = Object.entries(materialEdits).flatMap(([id, raw]) => {
    const row = advanced.materials.find((candidateRow) => candidateRow.id === id)
    const value = parseQuantity(raw)
    return row && value != null && value !== row.count ? [{ id, value }] : []
  })
  const seedPlan = Object.entries(seedEdits).flatMap(([id, raw]) => {
    const row = advanced.seeds.find((candidateRow) => candidateRow.id === id)
    const value = parseQuantity(raw)
    return row && value != null && value !== row.count ? [{ id, value }] : []
  })
  const materialInvalid = Object.values(materialEdits).some((raw) => raw.trim() !== '' && parseQuantity(raw) == null)
  const seedInvalid = Object.values(seedEdits).some((raw) => raw.trim() !== '' && parseQuantity(raw) == null)
  const plannedCount = materialPlan.length + seedPlan.length
    + (coinChanged ? 1 : 0) + (rebornChanged ? 1 : 0)
    + (record && (levelChanged || expChanged || buyChanged) ? 1 : 0)
  const canPrepare = plannedCount > 0 && (!record || bpValid) && (!coin || coinValid)
    && !materialInvalid && !seedInvalid && !disabled

  function selectSeason(value: number) {
    setSeason(value)
    const next = advanced.battle_pass.records.find((row) => row.season_id === value)
    setLevel(next?.cur_level == null ? '' : String(next.cur_level))
    setExp(next?.cur_exp == null ? '' : String(next.cur_exp))
    setBuy(Boolean(next?.has_buy))
  }

  function clearPreview() {
    setCandidate(null)
    setConfirm(false)
    setResult(null)
  }

  function buildPlan(): LabAdvancedPlan | null {
    if (!canPrepare) return null
    const plan: LabAdvancedPlan = { materials: materialPlan, seeds: seedPlan }
    if (coinChanged) plan.season_coin = coinValue
    if (rebornChanged) plan.reborn_card = true
    if (record && (levelChanged || expChanged || buyChanged)) {
      plan.battle_pass = { season_id: record.season_id as number }
      if (levelChanged && levelValue != null) plan.battle_pass.cur_level = levelValue
      if (expChanged && expValue != null) plan.battle_pass.cur_exp = expValue
      if (buyChanged) plan.battle_pass.has_buy = buy
    }
    return plan
  }

  function submit() {
    const plan = buildPlan()
    if (!plan) return
    void operation.run(async (signal) => {
      try {
        clearPreview()
        setCandidate(await nativeAuth.prepareAdvanced(plan, saveSha, signal))
        onPrepared()
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      }
    })
  }

  function upload() {
    if (!candidate) return
    void operation.run(async (signal) => {
      try {
        setConfirm(false)
        const uploaded = await nativeAuth.confirm(candidate.backup.id, candidate.candidate_sha256, signal)
        setResult(uploaded)
        onPrepared()
      } catch (error) {
        if (!signal.aborted && error instanceof ApiProblem && isExpired(error)) onExpired()
        throw error
      }
    })
  }

  return <section className="cloud-section panel advanced-section" aria-labelledby="advanced-title">
    <div className="cloud-section-head">
      <div>
        <span className="cloud-kicker">Confirmado E3 · pase E2</span>
        <h2 id="advanced-title">Materiales, recursos y pase</h2>
        <p className="cloud-state">Un lote atómico con respaldo y confirmación</p>
      </div>
      <div className="editor-current">
        <span>Cambios</span>
        <strong data-testid="advanced-change-count">{numberFormat.format(plannedCount)}</strong>
      </div>
    </div>
    <p className="cloud-note">
      Materiales, semillas, moneda de temporada y renacimiento están confirmados por el
      propietario en Android físico. El pase de batalla sigue experimental. No toca gemas,
      fichas de pesca, recompensas reclamadas, recibos ni compras.
    </p>
    {!writeReady && <Notice tone="warning">
      Puedes preparar el lote y su respaldo. La subida a la nube está deshabilitada.
    </Notice>}
    <div className="advanced-stack">
      <ItemCollection title="Materiales" description="Cantidades de itemData.materials"
        rows={advanced.materials} query={materialQuery} onQuery={setMaterialQuery}
        category={materialCategory} onCategory={setMaterialCategory} categories={materialCategories}
        selected={materialSelected} onSelected={setMaterialSelected}
        edits={materialEdits} onEdit={(id, value) => {
          setMaterialEdits((current) => ({ ...current, [id]: value }))
          clearPreview()
        }} disabled={disabled} />
      <ItemCollection title="Semillas" description="Cantidades de itemData.seeds"
        rows={advanced.seeds} query={seedQuery} onQuery={setSeedQuery}
        category={seedCategory} onCategory={setSeedCategory} categories={seedCategories}
        selected={seedSelected} onSelected={setSeedSelected}
        edits={seedEdits} onEdit={(id, value) => {
          setSeedEdits((current) => ({ ...current, [id]: value }))
          clearPreview()
        }} disabled={disabled} />
      <details className="advanced-panel">
        <summary>
          <span><strong>Monedas y recursos</strong><small>Moneda de temporada</small></span>
          <span className="advanced-count">{advanced.season_coin.value == null ? 'No disponible' : numberFormat.format(advanced.season_coin.value)}</span>
          <ChevronDown size={17} aria-hidden="true" />
        </summary>
        <div className="advanced-panel-body">
          {!advanced.season_coin.available ? <p className="cloud-note">
            La partida no contiene <code>seasonData.coin</code> como entero; no se crea el campo.
          </p> : <>
            <label className="cloud-field"><span>Monedas de temporada (seasonData.coin)</span>
              <input inputMode="numeric" value={coin} disabled={disabled}
                aria-invalid={!coinValid} onChange={(event) => {
                  setCoin(event.target.value)
                  clearPreview()
                }} />
              <small>Entero entre 0 y {numberFormat.format(MAX_VALUE)}. No es gema, ficha de pesca ni experiencia del pase.</small>
            </label>
            <div className="advanced-quick">
              {[1_000, 10_000, 100_000, 1_000_000].map((value) => <button key={value} type="button"
                className="button quiet" disabled={disabled} onClick={() => {
                  setCoin(String(value))
                  clearPreview()
                }}>{numberFormat.format(value)}</button>)}
            </div>
          </>}
        </div>
      </details>
      <details className="advanced-panel">
        <summary>
          <span><strong>Beneficios permanentes</strong><small>Tarjeta de renacimiento</small></span>
          <span className="advanced-count">{advanced.reborn_card.value == null ? 'No disponible' : advanced.reborn_card.value ? 'Activa' : 'Inactiva'}</span>
          <ChevronDown size={17} aria-hidden="true" />
        </summary>
        <div className="advanced-panel-body">
          {!advanced.reborn_card.available ? <p className="cloud-note">
            No existe <code>gameData.rebornCard</code> booleano en esta partida; no se inventa el campo.
          </p> : advanced.reborn_card.value ? <p className="cloud-note">
            La partida ya declara la tarjeta como activa. No se modifica.
          </p> : <label className="cloud-check"><input type="checkbox" checked={activateReborn}
            disabled={disabled} onChange={(event) => {
              setActivateReborn(event.target.checked)
              clearPreview()
            }} />
            <span>Activar <code>gameData.rebornCard</code> (tarjeta de renacimiento permanente)</span>
          </label>}
          <p className="cloud-note"><strong>Límite:</strong> {advanced.reborn_card.limitation}</p>
          <p className="cloud-note">
            Referencia local: <code>{advanced.reborn_card.local_reference}</code>; en la nube:
            <code>{advanced.reborn_card.remote_representation}</code>; proyección: {advanced.reborn_card.projection}.
          </p>
        </div>
      </details>
      <BattlePassEditor advanced={advanced} disabled={disabled}
        level={level} onLevel={(value) => { setLevel(value); clearPreview() }}
        exp={exp} onExp={(value) => { setExp(value); clearPreview() }}
        buy={buy} onBuy={(value) => { setBuy(value); clearPreview() }}
        season={season} onSeason={selectSeason} />
    </div>
    <div className="advanced-actions">
      <button type="button" className="button primary" disabled={!canPrepare}
        onClick={submit}>
        <WandSparkles size={17} aria-hidden="true" />
        Preparar lote de cambios
      </button>
      {!canPrepare && plannedCount > 0 && !bpValid && <small className="cloud-note">
        Revisa el nivel del pase: no puede ser menor que las recompensas ya reclamadas.
      </small>}
      {(materialInvalid || seedInvalid) && <small className="cloud-note">
        Hay cantidades con formato inválido. Usa enteros entre 0 y 2.147.483.647 o deja el campo vacío.
      </small>}
    </div>
    {operation.pending && <Loading>
      {result ? 'Subiendo y verificando…' : candidate ? 'Subiendo y verificando…' : 'Preparando lote y respaldo…'}
    </Loading>}
    {operation.problem && <Problem problem={formatProblem(operation.problem,
      candidate ? 'No se pudo confirmar la subida. Verifica el estado desde Partida.'
        : 'No se pudo preparar el lote avanzado. Revisa los datos y vuelve a intentarlo.')} />}
    {candidate && <div className="cloud-preview advanced-preview">
      <h3>Revisar lote preparado</h3>
      <p className="cloud-note">
        {candidate.changes.length} campo(s) cambiarán. Respaldo <code>{candidate.backup.id}</code>.
      </p>
      <div className="advanced-diff">
        {candidate.changes.slice(0, 40).map((change) => <div key={change.path}>
          <code>{change.path}</code>
          <span>{changeLabel(change.before)} → <strong>{changeLabel(change.after)}</strong></span>
        </div>)}
        {candidate.changes.length > 40 && <p className="cloud-note">
          Se muestran 40 de {candidate.changes.length} cambios; el respaldo conserva el lote completo.
        </p>}
      </div>
      {!candidate.changed ? <p className="cloud-note">No hay diferencias que subir.</p>
        : writeReady && !result && <>
          <label className="cloud-check"><input type="checkbox" checked={confirm} disabled={disabled}
            onChange={(event) => setConfirm(event.target.checked)} />
            <span>Confirmo que quiero sobrescribir la partida en la nube de {accountLabel} con este lote.</span>
          </label>
          <button type="button" className="button primary" disabled={disabled || !confirm}
            onClick={upload}>Subir lote y verificar</button>
        </>}
    </div>}
    {result && <div role="status" className={`cloud-feedback ${result.persisted ? 'verified' : 'uncertain'}`}>
      {result.persisted
        ? candidate?.experimental
          ? 'Lote subido y verificado en la nube. El pase de batalla sigue pendiente de prueba en Android físico.'
          : 'Lote subido y verificado en la nube. Las funciones confirmadas ya fueron validadas por el propietario en Android físico.'
        : 'No se pudo confirmar la subida del lote. Verifica el estado desde Partida.'}
    </div>}
    {result?.persisted && <p className="cloud-note">
      Verificar la subida demuestra que los campos llegaron a la nube. Materiales, semillas,
      moneda de temporada y renacimiento cuentan además con validación del propietario en Android
      físico. El pase de batalla sigue pendiente de esa prueba.
    </p>}
  </section>
}

function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
}