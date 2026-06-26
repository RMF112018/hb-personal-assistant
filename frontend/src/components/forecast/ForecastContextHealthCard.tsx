import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { deriveForecastHealth, HEALTH_PILL } from './forecastHealth'
import { ForecastStatusPill } from './ForecastStatusPill'

/**
 * Panel-less forecast-health card, embedded inside the Forecast Context panel. Reuses the pure
 * deriveForecastHealth verdict and adds a source line: the selected output when one is active,
 * otherwise a fallback to the latest forecast (with its date). Persisted data only; no paths/payloads.
 */
export function ForecastContextHealthCard({
  project,
  readinessStatus,
  runFailed,
  activeOutputId,
}: {
  project: string
  readinessStatus: string | null
  runFailed: boolean
  activeOutputId?: string
}) {
  const { data: list } = useQuery({
    queryKey: ['forecast', 'db-outputs', project],
    queryFn: () => api.getForecastDbOutputs(project),
  })
  const outputs = list?.outputs ?? []
  const latest = outputs[0]
  const activeId = activeOutputId ?? latest?.output_id

  const { data: detail } = useQuery({
    queryKey: ['forecast', 'db-output', activeId],
    queryFn: () => api.getForecastDbOutput(activeId as string),
    enabled: Boolean(activeId),
  })

  const summary = detail?.summary
  const health = deriveForecastHealth({
    runFailed,
    readinessBlocked: readinessStatus === 'blocked',
    hasOutput: outputs.length > 0,
    confidenceLabel: summary?.forecast_confidence_label,
    maturityLabel: summary?.forecast_maturity_label,
  })

  let sourceLine: string | null = null
  if (activeOutputId) {
    sourceLine = 'Using selected forecast output.'
  } else if (latest) {
    sourceLine = `Using latest forecast: ${latest.created_display ?? '—'}.`
  }

  return (
    <div className="forecast-metric-card mt-3" aria-label={`Forecast health: ${health.label}`}>
      <div className="forecast-metric-label">Forecast health</div>
      <div className="flex flex-wrap items-center gap-2 mt-1">
        <ForecastStatusPill status={HEALTH_PILL[health.level]} />
        <span className="text-sm font-medium">{health.label}</span>
      </div>
      <p className="text-sm text-[var(--hb-muted)] mt-1">{health.detail}</p>
      {sourceLine && <p className="text-xs text-[var(--hb-muted)] mt-1">{sourceLine}</p>}
    </div>
  )
}
