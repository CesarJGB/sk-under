import { ChevronDown } from 'lucide-react'
import { useId, type ReactNode } from 'react'

export function AccordionGroup({ title, meta, summary, expanded, onToggle, testId, children }: {
  title: string
  meta?: string
  summary?: string
  expanded: boolean
  onToggle: () => void
  testId?: string
  children: ReactNode
}) {
  const panelId = useId()
  return <section className={`lock-group accordion-group${expanded ? ' is-expanded' : ''}`} data-testid={testId}>
    <button type="button" className="accordion-head" aria-expanded={expanded} aria-controls={panelId} onClick={onToggle}>
      <span className="accordion-copy">
        <strong>{title}</strong>
        {(meta || summary) && <small>{meta}{meta && summary ? ' · ' : ''}{summary}</small>}
      </span>
      <ChevronDown className="accordion-chevron" size={18} aria-hidden="true" />
    </button>
    {expanded && <div className="accordion-panel" id={panelId}>{children}</div>}
  </section>
}