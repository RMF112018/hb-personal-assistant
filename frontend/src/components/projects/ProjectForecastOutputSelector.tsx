import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { formatCurrency } from '../../lib/format'
import { EmptyState } from '../common/EmptyState'
import { ErrorState } from '../common/ErrorState'
import { LoadingState } from '../common/LoadingState'
import { SectionCard } from '../common/SectionCard'
import { selectForecastOutput } from './projectForecastOutputSelection'

type ProjectForecastOutputSelectorProps = {
  projectKey: string
  requestedOutputId?: string | null
  onSelectOutput: (outputId: string) => void
}

/**
 * Project-scoped Forecast History / output selector. Reads the persisted outputs for the route
 * project only (explicit projectKey — never the API default) and lets the operator pick a prior
 * output; the choice is lifted to the route via {@link onSelectOutput}. Selection validity/fallback
 * is resolved by the shared {@link selectForecastOutput}, so this matches the summary and monthly
 * panel exactly. Read-only: no generation, no export.
 */
export function ProjectForecastOutputSelector({
  projectKey,
  requestedOutputId,
  onSelectOutput,
}: ProjectForecastOutputSelectorProps) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['forecast', 'db-outputs', projectKey],
    queryFn: () => api.getForecastDbOutputs(projectKey),
  })

  if (isLoading) {
    return <LoadingState label="Loading forecast history…" />
  }

  if (error) {
    return (
      <ErrorState
        userMessage="Forecast history could not be loaded. Check the local data connection and try again."
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
        title="No forecast outputs are available for this project yet."
        hint="Create a forecast for this project to build its history."
      />
    )
  }

  const { selectedOutputId, isInvalidSelection } = selectForecastOutput(outputs, requestedOutputId)

  return (
    <SectionCard title="Forecast History">
      <p className="text-sm text-[var(--hb-muted)]">
        Select a forecast output to review project summary and monthly values.
      </p>

      {isInvalidSelection && (
        <p className="mt-2 text-sm text-[var(--hb-warning,#b45309)]">
          The selected forecast output is not available for this project. Showing the latest
          available output.
        </p>
      )}

      <ul className="mt-3 space-y-2">
        {outputs.map((output, index) => {
          const selected = output.output_id === selectedOutputId
          return (
            <li key={output.output_id}>
              <button
                type="button"
                aria-current={selected ? 'true' : undefined}
                onClick={() => onSelectOutput(output.output_id)}
                className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
                  selected
                    ? 'border-[var(--hb-accent)] bg-[var(--hb-surface,transparent)]'
                    : 'border-[var(--hb-border)] hover:border-[var(--hb-accent)]'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span className="font-medium">{output.created_display ?? 'Forecast output'}</span>
                  {index === 0 && <span className="badge">Latest</span>}
                  {selected && <span className="badge">Selected</span>}
                </span>
                {output.estimated_final_cost && (
                  <span className="mt-1 block text-xs text-[var(--hb-muted)]">
                    Estimated at Completion: {formatCurrency(output.estimated_final_cost)}
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </SectionCard>
  )
}
