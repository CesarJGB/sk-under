import { ScanLine } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { ThemeSelect } from './ThemeSelect'

export function Brand() {
  return <Link to="/" className="brand" aria-label="SK-Under, volver al dashboard">
    <span className="brand-icon"><ScanLine size={22} aria-hidden="true" /></span>
    SK-Under
  </Link>
}

export function SimpleTopbar({ children }: { children?: ReactNode }) {
  return <header className="topbar">
    <div className="shell topbar-inner topbar-simple">
      <Brand />
      <div className="topbar-actions">
        {children}
        <ThemeSelect />
      </div>
    </div>
  </header>
}
