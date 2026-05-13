import { Link, useLocation } from 'react-router-dom'
import { Shield } from 'lucide-react'
import LiveDot from './LiveDot.jsx'

export default function TopNav() {
  const { pathname } = useLocation()
  const links = [
    { to: '/login', label: 'Enter' },
    { to: '/report', label: 'Report' },
  ]
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface-0/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <Link to="/" className="group flex items-center gap-2.5">
          <Shield
            size={16}
            strokeWidth={1.75}
            className="text-text-secondary transition-colors group-hover:text-text-primary"
          />
          <span className="text-[13px] font-medium tracking-tight text-text-primary">
            ProctorVision
          </span>
          <span className="hidden font-mono text-[10px] uppercase tracking-eyebrow text-text-muted sm:inline">
            v0.1
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          {links.map((l) => {
            const active = pathname === l.to
            return (
              <Link
                key={l.to}
                to={l.to}
                className={`rounded px-3 py-1.5 text-[13px] transition-colors ${
                  active
                    ? 'text-text-primary'
                    : 'text-text-muted hover:text-text-secondary'
                }`}
              >
                {l.label}
              </Link>
            )
          })}
          <div className="mx-3 h-4 w-px bg-border" />
          <LiveDot variant="online" label="online" />
        </nav>
      </div>
    </header>
  )
}
