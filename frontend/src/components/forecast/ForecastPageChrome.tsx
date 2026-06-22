import {
  ChevronLeft,
  Database,
  LayoutDashboard,
  Play,
  Settings2,
  Upload,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import './forecast-ui.css'

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/forecasting', label: 'Overview', icon: LayoutDashboard },
  { to: '/forecasting/runs', label: 'Generate', icon: Play },
  { to: '/forecasting/external', label: 'Evaluate', icon: Upload },
  { to: '/forecasting/config', label: 'Configuration', icon: Settings2 },
  { to: '/forecasting/runtime', label: 'Storage', icon: Database },
]

export { ForecastShell, ForecastHero, ForecastPanel, ForecastTable, ForecastTh, ForecastTd, ForecastChecklistItem, ForecastWizardRail, ForecastDomainTile, ForecastAdvisoryStrip, ForecastProgressRow } from './ForecastPrimitives'
export { ForecastSummaryCard, ForecastSummaryGrid } from './ForecastSummary'

export function ForecastBackLink({ to = '/forecasting', label = 'Back to forecast overview' }: { to?: string; label?: string }) {
  return (
    <div className="mb-1">
      <Link to={to} className="forecast-btn-ghost inline-flex">
        <ChevronLeft size={14} aria-hidden />
        {label}
      </Link>
    </div>
  )
}

function isNavActive(pathname: string, to: string): boolean {
  if (to === '/forecasting') {
    if (pathname === '/forecasting') return true
    if (/^\/forecasting\/[^/]+$/.test(pathname)) return true
    return false
  }
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function ForecastSubnav() {
  const { pathname } = useLocation()
  return (
    <nav aria-label="Forecasting sections" className="forecast-subnav">
      {NAV.map((item) => {
        const active = isNavActive(pathname, item.to)
        const Icon = item.icon
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`forecast-subnav-link ${active ? 'is-active' : ''}`}
          >
            <Icon size={14} strokeWidth={2} aria-hidden />
            {item.label}
          </Link>
        )
      })}
    </nav>
  )
}

export function ForecastPageHeader({
  title,
  subtitle,
  actions,
  eyebrow = 'Construction forecasting',
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
  eyebrow?: string
}) {
  return (
    <div className="forecast-hero mb-0">
      <div className="relative flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between pl-2">
        <div className="min-w-0">
          <div className="forecast-eyebrow mb-1">{eyebrow}</div>
          <h1 className="forecast-title">{title}</h1>
          {subtitle && <p className="text-sm text-[var(--hb-muted)] mt-2 max-w-2xl leading-relaxed">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  )
}

/** Primary CTA button style for forecasting actions. */
export function ForecastActionButton({
  children,
  onClick,
  disabled,
  variant = 'primary',
}: {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary' | 'ghost'
}) {
  const cls =
    variant === 'primary'
      ? 'forecast-btn-primary'
      : variant === 'ghost'
        ? 'forecast-btn-ghost'
        : 'forecast-btn-secondary'
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={cls}>
      {children}
    </button>
  )
}

/** Link styled as a forecast primary/secondary action. */
export function ForecastActionLink({
  to,
  children,
  variant = 'secondary',
}: {
  to: string
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost'
}) {
  const cls =
    variant === 'primary'
      ? 'forecast-btn-primary'
      : variant === 'ghost'
        ? 'forecast-btn-ghost'
        : 'forecast-btn-secondary'
  return (
    <Link to={to} className={cls}>
      {children}
    </Link>
  )
}

/** Quick-link chips for secondary navigation rows. */
export function ForecastQuickLinks({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-2 mt-4">{children}</div>
}

export function ForecastQuickLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="forecast-btn-ghost">
      {children}
    </Link>
  )
}

