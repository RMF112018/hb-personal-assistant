import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { EmptyState } from '../common/EmptyState'
import { ErrorState } from '../common/ErrorState'
import { LoadingState } from '../common/LoadingState'
import { ForecastMonthlyMatrixTable } from '../forecast/ForecastMonthlyMatrixTable'

type ProjectMonthlyForecastingPanelProps = {
  projectKey: string
}

/**
 * Project-scoped, read-only monthly forecast panel. Resolves the project's latest persisted output
 * (outputs are newest-first) and renders its month-by-month matrix via the pure, presentational
 * {@link ForecastMonthlyMatrixTable}. Every read passes the route projectKey explicitly (never the
 * API default); the monthly-table read is scoped transitively through the project-scoped output id.
 * No export, full-screen, or generation controls — gates loading/error/no-output/no-monthly states
 * with business-facing copy.
 */
export function ProjectMonthlyForecastingPanel({ projectKey }: ProjectMonthlyForecastingPanelProps) {
  // Both queries run unconditionally (stable hook order). The outputs list shares its key with
  // ProjectForecastingSummary so it is served from cache when arriving from the Forecasting page.
  const outputsQuery = useQuery({
    queryKey: ['forecast', 'db-outputs', projectKey],
    queryFn: () => api.getForecastDbOutputs(projectKey),
  })

  const outputs = outputsQuery.data?.outputs ?? []
  const latestOutput = outputs[0]
  const outputId = latestOutput?.output_id

  const monthlyQuery = useQuery({
    queryKey: ['forecast', 'db-monthly-table', outputId],
    queryFn: () => api.getForecastDbMonthlyTable(outputId as string),
    enabled: Boolean(outputId),
  })

  if (outputsQuery.isLoading || (outputId && monthlyQuery.isLoading)) {
    return <LoadingState label="Loading monthly forecast information…" />
  }

  if (outputsQuery.error || monthlyQuery.error) {
    return (
      <ErrorState
        userMessage="Monthly forecast information could not be loaded. Check the local data connection and try again."
        error={outputsQuery.error ?? monthlyQuery.error}
        onRetry={() => {
          void (outputsQuery.error ? outputsQuery.refetch() : monthlyQuery.refetch())
        }}
      />
    )
  }

  if (outputs.length === 0) {
    return (
      <EmptyState
        title="No forecast output is available for this project yet."
        hint="A project-specific forecast will appear here once one has been generated."
      />
    )
  }

  const table = monthlyQuery.data
  const months = table?.months ?? []
  const rows = table?.rows ?? []
  const hasMonthlyValues =
    Boolean(table) && table?.status === 'ready' && months.length > 0 && rows.length > 0

  if (!hasMonthlyValues) {
    return (
      <EmptyState
        title="No monthly forecast values are available for this forecast output yet."
        hint="Once month-by-month values are available for this forecast, they will appear here."
      />
    )
  }

  return (
    <section className="space-y-3">
      <p className="text-sm text-[var(--hb-muted)]">
        Latest forecast output
        {latestOutput?.created_display ? ` · ${latestOutput.created_display}` : ''} · {months.length}{' '}
        {months.length === 1 ? 'month' : 'months'} · {rows.length}{' '}
        {rows.length === 1 ? 'cost code' : 'cost codes'}
      </p>
      <ForecastMonthlyMatrixTable table={table} />
    </section>
  )
}
