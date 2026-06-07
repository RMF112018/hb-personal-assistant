import type { ReactNode } from 'react'

type EmptyStateProps = {
  title?: string
  hint?: string
  actions?: ReactNode
  className?: string
}

export function EmptyState({
  title = 'No data',
  hint,
  actions,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`card text-sm text-[var(--hb-muted)] ${className}`}>
      <div className="font-medium text-[var(--hb-text)]">{title}</div>
      {hint && <div className="mt-1 text-xs">{hint}</div>}
      {actions && <div className="mt-3 flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}
