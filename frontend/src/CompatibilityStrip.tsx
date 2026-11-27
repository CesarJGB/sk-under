import { CircleAlert, CircleCheck } from 'lucide-react'
import type { CompatibilitySummary } from './api'

function text(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.length ? value.join(', ') : '—'
  if (typeof value === 'object') return '—'
  return String(value)
}

export function CompatibilityStrip({ compatibility, compact = false }: {
  compatibility: CompatibilitySummary
  compact?: boolean
}) {
  const profile = (compatibility.profile ?? {}) as Record<string, unknown>
  const detected = (compatibility.detected ?? {}) as Record<string, unknown>
  const store = (compatibility.store ?? {}) as Record<string, unknown>
  const catalogs = compatibility.catalog_versions ?? {}
  const warnings = compatibility.warnings ?? []
  const compatible = compatibility.state === 'compatible'
  const experimental = compatibility.state === 'experimental'
  return <section className={`compatibility-strip ${compatibility.state}${compact ? ' compact' : ''}`} aria-live="polite">
    <div className="compatibility-head">
      <span className="compatibility-badge">
        {compatible ? <CircleCheck size={15} aria-hidden="true" /> : <CircleAlert size={15} aria-hidden="true" />}
        {compatibility.label}
      </span>
      <span className="compatibility-account">{profile.platform === 'ios' ? 'iOS' : profile.platform === 'android' ? 'Android' : ''}
        {profile.commercial_version ? ` ${text(profile.commercial_version)}` : ''}</span>
    </div>
    <p>{compatibility.reason}</p>
    {warnings.length > 0 && <p className="compatibility-warning">{warnings.join(' · ')}</p>}
    <details>
      <summary>Detalles de compatibilidad</summary>
      <dl>
        <dt>Versión comercial</dt><dd>{text(profile.commercial_version)}</dd>
        <dt>Protocolo app / juego</dt><dd>{text(profile.protocol_app_version)} / {text(profile.protocol_game_version)}</dd>
        <dt>Esquema del agregado</dt><dd>{text(profile.schema_versions)}</dd>
        <dt>Detectado en la partida</dt><dd>gameVersion {text(detected.game_version)} · AppVersion {text(detected.app_version)} · serialzedVersion {text(detected.serialzed_version)}</dd>
        <dt>Plataforma</dt><dd>{text(detected.platform)}</dd>
        <dt>Tienda</dt><dd>{text(store.version)} ({text(store.status)})</dd>
        <dt>Evidencia</dt><dd>{text(profile.evidence)}</dd>
        <dt>Comprobado</dt><dd>{text(profile.checked_at)}</dd>
        <dt>Catálogos</dt><dd>{Object.keys(catalogs).length ? Object.entries(catalogs).map(([key, value]) => `${key} ${value}`).join(' · ') : '—'}</dd>
      </dl>
      {(compatibility.manual_validation ?? []).length > 0 && <p className="detail-note">
        Requiere validación manual: {(compatibility.manual_validation ?? []).join(' · ')}
      </p>}
      <p className="detail-note">
        {compatibility.write_supported
          ? experimental ? 'Escritura experimental: cada subida exige respaldo y verificación posterior.' : 'Lectura, preparación y escritura autorizadas.'
          : compatibility.prepare_ready ? 'Solo lectura y preparación local: la escritura no está autorizada.' : 'Solo lectura.'}
      </p>
    </details>
  </section>
}