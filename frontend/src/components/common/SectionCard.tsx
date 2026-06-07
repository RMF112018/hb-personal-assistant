import type { ReactNode } from 'react'

type SectionCardProps = {
  title: string
  description?: string
  actions?: ReactNode
  footer?: ReactNode
  children: ReactNode
  className?: string
}

export function SectionCard({
  title,
  description,
  actions,
  footer,
  children,
  className = '',
}: SectionCardProps) {
  return (
    <section className={`card min-w-0 hover:border-[var(--hb-accent)] transition-colors ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="section-title mb-0">{title}</h3>
          {description && <p className="mt-1 text-sm text-[var(--hb-muted)]">{description}</p>}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
      <div className="mt-3">{children}</div>
      {footer && <div className="mt-3 border-t border-[var(--hb-border)] pt-2 text-xs text-[var(--hb-muted)]">{footer}</div>}
    </section>
  )
}
