import type { ReactNode } from 'react'

import { getErrorCopy } from '../../lib/errorCopy'
import { TechnicalDetails } from './TechnicalDetails'

type ErrorStateProps = {
  message?: string | null
  userMessage?: string
  error?: unknown
  onRetry?: () => void
  actions?: ReactNode
  details?: ReactNode
  showDetails?: boolean
  className?: string
}

export function ErrorState({
  message,
  userMessage,
  error,
  onRetry,
  actions,
  details,
  showDetails = false,
  className = '',
}: ErrorStateProps) {
  if (!message && !userMessage && !error && !details) return null

  const copy = getErrorCopy(error ?? message)
  const primaryMessage = userMessage || copy.userMessage
  const technicalDetail = details || copy.technicalDetail

  return (
    <div className={`card border-red-900/70 text-sm ${className}`} role="alert">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="font-medium text-red-300">{primaryMessage}</div>
          <div className="mt-1 text-xs text-[var(--hb-muted)]">The rest of the page remains advisory.</div>
        </div>
        {(onRetry || actions) && (
          <div className="flex shrink-0 flex-wrap gap-2">
            {onRetry && (
              <button className="badge" onClick={onRetry}>
                Retry
              </button>
            )}
            {actions}
          </div>
        )}
      </div>
      <TechnicalDetails
        summary="Technical details"
        details={technicalDetail}
        defaultOpen={showDetails}
        className="mt-3"
      />
    </div>
  )
}
