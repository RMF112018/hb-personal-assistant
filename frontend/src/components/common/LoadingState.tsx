import type { ReactNode } from 'react'

type LoadingStateProps = {
  label?: string
  actions?: ReactNode
  className?: string
}

export function LoadingState({
  label = 'Loading…',
  actions,
  className = '',
}: LoadingStateProps) {
  return (
    <div className={`card flex items-center justify-between gap-3 text-sm text-[var(--hb-muted)] ${className}`}>
      <span>{label}</span>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  )
}
