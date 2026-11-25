import { Cloud, FilePenLine, House, Menu, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Brand } from '../Brand'

type Section = 'partida' | 'editor'

export function AccountHeader({
  accountLabel, platform, distribution, basePath, section,
}: {
  accountLabel: string
  platform: string
  distribution: string
  basePath: string
  section: Section
}) {
  const [open, setOpen] = useState(false)
  const titleId = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const restoreFocus = useRef<HTMLElement | null>(null)

  function close(restore = true) {
    setOpen(false)
    if (restore) {
      const target = restoreFocus.current ?? trigger.current
      window.setTimeout(() => target?.focus({ preventScroll: true }), 0)
    }
  }

  useEffect(() => {
    if (!open) return
    restoreFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : trigger.current
    const body = document.body
    const previousOverflow = body.style.overflow
    body.style.overflow = 'hidden'
    closeButton.current?.focus({ preventScroll: true })

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
        return
      }
      if (event.key !== 'Tab' || !panel.current) return
      const focusable = [...panel.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )].filter((element) => element.offsetParent !== null)
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      body.style.overflow = previousOverflow
    }
  }, [open])

  const items = [
    { section: 'partida' as const, label: 'Partida', to: `${basePath}/partida`, icon: Cloud },
    { section: 'editor' as const, label: 'Editor', to: `${basePath}/editor`, icon: FilePenLine },
  ]

  return <>
    <header className="topbar account-topbar">
      <div className="shell topbar-inner account-topbar-inner">
        <button ref={trigger} className="button quiet account-menu-button" type="button"
          aria-label="Abrir menú de cuenta" aria-expanded={open} aria-controls="account-drawer"
          onClick={() => setOpen(true)}>
          <Menu size={21} aria-hidden="true" />
        </button>
        <Brand />
        <span className="account-topbar-label" title={undefined}>{accountLabel}</span>
      </div>
    </header>
    {open && <div className="drawer-layer" onMouseDown={(event) => {
      if (event.target === event.currentTarget) close()
    }}>
      <div id="account-drawer" ref={panel} className="account-drawer" role="dialog" aria-modal="true"
        aria-labelledby={titleId}>
        <div className="account-drawer-head">
          <p id={titleId}>Cuenta actual</p>
          <button ref={closeButton} className="button quiet drawer-close" type="button"
            aria-label="Cerrar menú" onClick={() => close()}>
            <X size={19} aria-hidden="true" />
          </button>
        </div>
        <div className="account-drawer-account">
          <strong>{accountLabel}</strong>
          <span>{[platform, distribution].filter(Boolean).join(' · ')}</span>
        </div>
        <nav className="account-drawer-nav" aria-label="Secciones de la cuenta">
          {items.map(({ section: itemSection, label, to, icon: Icon }) => <Link key={itemSection}
            to={to} className={`account-drawer-link${section === itemSection ? ' active' : ''}`}
            aria-current={section === itemSection ? 'page' : undefined}
            onClick={() => close(false)}>
            <Icon size={18} aria-hidden="true" />{label}
          </Link>)}
          <Link to="/" className="account-drawer-link" onClick={() => close(false)}>
            <House size={18} aria-hidden="true" />Volver al inicio
          </Link>
        </nav>
      </div>
    </div>}
  </>
}