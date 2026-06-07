import type { ReactNode } from 'react'

type DashboardCardProps = {
  title: string
  subtitle?: string
  actions?: ReactNode
  footer?: ReactNode
  span?: 'default' | 'wide' | 'full' | 'tall'
  tone?: 'default' | 'attention' | 'success' | 'muted'
  children?: ReactNode
  className?: string
}

const spanClasses: Record<NonNullable<DashboardCardProps['span']>, string> = {
  default: '',
  wide: 'md:col-span-2',
  full: 'col-span-full',
  tall: 'md:row-span-2',
}

const toneClasses: Record<NonNullable<DashboardCardProps['tone']>, string> = {
  default: '',
  attention: 'border-amber-800/70',
  success: 'border-emerald-800/70',
  muted: 'opacity-90',
}

export function DashboardCard({
  title,
  subtitle,
  actions,
  footer,
  span = 'default',
  tone = 'default',
  children,
  className = '',
}: DashboardCardProps) {
  return (
    <article className={`card min-w-0 ${spanClasses[span]} ${toneClasses[tone]} hover:border-[var(--hb-accent)] transition-colors ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{title}</h3>
          {subtitle && <p className="mt-1 text-xs text-[var(--hb-muted)]">{subtitle}</p>}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
      {children && <div className="mt-3">{children}</div>}
      {footer && <div className="mt-3 border-t border-[var(--hb-border)] pt-2 text-xs text-[var(--hb-muted)]">{footer}</div>}
    </article>
  )
}
