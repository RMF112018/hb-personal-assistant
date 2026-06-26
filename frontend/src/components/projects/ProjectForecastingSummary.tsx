import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { EmptyState } from '../common/EmptyState'
import { ErrorState } from '../common/ErrorState'
import { LoadingState } from '../common/LoadingState'
import { ForecastResultsSummary } from '../forecast/ForecastResultsSummary'

type ProjectForecastingSummaryProps = {
  projectKey: string
}

/**
 * Project-scoped forecast status + KPI panel. Reads the persisted forecast outputs for the route
 * project only (explicit projectKey — never the API default), gates loading/error/no-output with
 * business-facing copy, and delegates the headline KPI cards to the read-only
 * {@link ForecastResultsSummary}. Both queries key off the same projectKey, so react-query serves
 * the outputs list from a single fetch. Never triggers forecast generation.
 */
export function ProjectForecastingSummary({ projectKey }: ProjectForecastingSummaryProps) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['forecast', 'db-outputs', projectKey],
    queryFn: () => api.getForecastDbOutputs(projectKey),
  })

  if (isLoading) {
    return <LoadingState label="Loading forecast information…" />
  }

  if (error) {
    return (
      <ErrorState
        userMessage="Forecast information could not be loaded. Check the local data connection and try again."
        error={error}
        onRetry={() => {
          void refetch()
        }}
      />
    )
  }

  const outputs = data?.outputs ?? []

  if (outputs.length === 0) {
    return (
      <EmptyState
        title="No forecast output is available for this project yet."
        hint="A project-specific forecast will appear here once one has been generated."
      />
    )
  }

  const latestUpdate = outputs[0]?.created_display

  return (
    <section className="space-y-3">
      {latestUpdate && (
        <p className="text-sm text-[var(--hb-muted)]">Last forecast update: {latestUpdate}</p>
      )}
      <ForecastResultsSummary project={projectKey} />
    </section>
  )
}
