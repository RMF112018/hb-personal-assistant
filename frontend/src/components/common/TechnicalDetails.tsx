import type { ReactNode } from 'react'

type TechnicalDetailsProps = {
  summary: string
  details?: ReactNode
  defaultOpen?: boolean
  className?: string
}

export function TechnicalDetails({
  summary,
  details,
  defaultOpen = false,
  className = '',
}: TechnicalDetailsProps) {
  if (!details) return null
  return (
    <details className={`text-xs text-[var(--hb-muted)] ${className}`} open={defaultOpen}>
      <summary className="cursor-pointer select-none">{summary}</summary>
      <div className="mt-2 rounded border border-[var(--hb-border)] bg-black/10 p-2 font-mono whitespace-pre-wrap">
        {formatDetails(details)}
      </div>
    </details>
  )
}

function formatDetails(details: ReactNode): ReactNode {
  if (typeof details === 'string' || typeof details === 'number') return details
  return details
}
