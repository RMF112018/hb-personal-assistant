import {
  Activity,
  AlertTriangle,
  ChevronLeft,
  ClipboardCheck,
  GitCompare,
  Link2,
  Layers,
  Scale,
  Upload,
  Workflow,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import '../forecast/forecast-ui.css'

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/schedules/imports', label: 'Imports', icon: Upload },
  { to: '/schedules/versions', label: 'Versions', icon: Layers },
  { to: '/schedules/activities', label: 'Activities', icon: Activity },
  { to: '/schedules/quality', label: 'Schedule Health', icon: AlertTriangle },
  { to: '/schedules/cpm', label: 'Computed CPM', icon: Workflow },
  { to: '/schedules/identity-review', label: 'Identity Review', icon: ClipboardCheck },
  { to: '/schedules/version-diff', label: 'Version Diff', icon: GitCompare },
  { to: '/schedules/cost-mapping', label: 'Cost Mapping', icon: Link2 },
  { to: '/schedules/cost-weighting', label: 'Cost Weighting', icon: Scale },
]

export {
  ForecastShell as ScheduleShell,
  ForecastTable as ScheduleTable,
  ForecastTh as ScheduleTh,
  ForecastTd as ScheduleTd,
  ForecastPanel as SchedulePanel,
} from '../forecast/ForecastPrimitives'

export function ScheduleBackLink({
  to = '/schedules/versions',
  label = 'Back to schedule versions',
}: {
  to?: string
  label?: string
}) {
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
  if (to === '/schedules/quality' && pathname.startsWith('/schedules/health')) {
    return true
  }
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function ScheduleSubnav() {
  const { pathname } = useLocation()
  return (
    <nav aria-label="Schedule Intelligence sections" className="forecast-subnav">
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

export function SchedulePageHeader({
  title,
  subtitle,
  actions,
  eyebrow = 'Schedule Intelligence',
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
          {subtitle && (
            <p className="text-sm text-[var(--hb-muted)] mt-2 max-w-2xl leading-relaxed">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  )
}

export function ScheduleActionButton({
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

export function ScheduleActionLink({
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
