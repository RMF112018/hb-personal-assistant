import { ForecastActionLink } from './ForecastPageChrome'

/**
 * Presentational callout for readiness blockers, generation errors, and non-blocking advisories.
 * All copy is resolved by the caller and passed in as path-free, payload-free lines — this component
 * never renders raw values, stamps, or paths. Errors announce as alerts; warnings as polite status.
 */
export interface ForecastErrorCalloutProps {
  tone?: 'error' | 'warning'
  title?: string
  lines: string[]
  actions?: { label: string; to?: string }[]
}

export function ForecastErrorCallout({
  tone = 'error',
  title,
  lines,
  actions = [],
}: ForecastErrorCalloutProps) {
  if (lines.length === 0 && actions.length === 0 && !title) return null
  const isError = tone === 'error'
  const toneClass = isError
    ? 'border-rose-700/70 bg-rose-950/25 text-rose-300'
    : 'border-amber-700/70 bg-amber-950/20 text-amber-300'

  return (
    <div
      className={`mt-2 rounded-md border px-3 py-2 text-sm ${toneClass}`}
      role={isError ? 'alert' : 'status'}
    >
      {title && <p className="font-medium">{title}</p>}
      {lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
      {actions.map((action) => (
        <p key={action.label}>
          {action.to ? (
            <ForecastActionLink to={action.to}>{action.label}</ForecastActionLink>
          ) : (
            action.label
          )}
        </p>
      ))}
    </div>
  )
}
