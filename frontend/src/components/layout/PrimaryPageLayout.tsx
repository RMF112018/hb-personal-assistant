import type { ReactNode } from 'react'

type PrimaryPageLayoutProps = {
  // title/subtitle removed: the AppShell chrome header now owns the active page title (dynamic per route + route handle metadata).
  // A single sr-only <h1> in the shell main provides the accessible page heading; card/section headings (h3) live inside content.
  actions?: ReactNode
  status?: ReactNode
  children: ReactNode
  className?: string
}

export function PrimaryPageLayout({
  actions,
  status,
  children,
  className = '',
}: PrimaryPageLayoutProps) {
  return (
    <div className={`space-y-4 ${className}`}>
      {(actions || status) && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          {/* spacer to preserve actions alignment when title block is no longer rendered */}
          <div className="min-w-0 flex-1" />
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {status && <div className="flex flex-wrap items-center gap-2">{status}</div>}
      <div className="min-w-0">{children}</div>
    </div>
  )
}
