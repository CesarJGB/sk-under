import { Check, Monitor, Moon, Sun, type LucideIcon } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { useTheme, type ThemePreference } from './theme'

type ThemeOption = {
  value: ThemePreference
  label: string
  icon: LucideIcon
}

const OPTIONS: ThemeOption[] = [
  { value: 'light', label: 'Claro', icon: Sun },
  { value: 'dark', label: 'Oscuro', icon: Moon },
  { value: 'system', label: 'Sistema', icon: Monitor },
]

export function ThemeSelect({ variant = 'topbar' }: { variant?: 'topbar' | 'drawer' }) {
  const { preference, setPreference } = useTheme()
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const selected = OPTIONS.find((option) => option.value === preference) ?? OPTIONS[2]
  const CurrentIcon = selected.icon
  const drawer = variant === 'drawer'

  function close(restoreFocus = true) {
    setOpen(false)
    if (restoreFocus) {
      window.requestAnimationFrame(() => trigger.current?.focus({ preventScroll: true }))
    }
  }

  useEffect(() => {
    if (!open) return
    const target = menu.current?.querySelector<HTMLElement>('[aria-checked="true"]')
    target?.focus({ preventScroll: true })

    function onPointerDown(event: PointerEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false)
    }

    function onDocumentKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      event.preventDefault()
      close()
    }

    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onDocumentKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onDocumentKeyDown)
    }
  }, [open])

  function onMenuKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const items = [...(menu.current?.querySelectorAll<HTMLElement>('[role="menuitemradio"]') ?? [])]
    if (!items.length) return
    const index = items.indexOf(document.activeElement as HTMLElement)
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      close()
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const delta = event.key === 'ArrowDown' ? 1 : -1
      items[(index + delta + items.length) % items.length]?.focus()
      return
    }
    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault()
      items[event.key === 'Home' ? 0 : items.length - 1]?.focus()
      return
    }
    if (event.key === 'Tab') setOpen(false)
  }

  return <div className={`theme-select theme-select-${variant}`} ref={root}>
    <button ref={trigger} className={drawer ? 'drawer-theme-trigger' : 'button quiet topbar-utility'}
      type="button" aria-label={`Apariencia: ${selected.label}`} aria-haspopup="menu"
      aria-expanded={open} aria-controls={open ? menuId : undefined}
      title={`Apariencia: ${selected.label}`}
      onClick={() => setOpen((value) => !value)}>
      <CurrentIcon size={18} aria-hidden="true" />
      {drawer && <span className="drawer-theme-label">Apariencia</span>}
      {drawer && <span className="drawer-theme-value">{selected.label}</span>}
    </button>
    {open && <div ref={menu} id={menuId} className={`theme-menu${drawer ? ' theme-menu-drawer' : ''}`}
      role="menu" aria-label="Seleccionar apariencia" onKeyDown={onMenuKeyDown}>
      {OPTIONS.map(({ value, label, icon: Icon }) => <button key={value} type="button"
        className="theme-option" role="menuitemradio" aria-checked={preference === value}
        onClick={() => { setPreference(value); close() }}>
        <Icon size={17} aria-hidden="true" />
        <span>{label}</span>
        {preference === value && <Check className="theme-check" size={16} aria-hidden="true" />}
      </button>)}
    </div>}
  </div>
}