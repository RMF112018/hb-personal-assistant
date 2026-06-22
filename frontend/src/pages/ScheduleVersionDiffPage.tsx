import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  ScheduleActionButton,
  ScheduleBackLink,
  SchedulePageHeader,
  ScheduleShell,
  ScheduleSubnav,
} from '../components/schedule/SchedulePageChrome'
import {
  DEFAULT_SCHEDULE_PROJECT,
  useScheduleVersions,
} from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

export function ScheduleVersionDiffPage() {
  const projectKey = DEFAULT_SCHEDULE_PROJECT
  const { data: versionsData } = useScheduleVersions(projectKey)
  const versions = Array.isArray(versionsData) ? (versionsData as Record<string, unknown>[]) : []

  const [fromVersion, setFromVersion] = useState('')
  const [toVersion, setToVersion] = useState('')
  const [runDiff, setRunDiff] = useState(false)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['schedules', 'diff', projectKey, fromVersion, toVersion],
    queryFn: () => api.getScheduleVersionDiff(projectKey, fromVersion, toVersion),
    enabled: runDiff && Boolean(fromVersion && toVersion && fromVersion !== toVersion),
  })

  const diff = data as Record<string, unknown> | undefined
  let summary: Record<string, unknown> = {}
  if (diff?.summary_json) {
    try {
      summary = JSON.parse(String(diff.summary_json)) as Record<string, unknown>
    } catch {
      summary = {}
    }
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Version diff"
        subtitle="Activity-ID-aligned drift analysis between two committed schedule versions."
      />

      <div className="forecast-panel p-4 space-y-3 max-w-2xl text-sm">
        <label className="block">
          <span className="text-[var(--hb-muted)]">From version</span>
          <select
            className="mt-1 block w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5"
            value={fromVersion}
            onChange={(e) => {
              setFromVersion(e.target.value)
              setRunDiff(false)
            }}
          >
            <option value="">Select baseline version</option>
            {versions.map((v) => (
              <option key={String(v.schedule_version_key)} value={String(v.schedule_version_key)}>
                {String(v.display_label)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[var(--hb-muted)]">To version</span>
          <select
            className="mt-1 block w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5"
            value={toVersion}
            onChange={(e) => {
              setToVersion(e.target.value)
              setRunDiff(false)
            }}
          >
            <option value="">Select comparison version</option>
            {versions.map((v) => (
              <option key={String(v.schedule_version_key)} value={String(v.schedule_version_key)}>
                {String(v.display_label)}
              </option>
            ))}
          </select>
        </label>
        <ScheduleActionButton
          disabled={!fromVersion || !toVersion || fromVersion === toVersion}
          onClick={() => {
            setRunDiff(true)
            void refetch()
          }}
        >
          Compare versions
        </ScheduleActionButton>
      </div>

      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Computing diff…</p> : null}
      {error ? <EmptyState title="Could not compute version diff" /> : null}

      {diff && runDiff ? (
        <div className="forecast-panel p-4 space-y-2 text-sm mt-3">
          <p>
            <strong>Activities added:</strong> {String(diff.activity_added_count)} ·{' '}
            <strong>removed:</strong> {String(diff.activity_removed_count)} ·{' '}
            <strong>changed:</strong> {String(diff.activity_changed_count)}
          </p>
          <p>
            <strong>Relationships added:</strong> {String(diff.relationship_added_count)} ·{' '}
            <strong>removed:</strong> {String(diff.relationship_removed_count)} ·{' '}
            <strong>logic churn:</strong> {String(diff.logic_churn_rate)}
          </p>
          {Array.isArray(summary.added_activity_ids) && summary.added_activity_ids.length > 0 ? (
            <p>
              <strong>Sample added IDs:</strong>{' '}
              {(summary.added_activity_ids as string[]).slice(0, 10).join(', ')}
            </p>
          ) : null}
          {Array.isArray(summary.removed_activity_ids) && summary.removed_activity_ids.length > 0 ? (
            <p>
              <strong>Sample removed IDs:</strong>{' '}
              {(summary.removed_activity_ids as string[]).slice(0, 10).join(', ')}
            </p>
          ) : null}
        </div>
      ) : null}
    </ScheduleShell>
  )
}