import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { useState } from 'react'

import {
  ScheduleBackLink,
  SchedulePageHeader,
  SchedulePanel,
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
import { ScheduleVersionPicker } from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'
import {
  api,
  type ScheduleCpmActivity,
  type ScheduleCpmDcmaEvidence,
  type ScheduleCpmRunEntry,
  type ScheduleCpmSummary,
} from '../lib/api'

const RUN_KINDS: { key: string; label: string }[] = [
  { key: 'graph_diagnostics', label: 'Graph diagnostics' },
  { key: 'forward_pass', label: 'Forward pass' },
  { key: 'backward_pass', label: 'Backward pass' },
  { key: 'float', label: 'Float' },
  { key: 'longest_path', label: 'Longest path' },
  { key: 'criticality', label: 'Criticality' },
]

function statusClass(available: boolean): string {
  return available ? 'text-emerald-600' : 'text-[var(--hb-muted)]'
}

function StatusPill({ available, text }: { available: boolean; text: string }) {
  return <span className={`text-xs font-medium ${statusClass(available)}`}>{text}</span>
}

function num(value: unknown): string {
  return value == null || value === '' ? '—' : String(value)
}

function RunChainCard({ summary }: { summary: ScheduleCpmSummary }) {
  return (
    <SchedulePanel title="CPM run chain">
      <p className="text-xs text-[var(--hb-muted)] mb-2">
        Application-computed CPM; source-export evidence is shown separately on Schedule Health.
      </p>
      <ul className="space-y-1 text-sm">
        {RUN_KINDS.map(({ key, label }) => {
          const run: ScheduleCpmRunEntry | undefined = summary.runs?.[key]
          const available = Boolean(run?.available)
          return (
            <li key={key} className="flex items-center justify-between gap-3">
              <span>{label}</span>
              <StatusPill
                available={available}
                text={available ? String(run?.cpm_recalculation_status ?? 'available') : 'Not run'}
              />
            </li>
          )
        })}
      </ul>
      {summary.missing_dependency_reasons?.length ? (
        <p className="mt-2 text-xs text-amber-600">
          Missing: {summary.missing_dependency_reasons.join(', ')}
        </p>
      ) : null}
    </SchedulePanel>
  )
}

function DcmaEvidenceCard({ dcma }: { dcma: ScheduleCpmDcmaEvidence }) {
  const status = !dcma.available
    ? 'Not measurable until CPM calculation chain is available'
    : dcma.measurable
      ? 'Application-computed CPM available'
      : 'Attempted — not measurable'
  return (
    <SchedulePanel title="DCMA critical-path metric">
      <div className="text-sm">
        <div className="font-medium">{status}</div>
        <div className="mt-1 text-xs text-[var(--hb-muted)]">
          Basis: {dcma.basis ?? (dcma.available ? 'application_computed_cpm (attempted)' : 'source-export evidence')}
        </div>
        <p className="mt-2 text-xs text-[var(--hb-muted)]">
          DCMA critical-path metric is based on application-computed CPM evidence. Source critical
          flags used: {String(dcma.source_critical_flags_used ?? false)}.
        </p>
        {dcma.reason_codes?.length ? (
          <p className="mt-1 text-xs text-amber-600">Reasons: {dcma.reason_codes.join(', ')}</p>
        ) : null}
        {dcma.caveats?.length ? (
          <p className="mt-1 text-xs text-[var(--hb-muted)]">Caveats: {dcma.caveats.join(', ')}</p>
        ) : null}
        {dcma.dependency_run_ids ? (
          <p className="mt-1 text-[10px] text-[var(--hb-muted)] break-all">
            Dependency runs: {Object.entries(dcma.dependency_run_ids)
              .map(([k, v]) => `${k}=${v ?? '—'}`)
              .join('  ')}
          </p>
        ) : null}
      </div>
    </SchedulePanel>
  )
}

function LongestPathPanel({ versionKey }: { versionKey: string }) {
  const { data } = useQuery({
    queryKey: ['schedules', 'cpm-longest-path', versionKey],
    queryFn: () => api.getScheduleCpmLongestPath(versionKey),
    enabled: Boolean(versionKey),
  })
  if (!data) return null
  if (!data.available) {
    return (
      <SchedulePanel title="Longest path">
        <EmptyState title="No longest path computed" hint={data.reason} />
      </SchedulePanel>
    )
  }
  const path = (data.path ?? {}) as Record<string, unknown>
  return (
    <SchedulePanel title="Longest path">
      <p className="text-xs text-[var(--hb-muted)] mb-2">
        Longest path (not a critical-path declaration). Start {num(path.start_activity_id)} →
        end {num(path.end_activity_id)}; {num(path.activity_count)} activities; duration{' '}
        {num(path.path_duration)}.
      </p>
      <ScheduleTable
        headers={
          <>
            <ScheduleTh>Seq</ScheduleTh>
            <ScheduleTh>Activity</ScheduleTh>
            <ScheduleTh>Name</ScheduleTh>
            <ScheduleTh>Early start</ScheduleTh>
            <ScheduleTh>Early finish</ScheduleTh>
            <ScheduleTh>Total float</ScheduleTh>
            <ScheduleTh>Criticality</ScheduleTh>
          </>
        }
      >
        {data.activities.map((a: ScheduleCpmActivity, i: number) => (
          <tr key={`${a.activity_id}-${i}`}>
            <ScheduleTd>{num(a.longest_path_sequence)}</ScheduleTd>
            <ScheduleTd>{num(a.activity_id)}</ScheduleTd>
            <ScheduleTd>{num(a.activity_name)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_early_start)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_early_finish)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_total_float)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_criticality_class)}</ScheduleTd>
          </tr>
        ))}
      </ScheduleTable>
    </SchedulePanel>
  )
}

function ActivityTable({ versionKey }: { versionKey: string }) {
  const { data } = useQuery({
    queryKey: ['schedules', 'cpm-activities', versionKey],
    queryFn: () => api.getScheduleCpmActivities(versionKey, { limit: 1000 }),
    enabled: Boolean(versionKey),
  })
  if (!data) return null
  if (!data.available) {
    return (
      <SchedulePanel title="Computed activities">
        <EmptyState title="No computed CPM activities" hint={data.reason} />
      </SchedulePanel>
    )
  }
  return (
    <SchedulePanel title="Computed activities">
      <p className="text-xs text-[var(--hb-muted)] mb-2">
        Source run: {num(data.source_run?.calculation_type)} — application-computed fields only.
      </p>
      <ScheduleTable
        headers={
          <>
            <ScheduleTh>Activity</ScheduleTh>
            <ScheduleTh>Name</ScheduleTh>
            <ScheduleTh>ES</ScheduleTh>
            <ScheduleTh>EF</ScheduleTh>
            <ScheduleTh>LS</ScheduleTh>
            <ScheduleTh>LF</ScheduleTh>
            <ScheduleTh>Total float</ScheduleTh>
            <ScheduleTh>Free float</ScheduleTh>
            <ScheduleTh>Criticality</ScheduleTh>
            <ScheduleTh>Longest path</ScheduleTh>
          </>
        }
      >
        {data.activities.map((a: ScheduleCpmActivity, i: number) => (
          <tr key={`${a.activity_id}-${i}`}>
            <ScheduleTd>{num(a.activity_id)}</ScheduleTd>
            <ScheduleTd>{num(a.activity_name)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_early_start)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_early_finish)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_late_start)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_late_finish)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_total_float)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_free_float)}</ScheduleTd>
            <ScheduleTd>{num(a.computed_criticality_class)}</ScheduleTd>
            <ScheduleTd>{a.longest_path_member_flag ? 'Yes' : '—'}</ScheduleTd>
          </tr>
        ))}
      </ScheduleTable>
    </SchedulePanel>
  )
}

export function ScheduleCpmPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const [versionKey, setVersionKey] = useState(searchParams.get('version') || '')

  const { data: summary, isLoading, error } = useQuery({
    queryKey: ['schedules', 'cpm-summary', versionKey],
    queryFn: () => api.getScheduleCpmSummary(versionKey),
    enabled: Boolean(versionKey),
  })

  function onProjectChange(next: string) {
    setProjectKey(next)
    setVersionKey('')
    const params = new URLSearchParams(searchParams)
    if (next) params.set('project', next)
    else params.delete('project')
    params.delete('version')
    setSearchParams(params, { replace: true })
  }

  function onVersionChange(next: string) {
    setVersionKey(next)
    const params = new URLSearchParams(searchParams)
    if (next) {
      params.set('version', next)
      const inferred = next.split('|')[0]
      if (inferred) params.set('project', inferred)
    } else {
      params.delete('version')
    }
    setSearchParams(params, { replace: true })
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Computed CPM"
        subtitle="Application-computed CPM chain, longest path, computed criticality, and DCMA critical-path metric evidence (read-only)."
      />

      <div className="forecast-panel p-4 mb-3 max-w-5xl flex flex-wrap gap-3 items-end">
        <ScheduleProjectPicker value={projectKey} onChange={onProjectChange} className="min-w-[16rem]" />
        <ScheduleVersionPicker projectKey={projectKey} value={versionKey} onChange={onVersionChange} />
      </div>

      {!versionKey ? (
        <EmptyState title="Select a schedule version" hint="Choose a project and version to view computed CPM analysis." />
      ) : isLoading ? (
        <EmptyState title="Loading computed CPM…" />
      ) : error ? (
        <EmptyState title="Could not load computed CPM" hint="The CPM analysis request failed. Try again." />
      ) : !summary || !summary.available ? (
        <EmptyState
          title="No computed CPM yet"
          hint="Not measurable until CPM calculation chain is available. Source-export evidence remains on Schedule Health."
        />
      ) : (
        <div className="space-y-3 max-w-5xl">
          <div className="grid gap-3 md:grid-cols-2">
            <RunChainCard summary={summary} />
            <DcmaEvidenceCard dcma={summary.dcma_critical_path} />
          </div>
          <LongestPathPanel versionKey={versionKey} />
          <ActivityTable versionKey={versionKey} />
          <p className="text-xs text-[var(--hb-muted)]">
            Source-export evidence is shown separately on the Schedule Health page and is not
            reinterpreted here as application-computed CPM.
          </p>
        </div>
      )}
    </ScheduleShell>
  )
}
