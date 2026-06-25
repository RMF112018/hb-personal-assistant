import { useQuery } from '@tanstack/react-query'
import { HeartPulse } from 'lucide-react'

import { api } from '../../lib/api'
import { deriveForecastHealth, HEALTH_PILL } from './forecastHealth'
import { ForecastPanel } from './ForecastPrimitives'
import { ForecastStatusPill } from './ForecastStatusPill'

/**
 * Renders the forecast-health verdict for the selected project. Status is conveyed by an explicit
 * text label and detail line (never color alone). Persisted forecast data only; no payloads/paths.
 */
export function ForecastHealthSummary({
  project,
  readinessStatus,
  runFailed,
}: {
  project: string
  readinessStatus: string | null
  runFailed: boolean
}) {
  const { data: list } = useQuery({
    queryKey: ['forecast', 'db-outputs', project],
    queryFn: () => api.getForecastDbOutputs(project),
  })
  const outputs = list?.outputs ?? []
  const activeId = outputs[0]?.output_id

  const { data: ds } = useQuery({
    queryKey: ['forecast', 'db-decision-support', activeId],
    queryFn: () => api.getForecastDbDecisionSupport(activeId as string),
    enabled: Boolean(activeId),
  })

  const scorecard = ds?.confidence_scorecards?.find((s) => s.scope === 'project')
  const health = deriveForecastHealth({
    runFailed,
    readinessBlocked: readinessStatus === 'blocked',
    hasOutput: outputs.length > 0,
    confidenceLabel: scorecard?.label,
    maturityTier: ds?.maturity?.maturity_tier,
  })

  return (
    <ForecastPanel icon={HeartPulse} title="Forecast health">
      <div className="flex flex-wrap items-center gap-2" aria-label={`Forecast health: ${health.label}`}>
        <ForecastStatusPill status={HEALTH_PILL[health.level]} />
        <span className="text-sm font-medium">{health.label}</span>
      </div>
      <p className="text-sm text-[var(--hb-muted)] mt-2">{health.detail}</p>
    </ForecastPanel>
  )
}
