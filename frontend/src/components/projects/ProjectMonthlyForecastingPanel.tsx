import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { EmptyState } from '../common/EmptyState'
import { ErrorState } from '../common/ErrorState'
import { LoadingState } from '../common/LoadingState'
import { ForecastMonthlyMatrixTable } from '../forecast/ForecastMonthlyMatrixTable'
import { selectForecastOutput } from './projectForecastOutputSelection'

type ProjectMonthlyForecastingPanelProps = {
  projectKey: string
  /** Requested output id from the route (`?outputId=`); resolved/validated against this project. */
  requestedOutputId?: string | null
}

/**
 * Project-scoped, read-only monthly forecast panel. Resolves the selected (or latest) persisted
 * output via the shared {@link selectForecastOutput} and renders its month-by-month matrix via the
 * pure, presentational {@link ForecastMonthlyMatrixTable}. Every read passes the route projectKey
 * explicitly (never the API default); the monthly-table read is scoped transitively through the
 * project-scoped output id (an invalid/foreign requested id is never fetched — it falls back to the
 * latest valid output). No export, full-screen, or generation controls.
 */
export function ProjectMonthlyForecastingPanel({
  projectKey,
  requestedOutputId,
}: ProjectMonthlyForecastingPanelProps) {
  // Both queries run unconditionally (stable hook order). The outputs list shares its key with
  // ProjectForecastingSummary so it is served from cache when arriving from the Forecasting page.
  const outputsQuery = useQuery({
    queryKey: ['forecast', 'db-outputs', projectKey],
    queryFn: () => api.getForecastDbOutputs(projectKey),
  })

  const outputs = outputsQuery.data?.outputs ?? []
  const { selectedOutputId } = selectForecastOutput(outputs, requestedOutputId)
  const outputId = selectedOutputId ?? undefined

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

  const selectedOutput = outputs.find((o) => o.output_id === outputId) ?? outputs[0]

  return (
    <section className="space-y-3">
      <p className="text-sm text-[var(--hb-muted)]">
        Forecast output
        {selectedOutput?.created_display ? ` · ${selectedOutput.created_display}` : ''} ·{' '}
        {months.length} {months.length === 1 ? 'month' : 'months'} · {rows.length}{' '}
        {rows.length === 1 ? 'cost code' : 'cost codes'}
      </p>
      <ForecastMonthlyMatrixTable table={table} />
    </section>
  )
}
