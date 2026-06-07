import type { ReactNode } from 'react'

type PrimaryPageLayoutProps = {
  title: string
  subtitle?: string
  actions?: ReactNode
  status?: ReactNode
  children: ReactNode
  className?: string
}

export function PrimaryPageLayout({
  title,
  subtitle,
  actions,
  status,
  children,
  className = '',
}: PrimaryPageLayoutProps) {
  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {/* Visual page label only (not a heading). Canonical <h1> comes from shell PageHeader. */}
          <div className="text-lg font-semibold">{title}</div>
          {subtitle && <p className="mt-1 text-sm text-[var(--hb-muted)]">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {status && <div className="flex flex-wrap items-center gap-2">{status}</div>}
      <div className="min-w-0">{children}</div>
    </div>
  )
}
