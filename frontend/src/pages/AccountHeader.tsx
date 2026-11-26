import { Cloud, Eye, EyeOff, FilePenLine, House, Menu } from 'lucide-react'
import {
  useEffect, useId, useRef, useState,
  type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent,
} from 'react'
import { Link } from 'react-router'
import { Brand } from '../Brand'
import { useEmailPrivacy } from '../accountPrivacy'
import { ThemeSelect } from '../ThemeSelect'

type Section = 'partida' | 'editor'

type DragState = {
  pointerId: number
  startX: number
  startY: number
  baseX: number
  width: number
  x: number
  axis: 'pending' | 'horizontal' | 'ignored'
  samples: Array<{ x: number; t: number }>
}

const CLOSE_DURATION = 220
const DRAG_AXIS_THRESHOLD = 6
const CLOSE_DISTANCE_RATIO = 0.33
const CLOSE_VELOCITY = -0.5

function reducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function AccountHeader({
  accountLabel, accountTitle, platform, distribution, gameVersion, basePath, section,
}: {
  accountLabel: string
  accountTitle?: string
  platform: string
  distribution: string
  gameVersion?: string
  basePath: string
  section: Section
}) {
  const [open, setOpen] = useState(false)
  const [entered, setEntered] = useState(false)
  const [closing, setClosing] = useState(false)
  const [hideEmail, setHideEmail] = useEmailPrivacy()
  const titleId = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const layer = useRef<HTMLDivElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const backdrop = useRef<HTMLDivElement>(null)
  const restoreFocus = useRef<HTMLElement | null>(null)
  const closeTimer = useRef<number | null>(null)
  const closingRef = useRef(false)
  const drag = useRef<DragState | null>(null)
  const suppressClickUntil = useRef(0)

  function finishClose(restore: boolean) {
    closingRef.current = false
    drag.current = null
    setEntered(false)
    setOpen(false)
    setClosing(false)
    if (restore) {
      const target = restoreFocus.current ?? trigger.current
      window.setTimeout(() => target?.focus({ preventScroll: true }), 0)
    }
  }

  function close(restore = true) {
    if (closingRef.current) return
    closingRef.current = true
    drag.current = null
    setClosing(true)
    layer.current?.classList.remove('dragging')
    if (panel.current) panel.current.style.transform = 'translate3d(-100%, 0, 0)'
    if (backdrop.current) backdrop.current.style.opacity = '0'
    if (reducedMotion()) {
      finishClose(restore)
      return
    }
    closeTimer.current = window.setTimeout(() => {
      closeTimer.current = null
      finishClose(restore)
    }, CLOSE_DURATION)
  }

  function settleOpen() {
    layer.current?.classList.remove('dragging')
    if (panel.current) panel.current.style.transform = 'translate3d(0, 0, 0)'
    if (backdrop.current) backdrop.current.style.opacity = '1'
  }

  function onPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (closingRef.current || !event.isPrimary) return
    if (event.pointerType === 'mouse' && event.button !== 0) return
    const layerElement = layer.current
    if (!layerElement) return
    const drawerRect = event.currentTarget.getBoundingClientRect()
    const layerRect = layerElement.getBoundingClientRect()
    drag.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      baseX: drawerRect.left - layerRect.left,
      width: drawerRect.width,
      x: drawerRect.left - layerRect.left,
      axis: 'pending',
      samples: [{ x: event.clientX, t: performance.now() }],
    }
  }

  function onPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const state = drag.current
    if (!state || state.pointerId !== event.pointerId) return
    const dx = event.clientX - state.startX
    const dy = event.clientY - state.startY

    if (state.axis === 'pending') {
      if (Math.abs(dx) < DRAG_AXIS_THRESHOLD && Math.abs(dy) < DRAG_AXIS_THRESHOLD) return
      if (Math.abs(dy) >= Math.abs(dx) || dx > 0) {
        state.axis = 'ignored'
        return
      }
      state.axis = 'horizontal'
      const drawerRect = event.currentTarget.getBoundingClientRect()
      const layerElement = layer.current
      if (layerElement) state.baseX = drawerRect.left - layerElement.getBoundingClientRect().left
      state.width = drawerRect.width
      layer.current?.classList.add('dragging')
      try {
        event.currentTarget.setPointerCapture(event.pointerId)
      } catch {
        // La captura es una mejora; el gesto sigue funcionando sin ella.
      }
    }
    if (state.axis !== 'horizontal') return
    if (event.cancelable) event.preventDefault()

    state.x = Math.min(0, Math.max(-state.width, state.baseX + dx))
    const progress = Math.max(0, Math.min(1, 1 + state.x / state.width))
    if (panel.current) panel.current.style.transform = `translate3d(${state.x}px, 0, 0)`
    if (backdrop.current) backdrop.current.style.opacity = String(progress)

    const now = performance.now()
    state.samples.push({ x: event.clientX, t: now })
    while (state.samples.length > 2 && now - state.samples[0].t > 100) state.samples.shift()
  }

  function endDrag(event: ReactPointerEvent<HTMLDivElement>, cancelled: boolean) {
    const state = drag.current
    if (!state || state.pointerId !== event.pointerId) return
    drag.current = null
    if (state.axis !== 'horizontal') return

    suppressClickUntil.current = performance.now() + 350
    try {
      event.currentTarget.releasePointerCapture(event.pointerId)
    } catch {
      // El puntero pudo haberse liberado antes de cancelar.
    }

    if (cancelled) {
      settleOpen()
      return
    }

    const last = state.samples[state.samples.length - 1]
    const first = state.samples[0]
    const elapsed = last.t - first.t
    const stillMoving = performance.now() - last.t < 100
    const velocity = stillMoving && elapsed > 0 ? (last.x - first.x) / elapsed : 0
    const farEnough = state.x <= -state.width * CLOSE_DISTANCE_RATIO
    const fastEnough = velocity <= CLOSE_VELOCITY && state.x <= -8

    if (farEnough || fastEnough) close(true)
    else settleOpen()
  }

  function onPointerCancel(event: ReactPointerEvent<HTMLDivElement>) {
    endDrag(event, true)
  }

  function onLostPointerCapture(event: ReactPointerEvent<HTMLDivElement>) {
    if (drag.current?.axis === 'horizontal' && drag.current.pointerId === event.pointerId) {
      drag.current = null
      settleOpen()
    }
  }

  function onClickCapture(event: ReactMouseEvent<HTMLDivElement>) {
    if (performance.now() < suppressClickUntil.current) {
      suppressClickUntil.current = 0
      event.preventDefault()
      event.stopPropagation()
    }
  }

  useEffect(() => {
    if (!open) return
    const frame = window.requestAnimationFrame(() => setEntered(true))
    return () => window.cancelAnimationFrame(frame)
  }, [open])

  useEffect(() => () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current)
  }, [])

  useEffect(() => {
    if (!open) return
    restoreFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : trigger.current
    const body = document.body
    const previousOverflow = body.style.overflow
    body.style.overflow = 'hidden'
    const firstFocusable = panel.current?.querySelector<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )
    const focusTarget = firstFocusable ?? panel.current
    focusTarget?.focus({ preventScroll: true })

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
  const version = gameVersion?.trim()
    ? `v${gameVersion.trim().replace(/^v/i, '')}`
    : ''
  const details = [platform, distribution, version].filter(Boolean).join(' · ')

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
    {open && <div ref={layer} className={`drawer-layer${entered ? ' entered' : ''}${closing ? ' closing' : ''}`}
      onClickCapture={onClickCapture}>
      <div ref={backdrop} className="drawer-backdrop" aria-hidden="true" onClick={() => close()} />
      <div id="account-drawer" ref={panel} className="account-drawer" role="dialog" aria-modal="true"
        aria-labelledby={titleId} tabIndex={-1}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={(event) => endDrag(event, false)}
        onPointerCancel={onPointerCancel} onLostPointerCapture={onLostPointerCapture}>
        <h2 id={titleId} className="account-drawer-title">
          SK-Under<span className="sr-only">, menú de cuenta</span>
        </h2>
        <div className="account-drawer-account">
          <span className="account-drawer-identity">
            <strong title={accountTitle}>{accountLabel}</strong>
            <span>{details}</span>
          </span>
          <button className="drawer-privacy" type="button" aria-pressed={hideEmail}
            aria-label={hideEmail ? 'Mostrar correo' : 'Ocultar correo'}
            title={hideEmail ? 'Mostrar correo' : 'Ocultar correo'}
            onClick={() => setHideEmail((value) => !value)}>
            {hideEmail ? <Eye size={19} aria-hidden="true" /> : <EyeOff size={19} aria-hidden="true" />}
          </button>
        </div>
        <nav className="account-drawer-nav" aria-label="Secciones de la cuenta">
          {items.map(({ section: itemSection, label, to, icon: Icon }) => <Link key={itemSection}
            to={to} className={`account-drawer-link${section === itemSection ? ' active' : ''}`}
            aria-current={section === itemSection ? 'page' : undefined}
            onClick={() => close(false)}>
            <Icon size={25} strokeWidth={1.9} aria-hidden="true" /><span>{label}</span>
          </Link>)}
          <Link to="/" className="account-drawer-link" onClick={() => close(false)}>
            <House size={25} strokeWidth={1.9} aria-hidden="true" /><span>Volver al inicio</span>
          </Link>
        </nav>
        <div className="drawer-theme">
          <ThemeSelect variant="drawer" />
        </div>
      </div>
    </div>}
  </>
}