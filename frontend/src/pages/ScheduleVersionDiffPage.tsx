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
  const [wbsFilter, setWbsFilter] = useState('')
  const [runDiff, setRunDiff] = useState(Boolean(searchParams.get('diff_id')))

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['schedules', 'diff', projectKey, fromVersion, toVersion],
    queryFn: () => api.getScheduleVersionDiff(projectKey, fromVersion, toVersion),
    enabled: runDiff && Boolean(fromVersion && toVersion && fromVersion !== toVersion),
  })

  const diff = data as Record<string, unknown> | undefined
  const activeDiffId = String(diff?.diff_id ?? diffId ?? '')
  const { data: detailData } = useQuery({
    queryKey: ['schedules', 'diff-details', projectKey, activeDiffId, severity, domain, attentionOnly, activitySearch, wbsFilter],
    queryFn: () =>
      api.getScheduleDiffDetails(projectKey, activeDiffId, {
        severity: severity || undefined,
        changeDomain: domain || undefined,
        requiresAttention: attentionOnly ? true : undefined,
        activityId: activitySearch || undefined,
        wbsCode: wbsFilter || undefined,
        limit: 100,
      }),
    enabled: Boolean(projectKey && activeDiffId),
  })
  const { data: impactData } = useQuery({
    queryKey: ['schedules', 'diff-impact', projectKey, activeDiffId],
    queryFn: () => api.getScheduleDiffImpact(projectKey, activeDiffId, { limit: 100 }),
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
  const impactPayload =
    impactData && typeof impactData === 'object' ? (impactData as Record<string, unknown>) : {}
  const impactSummary =
    impactPayload.summary && typeof impactPayload.summary === 'object'
      ? (impactPayload.summary as Record<string, unknown>)
      : (diff?.impact_summary as Record<string, unknown> | undefined) ?? {}
  const impactRollups = Array.isArray(impactPayload.rollups)
    ? (impactPayload.rollups as Record<string, unknown>[])
    : []
  const topWbs =
    impactPayload.top_wbs && typeof impactPayload.top_wbs === 'object'
      ? (impactPayload.top_wbs as Record<string, unknown>)
      : (diff?.impact_top_wbs as Record<string, unknown> | undefined) ?? {}
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

      {activeDiffId && Object.keys(impactSummary).length > 0 ? (
        <div className="forecast-panel p-4 space-y-4 text-sm mt-3">
          <div>
            <h2 className="text-base font-semibold">Impact summary</h2>
            <p className="text-xs text-[var(--hb-muted)]">
              Read-only rollups generated from persisted detailed diff facts.
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {[
              ['Impact', impactSummary.impact_level ?? 'informational'],
              ['Score', impactSummary.impact_score ?? '0'],
              ['Attention', impactSummary.requires_attention_count ?? 0],
              ['Critical', impactSummary.critical_count ?? 0],
              ['Max later', impactSummary.max_later_day_delta ?? '—'],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded border border-[var(--hb-border)] p-2">
                <div className="text-xs text-[var(--hb-muted)]">{String(label)}</div>
                <div className="text-lg font-semibold">{String(value)}</div>
              </div>
            ))}
          </div>
          {topWbs.rollup_label ? (
            <p>
              <strong>Top WBS impact:</strong> {String(topWbs.rollup_label)} ·{' '}
              {String(topWbs.impact_level ?? 'informational')} · score{' '}
              {String(topWbs.impact_score ?? '0')}
            </p>
          ) : null}
          <ImpactRollupTable
            title="WBS impact"
            rows={impactRollups.filter((row) => row.rollup_type === 'wbs').slice(0, 8)}
            onSelect={(row) => {
              setWbsFilter(String(row.wbs_code ?? ''))
              setActivitySearch('')
            }}
          />
          <ImpactRollupTable
            title="Attention-required rollups"
            rows={impactRollups.filter((row) => row.rollup_type === 'attention').slice(0, 8)}
            onSelect={(row) => {
              setSeverity(String(row.rollup_key ?? '').split('|')[0] || '')
              setAttentionOnly(true)
            }}
          />
          <ImpactRollupTable
            title="Milestone impact"
            rows={impactRollups.filter((row) => row.rollup_type === 'milestone').slice(0, 8)}
            onSelect={(row) => setActivitySearch(String(row.milestone_activity_id ?? row.activity_id ?? ''))}
            emptyLabel="No explicit milestone impact facts"
          />
          <ImpactRollupTable
            title="Critical and near-critical impact"
            rows={impactRollups.filter((row) => row.rollup_type === 'critical_path' || row.rollup_type === 'near_critical').slice(0, 8)}
            onSelect={(row) => setActivitySearch(String(row.activity_id ?? ''))}
            emptyLabel="No persisted critical or near-critical impact facts"
          />
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
            <label className="block">
              <span className="text-[var(--hb-muted)]">WBS</span>
              <input className="mt-1 block rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5" value={wbsFilter} onChange={(e) => setWbsFilter(e.target.value)} />
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

function ImpactRollupTable({
  title,
  rows,
  onSelect,
  emptyLabel = 'No rollups',
}: {
  title: string
  rows: Record<string, unknown>[]
  onSelect: (row: Record<string, unknown>) => void
  emptyLabel?: string
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-xs text-[var(--hb-muted)]">{emptyLabel}</p>
      ) : (
        <ScheduleTable
          headers={
            <>
              <ScheduleTh>Impact</ScheduleTh>
              <ScheduleTh>Area</ScheduleTh>
              <ScheduleTh>Changes</ScheduleTh>
              <ScheduleTh>Severity</ScheduleTh>
              <ScheduleTh>Date drift</ScheduleTh>
              <ScheduleTh>Logic</ScheduleTh>
              <ScheduleTh>Attention</ScheduleTh>
              <ScheduleTh>Max delta</ScheduleTh>
            </>
          }
        >
          {rows.map((row) => (
            <tr
              key={String(row.rollup_id)}
              className="cursor-pointer hover:bg-[var(--hb-bg)]"
              onClick={() => onSelect(row)}
            >
              <ScheduleTd>
                <div className="font-semibold">{String(row.impact_level ?? 'informational')}</div>
                <div className="text-xs text-[var(--hb-muted)]">score {String(row.impact_score ?? '0')}</div>
              </ScheduleTd>
              <ScheduleTd>{String(row.rollup_label ?? row.rollup_key ?? '—')}</ScheduleTd>
              <ScheduleTd>{String(row.change_count ?? 0)}</ScheduleTd>
              <ScheduleTd>
                C {String(row.critical_count ?? 0)} · Mj {String(row.major_count ?? 0)} · Md{' '}
                {String(row.moderate_count ?? 0)}
              </ScheduleTd>
              <ScheduleTd>{String(row.date_drift_count ?? 0)}</ScheduleTd>
              <ScheduleTd>{String(row.logic_change_count ?? row.relationship_change_count ?? 0)}</ScheduleTd>
              <ScheduleTd>{String(row.requires_attention_count ?? 0)}</ScheduleTd>
              <ScheduleTd>{String(row.max_day_delta ?? '—')}</ScheduleTd>
            </tr>
          ))}
        </ScheduleTable>
      )}
    </div>
  )
}
