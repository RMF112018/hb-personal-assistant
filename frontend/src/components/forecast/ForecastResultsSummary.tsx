import { useQuery } from '@tanstack/react-query'
import { LineChart } from 'lucide-react'

import { api } from '../../lib/api'
import { formatCurrency } from '../../lib/format'
import { EmptyState } from '../ui/EmptyState'
import { ForecastAdvisoryStrip, ForecastPanel } from './ForecastPrimitives'
import { ForecastSummaryCard, ForecastSummaryGrid } from './ForecastSummary'

/** Currency with cents preserved (for precise variances — a real zero reads "$0.00", not "$0"). */
function moneyCents(v: string | null | undefined): string {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/**
 * Single authoritative Forecast Summary for the active persisted output: cost position, variances,
 * budget basis, and the HB readiness-based confidence/maturity — all from the consolidated v63
 * read-model ``summary`` object. The active output is page-owned (lifted state); the in-panel
 * selector only appears when more than one output exists. Honest empty/zero copy throughout; never
 * "Unknown"/"Unsupported"/"no scorecard" for a valid output whose v66 decision-support is empty.
 */
export function ForecastResultsSummary({
  project,
  activeOutputId,
  onSelectOutput,
}: {
  project: string
  activeOutputId?: string
  onSelectOutput?: (id: string) => void
}) {
  const { data: list, isLoading, error } = useQuery({
    queryKey: ['forecast', 'db-outputs', project],
    queryFn: () => api.getForecastDbOutputs(project),
  })
  const outputs = list?.outputs ?? []
  const activeId = activeOutputId ?? outputs[0]?.output_id

  const { data: detail } = useQuery({
    queryKey: ['forecast', 'db-output', activeId],
    queryFn: () => api.getForecastDbOutput(activeId as string),
    enabled: Boolean(activeId),
  })

  if (error) {
    return (
      <ForecastPanel icon={LineChart} title="Forecast Summary">
        <ForecastAdvisoryStrip>
          Forecast database not available. The headline forecast position appears here once configured.
        </ForecastAdvisoryStrip>
      </ForecastPanel>
    )
  }

  if (!isLoading && outputs.length === 0) {
    return (
      <ForecastPanel icon={LineChart} title="Forecast Summary">
        <EmptyState
          title="No forecast output yet"
          hint="Generate a forecast for this project to see its headline position here."
        />
      </ForecastPanel>
    )
  }

  const s = detail?.summary
  const budgetUnavailable = !s || s.current_budget == null
  const noPrior = s?.variance_to_prior_forecast_status === 'no_prior_forecast'

  return (
    <ForecastPanel icon={LineChart} title="Forecast Summary">
      {outputs.length > 1 && onSelectOutput && (
        <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2 mb-1">
          Output
          <select
            className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
            value={activeId}
            onChange={(e) => onSelectOutput(e.target.value)}
          >
            {outputs.map((o) => (
              <option key={o.output_id} value={o.output_id}>
                {o.created_display ?? o.output_id}
              </option>
            ))}
          </select>
        </label>
      )}
      <ForecastSummaryGrid>
        <ForecastSummaryCard
          label="Estimated at Completion"
          value={formatCurrency(s?.estimated_at_completion)}
        />
        <ForecastSummaryCard
          label="Total Cost to Date"
          value={formatCurrency(s?.total_cost_to_date)}
        />
        <ForecastSummaryCard label="Cost to Complete" value={formatCurrency(s?.cost_to_complete)} />
        <ForecastSummaryCard
          label="Current Budget"
          value={budgetUnavailable ? 'Budget unavailable' : formatCurrency(s?.current_budget)}
          detail={budgetUnavailable ? undefined : (s?.budget_basis_label ?? undefined)}
        />
        <ForecastSummaryCard
          label="Variance to Budget"
          value={moneyCents(s?.variance_to_budget)}
          status={s?.variance_to_budget?.startsWith('-') ? 'ready' : 'neutral'}
        />
        <ForecastSummaryCard
          label="Variance from Prior Forecast"
          value={noPrior ? 'No prior forecast' : moneyCents(s?.variance_to_prior_forecast)}
        />
        <ForecastSummaryCard
          label="Forecast Confidence"
          value={s?.forecast_confidence_label ?? '—'}
          detail={s?.forecast_confidence_basis ?? undefined}
        />
        <ForecastSummaryCard
          label="Forecast Maturity"
          value={s?.forecast_maturity_label ?? '—'}
          detail={s?.forecast_maturity_basis ?? undefined}
        />
      </ForecastSummaryGrid>
    </ForecastPanel>
  )
}
