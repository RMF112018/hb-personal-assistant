import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { api } from '../../lib/api'
import { formatCurrency } from '../../lib/format'
import { EmptyState } from '../common/EmptyState'
import { ErrorState } from '../common/ErrorState'
import { LoadingState } from '../common/LoadingState'
import { SectionCard } from '../common/SectionCard'
import {
  buildBudgetVsEac,
  buildCostPosition,
  buildMonthlySeries,
  hasAnyVisualization,
} from './projectForecastDashboardData'
import { selectForecastOutput } from './projectForecastOutputSelection'

type ProjectForecastDashboardVisualizationsProps = {
  projectKey: string
  requestedOutputId?: string | null
}

const CHART_HEIGHT = 200
const CURRENCY_AXIS_WIDTH = 84

/**
 * Read-only Forecast Dashboard for the selected output. Resolves the SAME validated output id as the
 * summary/monthly via the shared {@link selectForecastOutput} (an invalid/foreign requested id is
 * never fetched — detail/monthly are gated on a valid id), reshapes only existing detail/monthly
 * fields into recharts visuals, and renders nothing editable (no export/fullscreen/edit). Each block
 * pairs a chart with an accessible figcaption so the values are available without the SVG.
 */
export function ProjectForecastDashboardVisualizations({
  projectKey,
  requestedOutputId,
}: ProjectForecastDashboardVisualizationsProps) {
  const outputsQuery = useQuery({
    queryKey: ['forecast', 'db-outputs', projectKey],
    queryFn: () => api.getForecastDbOutputs(projectKey),
  })

  const outputs = outputsQuery.data?.outputs ?? []
  const { selectedOutputId } = selectForecastOutput(outputs, requestedOutputId)

  const detailQuery = useQuery({
    queryKey: ['forecast', 'db-output', selectedOutputId],
    queryFn: () => api.getForecastDbOutput(selectedOutputId as string),
    enabled: Boolean(selectedOutputId),
  })

  const monthlyQuery = useQuery({
    queryKey: ['forecast', 'db-monthly-table', selectedOutputId],
    queryFn: () => api.getForecastDbMonthlyTable(selectedOutputId as string),
    enabled: Boolean(selectedOutputId),
  })

  if (
    outputsQuery.isLoading ||
    (selectedOutputId && (detailQuery.isLoading || monthlyQuery.isLoading))
  ) {
    return <LoadingState label="Loading forecast dashboard…" />
  }

  if (outputsQuery.error || detailQuery.error || monthlyQuery.error) {
    return (
      <ErrorState
        userMessage="Forecast dashboard could not be loaded. Check the local data connection and try again."
        error={outputsQuery.error ?? detailQuery.error ?? monthlyQuery.error}
      />
    )
  }

  if (!selectedOutputId) {
    return (
      <EmptyState
        title="No forecast output is available for this project yet."
        hint="Create a forecast for this project to see its dashboard."
      />
    )
  }

  const summary = detailQuery.data?.summary ?? null
  const budget = buildBudgetVsEac(summary)
  const cost = buildCostPosition(summary)
  const monthly = buildMonthlySeries(monthlyQuery.data)

  if (!hasAnyVisualization(budget, cost, monthly)) {
    return (
      <EmptyState
        title="No dashboard visualization data is available for the selected forecast output yet."
        hint="Once the selected forecast has comparable values, charts will appear here."
      />
    )
  }

  const firstMonth = monthly.series[0]?.label
  const lastMonth = monthly.series[monthly.series.length - 1]?.label
  const monthlyRange =
    monthly.series.length > 1 && firstMonth && lastMonth ? `${firstMonth}–${lastMonth}` : firstMonth

  return (
    <SectionCard title="Forecast Dashboard">
      <p className="text-sm text-[var(--hb-muted)]">
        A visual read of the selected forecast output. Charts are read-only.
      </p>

      <div className="mt-3 grid gap-4 md:grid-cols-2">
        {budget.hasData && (
          <figure className="m-0">
            <figcaption className="mb-1">
              <span className="font-medium">Budget vs EAC</span>
              <span className="block text-xs text-[var(--hb-muted)]">
                Current Budget {formatCurrency(budget.points[0].value)} · EAC{' '}
                {formatCurrency(budget.points[1].value)}
              </span>
            </figcaption>
            <div
              role="img"
              aria-label={`Bar chart comparing Current Budget ${formatCurrency(
                budget.points[0].value,
              )} and Estimated at Completion ${formatCurrency(budget.points[1].value)}`}
            >
              <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                <BarChart data={budget.points}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis
                    width={CURRENCY_AXIS_WIDTH}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => formatCurrency(v)}
                  />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} />
                  <Bar dataKey="value" fill="var(--hb-accent, #6366f1)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </figure>
        )}

        {cost.hasData && (
          <figure className="m-0">
            <figcaption className="mb-1">
              <span className="font-medium">Cost Position</span>
              <span className="block text-xs text-[var(--hb-muted)]">
                Cost to Date {formatCurrency(cost.points[0].value)} · To Complete{' '}
                {formatCurrency(cost.points[1].value)}
              </span>
            </figcaption>
            <div
              role="img"
              aria-label={`Bar chart of Cost to Date ${formatCurrency(
                cost.points[0].value,
              )} and Cost to Complete ${formatCurrency(cost.points[1].value)}`}
            >
              <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                <BarChart data={cost.points}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis
                    width={CURRENCY_AXIS_WIDTH}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => formatCurrency(v)}
                  />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} />
                  <Bar dataKey="value" fill="var(--hb-accent, #6366f1)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </figure>
        )}

        {monthly.hasData && (
          <figure className="m-0 md:col-span-2">
            <figcaption className="mb-1">
              <span className="font-medium">Monthly Forecast Distribution</span>
              <span className="block text-xs text-[var(--hb-muted)]">
                {monthly.series.length} {monthly.series.length === 1 ? 'month' : 'months'}
                {monthlyRange ? ` · ${monthlyRange}` : ''}
              </span>
            </figcaption>
            <div
              role="img"
              aria-label={`Line chart of monthly forecast values across ${monthly.series.length} months`}
            >
              <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                <LineChart data={monthly.series}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis
                    width={CURRENCY_AXIS_WIDTH}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => formatCurrency(v)}
                  />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} />
                  <Line
                    type="monotone"
                    dataKey="amount"
                    stroke="var(--hb-accent, #6366f1)"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </figure>
        )}
      </div>
    </SectionCard>
  )
}
