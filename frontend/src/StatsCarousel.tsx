import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { NativeSaveSummary } from './api'
import { evidenceText, formatStat, readStat, statPages } from './partidaStats'

export function StatsCarousel({ save }: { save: NativeSaveSummary }) {
  const pages = statPages()
  const [page, setPage] = useState(0)
  const viewport = useRef<HTMLDivElement>(null)
  const frame = useRef<number | null>(null)

  function go(next: number, smooth = true) {
    const target = Math.max(0, Math.min(pages.length - 1, next))
    const element = viewport.current
    setPage(target)
    element?.scrollTo({
      left: target * element.clientWidth,
      behavior: smooth && !window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'auto',
    })
  }

  useEffect(() => {
    const element = viewport.current
    if (!element) return
    const observer = new ResizeObserver(() => {
      if (Math.round(element.scrollLeft / Math.max(element.clientWidth, 1)) !== page) {
        element.scrollTo({ left: page * element.clientWidth, behavior: 'auto' })
      }
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [page])

  useEffect(() => {
    setPage((current) => Math.min(current, pages.length - 1))
  }, [pages.length])

  function onScroll() {
    if (frame.current != null) return
    frame.current = requestAnimationFrame(() => {
      frame.current = null
      const element = viewport.current
      if (!element) return
      const next = Math.round(element.scrollLeft / Math.max(element.clientWidth, 1))
      setPage((current) => current === next ? current : Math.max(0, Math.min(pages.length - 1, next)))
    })
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      go(page - 1)
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      go(page + 1)
    } else if (event.key === 'Home') {
      event.preventDefault()
      go(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      go(pages.length - 1)
    }
  }

  return <section className="partida-stats" aria-label="Estadísticas de la partida">
    <div className="partida-carousel-shell">
      <button className="partida-carousel-arrow" type="button" aria-label="Página anterior"
        disabled={page === 0} onClick={() => go(page - 1)}>
        <ChevronLeft size={17} aria-hidden="true" />
      </button>
      <div className="partida-carousel-viewport" ref={viewport} tabIndex={0} role="group"
        aria-roledescription="carrusel" aria-label={`Estadísticas, página ${page + 1} de ${pages.length}`}
        onScroll={onScroll} onKeyDown={onKeyDown}>
        <div className="partida-stats-track">
          {pages.map((metrics, index) => <div className="partida-stat-page" key={index}
            role="group" aria-roledescription="página" aria-label={`Página ${index + 1} de ${pages.length}`}
            aria-hidden={index === page ? undefined : true}>
            {metrics.map((metric) => {
              const value = readStat(metric, save)
              const display = formatStat(value)
              const Icon = metric.icon
              return <div className="partida-stat" key={metric.id} data-metric={metric.id}
                data-testid={`stat-${metric.id}`} data-state={value.kind} data-category={metric.category}
                data-evidence={metric.evidence.level} title={`${metric.label}: ${display.title}. ${evidenceText(metric.evidence)}`}>
                <div className="partida-stat-label">
                  <Icon size={15} aria-hidden="true" />
                  <span>{metric.label}</span>
                  {metric.evidence.experimental && <span className="partida-stat-flag" role="img" aria-label="Experimental" title="Experimental · E2" />}
                </div>
                <strong className={`partida-stat-value ${display.numeric ? 'numeric' : ''}`} data-tone={display.tone}>
                  {display.primary}
                </strong>
                {display.detail && <small className="partida-stat-detail">{display.detail}</small>}
              </div>
            })}
          </div>)}
        </div>
      </div>
      <button className="partida-carousel-arrow" type="button" aria-label="Página siguiente"
        disabled={page === pages.length - 1} onClick={() => go(page + 1)}>
        <ChevronRight size={17} aria-hidden="true" />
      </button>
    </div>
    <div className="partida-carousel-footer">
      <div className="partida-carousel-dots" aria-label="Paginación de estadísticas">
        {pages.map((_, index) => <button key={index} type="button" className="partida-carousel-dot"
          aria-label={`Ir a la página ${index + 1}`} aria-current={index === page ? 'page' : undefined}
          onClick={() => go(index)} />)}
      </div>
      <p className="partida-carousel-position" role="status">
        Página {page + 1} de {pages.length}
      </p>
    </div>
  </section>
}