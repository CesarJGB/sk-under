import { useEffect, useRef } from 'react'
import { Link } from 'react-router'

const amountFormat = new Intl.NumberFormat('es-MX')

export function QuickUnlockCard({
  title, path, unlocked, total, pending, selected, busy, onToggleAll,
}: {
  title: string
  path: string
  unlocked: number
  total: number
  pending: number
  selected: number
  busy: boolean
  onToggleAll: () => void
}) {
  const allSelected = pending > 0 && selected === pending
  const someSelected = selected > 0 && !allSelected
  const checkbox = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (checkbox.current) checkbox.current.indeterminate = someSelected
  }, [someSelected])

  return <article className="quick-unlock-card" data-testid={`quick-${title.toLowerCase()}`}>
    <div className="quick-unlock-head">
      <div>
        <h3>{title}</h3>
        <p>{amountFormat.format(unlocked)} de {amountFormat.format(total)} desbloqueados</p>
      </div>
      <span className="report-state available">{amountFormat.format(pending)} pendientes</span>
    </div>
    <label className="quick-unlock-select">
      <input ref={checkbox} type="checkbox" checked={allSelected} disabled={busy || pending === 0}
        aria-label={`Seleccionar todos: ${title}`} onChange={onToggleAll} />
      <span>{pending === 0
        ? 'Nada pendiente'
        : allSelected ? 'Todo seleccionado' : `${amountFormat.format(selected)} seleccionados`}</span>
    </label>
    <Link className="button quiet" to={path}>Revisar {title.toLowerCase()}</Link>
  </article>
}