import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import './forecast-ui.css'

export function ForecastShell({ children }: { children: ReactNode }) {
  return <div className="forecast-shell space-y-3">{children}</div>
}

export function ForecastHero({
  eyebrow,
  title,
  subtitle,
  actions,
  badge,
}: {
  eyebrow?: string
  title: string
  subtitle?: string
  actions?: ReactNode
  badge?: ReactNode
}) {
  return (
    <div className="forecast-hero">
      <div className="relative flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between pl-2">
        <div className="min-w-0">
          {eyebrow && <div className="forecast-eyebrow mb-1">{eyebrow}</div>}
          <h1 className="forecast-title">{title}</h1>
          {subtitle && <p className="text-sm text-[var(--hb-muted)] mt-2 max-w-2xl leading-relaxed">{subtitle}</p>}
          {badge && <div className="mt-2">{badge}</div>}
        </div>
        {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  )
}

export function ForecastPanel({
  icon: Icon,
  title,
  description,
  children,
  className = '',
  actions,
}: {
  icon?: LucideIcon
  title: string
  description?: string
  children: ReactNode
  className?: string
  actions?: ReactNode
}) {
  return (
    <section className={`forecast-panel ${className}`}>
      <div className="forecast-panel-header">
        {Icon && (
          <div className="forecast-panel-icon" aria-hidden>
            <Icon size={16} strokeWidth={2} />
          </div>
        )}
        <div className="min-w-0">
          <h2 className="forecast-section-label">{title}</h2>
          {description && <p className="text-sm text-[var(--hb-muted)] mt-1 leading-relaxed">{description}</p>}
        </div>
        {actions && <div className="ml-auto shrink-0">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

export function ForecastTable({ headers, children }: { headers: ReactNode; children: ReactNode }) {
  return (
    <div className="forecast-table-wrap">
      <table className="forecast-table">
        <thead>
          <tr>{headers}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export function ForecastTh({ children, className = '' }: { children?: ReactNode; className?: string }) {
  return <th className={className}>{children}</th>
}

export function ForecastTd({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <td className={className}>{children}</td>
}

export function ForecastChecklistItem({
  label,
  detail,
  ready,
  trailing,
}: {
  label: string
  detail?: ReactNode
  ready: boolean
  trailing?: ReactNode
}) {
  return (
    <li className={`forecast-checklist-item ${ready ? 'is-ready' : ''}`}>
      <div className="min-w-0">
        <div className="text-sm font-medium">{label}</div>
        {detail && <div className="text-xs text-[var(--hb-muted)] mt-0.5">{detail}</div>}
      </div>
      {trailing}
    </li>
  )
}

export function ForecastWizardRail({
  steps,
}: {
  steps: { label: string; state: 'pending' | 'active' | 'done' }[]
}) {
  return (
    <div className="forecast-wizard-rail" aria-label="Evaluation steps">
      {steps.map((step, idx) => (
        <div
          key={step.label}
          className={`forecast-wizard-step ${step.state === 'active' ? 'is-active' : ''} ${step.state === 'done' ? 'is-done' : ''}`}
        >
          <span className="forecast-wizard-num">{idx + 1}</span>
          {step.label}
        </div>
      ))}
    </div>
  )
}

export function ForecastDomainTile({
  label,
  count,
  active,
  onClick,
}: {
  label: string
  count?: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`forecast-domain-tile ${active ? 'is-active' : ''}`}
    >
      <div className="text-sm font-medium">{label}</div>
      <div className="text-xs text-[var(--hb-muted)] mt-0.5">{count ?? 0} items</div>
    </button>
  )
}

export function ForecastAdvisoryStrip({ children }: { children: ReactNode }) {
  return <div className="forecast-advisory-strip">{children}</div>
}

export function ForecastProgressRow({
  label,
  value,
  max,
  display,
}: {
  label: string
  value: number
  max: number
  display?: string
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-20 shrink-0 text-[var(--hb-muted)]">{label}</span>
      <div className="forecast-progress-bar">
        <span className="forecast-progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-28 shrink-0 text-right tabular-nums">{display ?? value}</span>
    </div>
  )
}