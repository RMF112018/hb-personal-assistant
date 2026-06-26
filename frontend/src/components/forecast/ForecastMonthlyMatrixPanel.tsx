import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { ForecastMonthlyMatrixTable } from './ForecastMonthlyMatrixTable'
import { ForecastPanel } from './ForecastPrimitives'

/**
 * Output-scoped monthly forecast matrix panel. Resolves the active persisted output (the page-owned
 * selection, else the project's latest output) and fetches its table-ready matrix. All values are
 * backend-authoritative; the table only formats / sorts / filters / groups.
 */
export function ForecastMonthlyMatrixPanel({
  project,
  activeOutputId,
}: {
  project: string
  activeOutputId?: string
}) {
  // Resolve the latest output when the page hasn't pinned one (mirrors the sibling panels).
  const { data: outputsResp } = useQuery({
    queryKey: ['forecast', 'db', 'outputs', project],
    queryFn: () => api.getForecastDbOutputs(project),
    enabled: !activeOutputId,
  })
  const outputId = activeOutputId ?? outputsResp?.outputs?.[0]?.output_id

  const {
    data: table,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['forecast', 'db', 'monthly-table', outputId],
    queryFn: () => api.getForecastDbMonthlyTable(outputId as string),
    enabled: Boolean(outputId),
  })

  if (!outputId) return null

  return (
    <ForecastPanel
      title="Monthly forecast"
      description="Completed-to-date actuals and forecast-to-complete by budget code and month, with row totals, a total row, and estimated cost at completion. All values are calculated and saved by the application."
    >
      <ForecastMonthlyMatrixTable
        table={table}
        loading={isLoading}
        error={error ? 'Please try again.' : null}
      />
    </ForecastPanel>
  )
}
