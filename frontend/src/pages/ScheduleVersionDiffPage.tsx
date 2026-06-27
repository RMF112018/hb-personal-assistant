import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import {
  ScheduleActionButton,
  ScheduleBackLink,
  SchedulePageHeader,
  ScheduleShell,
  ScheduleSubnav,
  ScheduleTable,
  ScheduleTd,
  ScheduleTh,
} from '../components/schedule/SchedulePageChrome'
import {
  ScheduleProjectPicker,
  useScheduleProjectParam,
} from '../components/schedule/ScheduleProjectPicker'
import { useScheduleVersions } from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

export function ScheduleVersionDiffPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const { data: versionsData } = useScheduleVersions(projectKey || undefined)
  const versions = Array.isArray(versionsData) ? (versionsData as Record<string, unknown>[]) : []

  const [fromVersion, setFromVersion] = useState(searchParams.get('from') ?? '')
  const [toVersion, setToVersion] = useState(searchParams.get('to') ?? '')
  const [diffId, setDiffId] = useState(searchParams.get('diff_id') ?? '')
  const [severity, setSeverity] = useState('')
  const [domain, setDomain] = useState('')
  const [attentionOnly, setAttentionOnly] = useState(false)
  const [activitySearch, setActivitySearch] = useState('')
  const [runDiff, setRunDiff] = useState(Boolean(searchParams.get('diff_id')))

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['schedules', 'diff', projectKey, fromVersion, toVersion],
    queryFn: () => api.getScheduleVersionDiff(projectKey, fromVersion, toVersion),
    enabled: runDiff && Boolean(fromVersion && toVersion && fromVersion !== toVersion),
  })

  const diff = data as Record<string, unknown> | undefined
  const activeDiffId = String(diff?.diff_id ?? diffId ?? '')
  const { data: detailData } = useQuery({
    queryKey: ['schedules', 'diff-details', projectKey, activeDiffId, severity, domain, attentionOnly, activitySearch],
    queryFn: () =>
      api.getScheduleDiffDetails(projectKey, activeDiffId, {
        severity: severity || undefined,
        changeDomain: domain || undefined,
        requiresAttention: attentionOnly ? true : undefined,
        activityId: activitySearch || undefined,
        limit: 100,
      }),
    enabled: Boolean(projectKey && activeDiffId),
  })
  const detailPayload =
    detailData && typeof detailData === 'object' ? (detailData as Record<string, unknown>) : {}
  const metadata =
    detailPayload.metadata && typeof detailPayload.metadata === 'object'
      ? (detailPayload.metadata as Record<string, unknown>)
      : {}
  const counts =
    detailPayload.summary_counts && typeof detailPayload.summary_counts === 'object'
      ? (detailPayload.summary_counts as Record<string, unknown>)
      : (diff?.detail_summary_counts as Record<string, unknown> | undefined) ?? {}
  const detailRows = Array.isArray(detailPayload.detail_rows)
    ? (detailPayload.detail_rows as Record<string, unknown>[])
    : Array.isArray(diff?.detail_preview)
      ? (diff.detail_preview as Record<string, unknown>[])
      : []
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
        <ScheduleProjectPicker value={projectKey} onChange={setProjectKey} />
        <label className="block">
          <span className="text-[var(--hb-muted)]">From version</span>
          <select
            className="mt-1 block w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5"
            value={fromVersion}
            onChange={(e) => {
              setFromVersion(e.target.value)
              setDiffId('')
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
              setDiffId('')
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
            const params = new URLSearchParams(searchParams)
            params.set('project', projectKey)
            params.set('from', fromVersion)
            params.set('to', toVersion)
            params.delete('diff_id')
            setSearchParams(params, { replace: true })
            void refetch()
          }}
        >
          Compare versions
        </ScheduleActionButton>
      </div>

      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Computing diff…</p> : null}
      {error ? <EmptyState title="Could not compute version diff" /> : null}

      {(diff && runDiff) || activeDiffId ? (
        <div className="forecast-panel p-4 space-y-2 text-sm mt-3">
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded border border-[var(--hb-border)] px-2 py-1">
              {metadata.identity_safe || diff?.identity_safe ? 'Identity-safe' : 'Manual / cross-identity'}
            </span>
            <span className="rounded border border-[var(--hb-border)] px-2 py-1">
              {String(metadata.comparison_type ?? diff?.comparison_type ?? 'manual')}
            </span>
          </div>
          <p>
            <strong>Activities added:</strong> {String(diff?.activity_added_count ?? counts.added_activity_count ?? 0)} ·{' '}
            <strong>removed:</strong> {String(diff?.activity_removed_count ?? counts.removed_activity_count ?? 0)} ·{' '}
            <strong>changed:</strong> {String(diff?.activity_changed_count ?? counts.changed_activity_count ?? 0)}
          </p>
          <p>
            <strong>Relationships added:</strong> {String(diff?.relationship_added_count ?? counts.relationship_added_count ?? 0)} ·{' '}
            <strong>removed:</strong> {String(diff?.relationship_removed_count ?? counts.relationship_removed_count ?? 0)} ·{' '}
            <strong>logic churn:</strong> {String(diff?.logic_churn_rate ?? '—')}
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
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 pt-2">
            {[
              ['Critical', counts.critical_severity_count],
              ['Major', counts.major_severity_count],
              ['Moderate', counts.moderate_severity_count],
              ['Date drift', counts.date_drift_count],
              ['Attention', counts.requires_attention_count],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded border border-[var(--hb-border)] p-2">
                <div className="text-xs text-[var(--hb-muted)]">{String(label)}</div>
                <div className="text-lg font-semibold">{String(value ?? 0)}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {activeDiffId ? (
        <div className="forecast-panel p-4 space-y-3 text-sm mt-3">
          <div className="flex flex-wrap gap-3 items-end">
            <label className="block">
              <span className="text-[var(--hb-muted)]">Severity</span>
              <select className="mt-1 block rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5" value={severity} onChange={(e) => setSeverity(e.target.value)}>
                <option value="">All</option>
                <option value="critical">Critical</option>
                <option value="major">Major</option>
                <option value="moderate">Moderate</option>
                <option value="minor">Minor</option>
                <option value="informational">Informational</option>
              </select>
            </label>
            <label className="block">
              <span className="text-[var(--hb-muted)]">Domain</span>
              <select className="mt-1 block rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5" value={domain} onChange={(e) => setDomain(e.target.value)}>
                <option value="">All</option>
                <option value="activity">Activity</option>
                <option value="relationship">Relationship</option>
                <option value="wbs">WBS</option>
                <option value="calendar">Calendar</option>
                <option value="activity_code">Activity code</option>
                <option value="udf">UDF</option>
              </select>
            </label>
            <label className="block">
              <span className="text-[var(--hb-muted)]">Activity</span>
              <input className="mt-1 block rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5" value={activitySearch} onChange={(e) => setActivitySearch(e.target.value)} />
            </label>
            <label className="flex items-center gap-2 pb-1">
              <input type="checkbox" checked={attentionOnly} onChange={(e) => setAttentionOnly(e.target.checked)} />
              Requires attention
            </label>
          </div>
          <ScheduleTable
            headers={
              <>
                <ScheduleTh>Severity</ScheduleTh>
                <ScheduleTh>Domain</ScheduleTh>
                <ScheduleTh>Change</ScheduleTh>
                <ScheduleTh>Activity</ScheduleTh>
                <ScheduleTh>WBS</ScheduleTh>
                <ScheduleTh>Field</ScheduleTh>
                <ScheduleTh>From</ScheduleTh>
                <ScheduleTh>To</ScheduleTh>
                <ScheduleTh>Delta</ScheduleTh>
                <ScheduleTh>Attention</ScheduleTh>
              </>
            }
          >
            {detailRows.map((row) => (
              <tr key={String(row.detail_id)}>
                <ScheduleTd>{String(row.severity ?? 'informational')}</ScheduleTd>
                <ScheduleTd>{String(row.change_domain ?? '—')}</ScheduleTd>
                <ScheduleTd>{String(row.change_type ?? '—')}</ScheduleTd>
                <ScheduleTd>
                  <div className="font-mono text-xs">{String(row.activity_id ?? '—')}</div>
                  <div className="text-xs text-[var(--hb-muted)]">{String(row.activity_name ?? '')}</div>
                </ScheduleTd>
                <ScheduleTd>{String(row.wbs_code ?? row.wbs_name ?? '—')}</ScheduleTd>
                <ScheduleTd>{String(row.field_name ?? '—')}</ScheduleTd>
                <ScheduleTd>{String(row.from_value ?? '—')}</ScheduleTd>
                <ScheduleTd>{String(row.to_value ?? '—')}</ScheduleTd>
                <ScheduleTd>{String(row.day_delta ?? row.numeric_delta ?? '—')}</ScheduleTd>
                <ScheduleTd>{row.requires_attention ? 'Yes' : 'No'}</ScheduleTd>
              </tr>
            ))}
          </ScheduleTable>
        </div>
      ) : null}
    </ScheduleShell>
  )
}
