import { useQuery } from '@tanstack/react-query'
import { LineChart } from 'lucide-react'

import { api } from '../../lib/api'
import { formatCurrency, formatNumber } from '../../lib/format'
import { EmptyState } from '../ui/EmptyState'
import { ForecastAdvisoryStrip, ForecastPanel } from './ForecastPrimitives'
import { ForecastStatusPill } from './ForecastStatusPill'
import { ForecastSummaryCard, ForecastSummaryGrid } from './ForecastSummary'

function confidencePill(label: string | null | undefined): string {
  if (label === 'high') return 'validated'
  if (label === 'moderate' || label === 'medium' || label === 'moderate-high') return 'attention'
  if (label === 'low' || label === 'none' || label === 'very low') return 'invalid'
  return 'unknown'
}

function maturityPill(tier: string | null | undefined): string {
  if (tier === 'M4' || tier === 'M5') return 'validated'
  if (tier === 'M2' || tier === 'M3') return 'attention'
  return 'unsupported'
}

/**
 * Executive headline for the latest persisted forecast output: top-level cost position, variances,
 * confidence, and maturity — read entirely from the persisted forecast data, above the detail tables.
 * Currency is formatted (no raw decimal strings); no output_id, paths, stamps, or payloads render.
 */
export function ForecastResultsSummary({ project }: { project: string }) {
  const { data: list, isLoading, error } = useQuery({
    queryKey: ['forecast', 'db-outputs', project],
    queryFn: () => api.getForecastDbOutputs(project),
  })
  const outputs = list?.outputs ?? []
  const output = outputs[0]
  const activeId = output?.output_id

  const { data: detail } = useQuery({
    queryKey: ['forecast', 'db-output', activeId],
    queryFn: () => api.getForecastDbOutput(activeId as string),
    enabled: Boolean(activeId),
  })
  const { data: ds } = useQuery({
    queryKey: ['forecast', 'db-decision-support', activeId],
    queryFn: () => api.getForecastDbDecisionSupport(activeId as string),
    enabled: Boolean(activeId),
  })

  if (error) {
    return (
      <ForecastPanel icon={LineChart} title="Results summary">
        <ForecastAdvisoryStrip>
          Forecast database not available. The headline forecast position appears here once configured.
        </ForecastAdvisoryStrip>
      </ForecastPanel>
    )
  }

  if (!isLoading && outputs.length === 0) {
    return (
      <ForecastPanel icon={LineChart} title="Results summary">
        <EmptyState
          title="No forecast output yet"
          hint="Generate a forecast for this project to see its headline position here."
        />
      </ForecastPanel>
    )
  }

  const scorecard = ds?.confidence_scorecards?.find((s) => s.scope === 'project')
  const maturity = ds?.maturity

  return (
    <ForecastPanel icon={LineChart} title="Results summary">
      <ForecastSummaryGrid>
        <ForecastSummaryCard
          label="Estimated final cost"
          value={formatCurrency(output?.estimated_final_cost)}
        />
        <ForecastSummaryCard
          label="Forecast at completion"
          value={formatCurrency(detail?.forecast_at_completion)}
        />
        <ForecastSummaryCard
          label="Cost to complete"
          value={formatCurrency(output?.cost_to_complete)}
        />
        <ForecastSummaryCard
          label="Variance to budget"
          value={formatCurrency(output?.variance_to_budget)}
          status={output?.variance_to_budget?.startsWith('-') ? 'ready' : 'neutral'}
        />
        <ForecastSummaryCard
          label="Variance to prior forecast"
          value={formatCurrency(output?.variance_to_prior_forecast)}
        />
        <div className="forecast-metric-card">
          <div className="forecast-metric-label">Forecast confidence</div>
          <div className="forecast-metric-value mt-1">
            <ForecastStatusPill status={confidencePill(scorecard?.label)} />
          </div>
          <div className="forecast-metric-detail">{scorecard?.label ?? 'no scorecard'}</div>
        </div>
        <div className="forecast-metric-card">
          <div className="forecast-metric-label">Project maturity</div>
          <div className="forecast-metric-value mt-1">
            <ForecastStatusPill status={maturityPill(maturity?.maturity_tier)} />
          </div>
          <div className="forecast-metric-detail">
            {maturity?.maturity_tier ?? '—'}
            {maturity
              ? ` · ${formatNumber(maturity.completed_month_count)} completed months`
              : ''}
          </div>
        </div>
      </ForecastSummaryGrid>
    </ForecastPanel>
  )
}
