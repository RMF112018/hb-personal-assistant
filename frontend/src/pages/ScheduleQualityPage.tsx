import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import {
  ScheduleBackLink,
  SchedulePageHeader,
  ScheduleShell,
  ScheduleSubnav,
} from '../components/schedule/SchedulePageChrome'
import {
  ScheduleProjectPicker,
  useScheduleProjectParam,
  useScheduleProjects,
} from '../components/schedule/ScheduleProjectPicker'
import { ScheduleVersionPicker } from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'
import { ScheduleHealthActionQueue } from '../components/schedule/health/ScheduleHealthActionQueue'
import { ScheduleHealthBaselinePanel } from '../components/schedule/health/ScheduleHealthBaselinePanel'
import { ScheduleHealthCpmPanel } from '../components/schedule/health/ScheduleHealthCpmPanel'
import { ScheduleHealthDeferredPanel } from '../components/schedule/health/ScheduleHealthDeferredPanel'
import { ScheduleHealthEvidencePanel } from '../components/schedule/health/ScheduleHealthEvidencePanel'
import { ScheduleHealthOverview } from '../components/schedule/health/ScheduleHealthOverview'
import { ScheduleHealthQualityPanel } from '../components/schedule/health/ScheduleHealthQualityPanel'
import { ScheduleHealthVersionComparisonPanel } from '../components/schedule/health/ScheduleHealthVersionComparisonPanel'
import { buildHealthModel, text, type QualitySummary } from '../components/schedule/health/healthShared'
import { api, getLocalUiRole } from '../lib/api'

export function ScheduleQualityPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const [versionKey, setVersionKey] = useState(searchParams.get('version') || '')
  const [compareKey, setCompareKey] = useState(searchParams.get('compare') || 'default_prior')
  const queryClient = useQueryClient()
  const canRerun = getLocalUiRole() === 'operator' || getLocalUiRole() === 'admin'
  const { data: projectsData } = useScheduleProjects()

  const { data: health, isLoading, error, refetch } = useQuery({
    queryKey: ['schedules', 'health-data', versionKey, projectKey || '__unscoped__'],
    queryFn: () => api.getScheduleHealthData(versionKey, projectKey || undefined),
    enabled: Boolean(versionKey),
  })

  const { data: qualityDetail } = useQuery({
    queryKey: ['schedules', 'quality-detail', versionKey],
    queryFn: () => api.getScheduleQuality(versionKey) as Promise<QualitySummary>,
    enabled: Boolean(versionKey && health),
  })

  const rerun = useMutation({
    mutationFn: () => api.rerunScheduleQuality(versionKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules', 'health-data', versionKey] })
      queryClient.invalidateQueries({ queryKey: ['schedules', 'quality-detail', versionKey] })
    },
  })

  const model = buildHealthModel(health, qualityDetail)
  const availableDiffs = model.availableDiffs

  function onProjectChange(next: string) {
    setProjectKey(next)
    setVersionKey('')
    setCompareKey('default_prior')
    const params = new URLSearchParams(searchParams)
    if (next) params.set('project', next)
    else params.delete('project')
    params.delete('version')
    params.delete('compare')
    setSearchParams(params, { replace: true })
  }

  function onVersionChange(next: string) {
    setVersionKey(next)
    setCompareKey('default_prior')
    const params = new URLSearchParams(searchParams)
    if (next) {
      params.set('version', next)
      const inferred = next.split('|')[0]
      if (inferred) params.set('project', inferred)
    } else {
      params.delete('version')
    }
    params.delete('compare')
    setSearchParams(params, { replace: true })
  }

  function onCompareChange(next: string) {
    setCompareKey(next)
    const params = new URLSearchParams(searchParams)
    if (next && next !== 'default_prior') params.set('compare', next)
    else params.delete('compare')
    setSearchParams(params, { replace: true })
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule Health"
        subtitle="PM-first schedule reliability, baseline drift, version-change, and CPM-quality assessment."
      />

      <div className="forecast-panel p-4 mb-3 max-w-5xl flex flex-wrap gap-3 items-end">
        <ScheduleProjectPicker value={projectKey} onChange={onProjectChange} className="min-w-[16rem]" />
        <ScheduleVersionPicker projectKey={projectKey} value={versionKey} onChange={onVersionChange} />
        <label className="block text-sm min-w-[14rem]">
          <span className="text-[var(--hb-muted)]">Compare against</span>
          <select
            className="mt-1 block w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5 text-sm"
            value={compareKey}
            disabled={!versionKey || availableDiffs.length === 0}
            onChange={(event) => onCompareChange(event.target.value)}
          >
            <option value="default_prior">Default prior version</option>
            {availableDiffs.map((diff, index) => (
              <option key={String(diff.diff_id ?? diff.fact_id ?? index)} value={String(diff.diff_id ?? index)}>
                {text(diff.from_schedule_version_key ?? diff.from_version_key ?? `Available diff ${index + 1}`)}
              </option>
            ))}
          </select>
        </label>
        {projectKey ? (
          <Link
            className="text-sm underline self-end pb-1"
            to={`/schedules/versions?project=${encodeURIComponent(projectKey)}`}
          >
            View project versions
          </Link>
        ) : null}
        {versionKey && canRerun ? (
          <button
            type="button"
            className="text-sm px-3 py-1.5 rounded border border-[var(--hb-border)]"
            disabled={rerun.isPending}
            onClick={() => rerun.mutate()}
          >
            {rerun.isPending ? 'Re-running...' : 'Rerun evaluation'}
          </button>
        ) : null}
      </div>

      {!versionKey ? (
        <EmptyState title="Select a schedule version" hint="Choose a version to review schedule health." />
      ) : null}
      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading schedule health...</p> : null}
      {error ? <EmptyState title="Could not load schedule health" /> : null}

      {versionKey && health ? (
        <div className="space-y-6">
          <p className="text-xs text-[var(--hb-muted)] max-w-5xl">
            Evidence basis is labeled on each section: Application-computed CPM is the engine&apos;s own
            computation; Source-export, Quality metric, Baseline crosswalk, and Identity-safe diff are read
            from imported or evaluated evidence. They are reported separately and never conflated.
          </p>

          <ScheduleHealthOverview
            model={model}
            health={health}
            qualityDetail={qualityDetail}
            projectKey={projectKey}
            projects={projectsData?.projects}
          />

          <ScheduleHealthCpmPanel data={health.computed_cpm_health} versionKey={versionKey} />

          <ScheduleHealthEvidencePanel model={model} />

          <ScheduleHealthQualityPanel model={model} />

          <ScheduleHealthBaselinePanel model={model} />

          <ScheduleHealthVersionComparisonPanel model={model} health={health} projectKey={projectKey} />

          <ScheduleHealthActionQueue model={model} />

          <ScheduleHealthDeferredPanel model={model} health={health} />

          {model.qualityStatus === 'pending' || model.qualityStatus === 'running' ? (
            <button type="button" className="text-sm underline" onClick={() => refetch()}>
              Refresh status
            </button>
          ) : null}
        </div>
      ) : null}
    </ScheduleShell>
  )
}
