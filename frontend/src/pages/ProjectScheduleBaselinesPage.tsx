import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { ScheduleBaselineSelector } from '../components/project-schedule/ScheduleBaselineSelector'
import { ScheduleControlsPanel } from '../components/project-schedule/ScheduleControlsPanel'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { api, type ScheduleControlsComparisonBasis } from '../lib/api'
import { scheduleQueryKeySuffix } from '../lib/scheduleDataState'
import { scheduleAnalyticalQuery } from '../lib/scheduleNavLinks'

export function ProjectScheduleBaselinesPage() {
  const { projectKey = '' } = useParams()
  const [searchParams] = useSearchParams()
  const rawAsOf = searchParams.get('as_of') || ''
  const asOf = /^\d{4}-\d{2}-\d{2}$/.test(rawAsOf) ? rawAsOf : ''
  const requestAsOf = asOf || undefined
  const [comparisonBasis, setComparisonBasis] = useState<ScheduleControlsComparisonBasis>('prior_update')
  const asOfKey = scheduleQueryKeySuffix(asOf)

  const {
    data: baselinesPayload,
    isLoading: baselinesLoading,
    isFetching: baselinesFetching,
    error: baselinesError,
    refetch,
  } = useQuery({
    queryKey: ['project', 'schedule', projectKey, 'baselines', asOfKey],
    queryFn: () => api.getProjectScheduleBaselines(projectKey, { asOf: requestAsOf }),
    enabled: Boolean(projectKey),
    placeholderData: keepPreviousData,
  })

  const {
    data: controlsPayload,
    isLoading: controlsLoading,
    isFetching: controlsFetching,
    error: controlsError,
  } = useQuery({
    queryKey: ['project', 'schedule', 'controls', projectKey, asOfKey, comparisonBasis],
    queryFn: () =>
      api.getProjectScheduleControls(projectKey, {
        asOf: requestAsOf,
        comparisonBasis,
      }),
    enabled: Boolean(projectKey) && Boolean(baselinesPayload?.available),
    placeholderData: keepPreviousData,
  })

  if (baselinesLoading && !baselinesPayload) {
    return (
      <ProjectWorkspaceShell>
        <LoadingState label="Loading baseline management…" />
      </ProjectWorkspaceShell>
    )
  }

  if (baselinesError) {
    return (
      <ProjectWorkspaceShell>
        <ErrorState
          userMessage="Baseline management could not be loaded."
          error={baselinesError}
          onRetry={() => { void refetch() }}
        />
      </ProjectWorkspaceShell>
    )
  }

  const backHref = `/projects/${encodeURIComponent(projectKey)}/schedule${scheduleAnalyticalQuery(searchParams)}`

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4" data-testid="baseline-management-page">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="section-title mb-0">Manage Baselines</h3>
            <p className="mt-1 text-sm text-[var(--hb-muted)]">
              Assign named baseline anchors and choose the comparison basis used by Schedule Controls.
            </p>
          </div>
          <Link className="badge" to={backHref}>
            Back to Schedule Overview
          </Link>
        </div>

        {baselinesFetching ? (
          <div className="text-xs text-[var(--hb-muted)]" role="status">
            Refreshing baseline selections…
          </div>
        ) : null}

        <div id="baseline-management" data-testid="baseline-management-section">
          <ScheduleBaselineSelector
            projectKey={projectKey}
            baselines={baselinesPayload as Record<string, any> | undefined}
            loading={baselinesLoading && !baselinesPayload}
            fetching={baselinesFetching}
            asOf={requestAsOf}
          />
        </div>

        <ScheduleControlsPanel
          controls={controlsPayload}
          loading={controlsLoading && !controlsPayload}
          fetching={controlsFetching}
          error={controlsError}
          comparisonBasis={comparisonBasis}
          onComparisonBasisChange={setComparisonBasis}
        />
      </section>
    </ProjectWorkspaceShell>
  )
}
