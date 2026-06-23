import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
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
  useScheduleProjects,
} from '../components/schedule/ScheduleProjectPicker'
import { useScheduleVersions } from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'

const SORT_OPTIONS = [
  { value: 'imported_at', label: 'Import date' },
  { value: 'data_date', label: 'Data date' },
  { value: 'project_key', label: 'Project' },
  { value: 'source_format', label: 'Source format' },
  { value: 'quality_score', label: 'Quality score' },
  { value: 'quality_grade', label: 'Quality grade' },
  { value: 'completion_posture', label: 'Completion posture' },
  { value: 'quality_status', label: 'Evaluation status' },
] as const

export function ScheduleVersionsPage() {
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const [sort, setSort] = useState<string>('imported_at')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const { data: projectsData } = useScheduleProjects()
  const { data, isLoading, error } = useScheduleVersions(projectKey || undefined)
  const versions = useMemo(() => {
    const rows = Array.isArray(data) ? [...(data as Record<string, unknown>[])] : []
    const mult = order === 'asc' ? 1 : -1
    return rows.sort((a, b) => {
      const av = String(a[sort] ?? '')
      const bv = String(b[sort] ?? '')
      if (sort === 'quality_score') {
        return (Number(a.quality_score ?? 0) - Number(b.quality_score ?? 0)) * mult
      }
      return av.localeCompare(bv) * mult
    })
  }, [data, sort, order])

  function projectLabel(key: string) {
    const project = projectsData?.projects?.find((p) => p.project_key === key)
    return project?.display_name || project?.display_label || key
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink to="/schedules/imports" label="Schedule Intelligence" />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule versions"
        subtitle="Committed schedule versions stored in the local database."
      />

      <div className="forecast-panel p-4 mb-4 max-w-3xl flex flex-wrap gap-3 items-end">
        <ScheduleProjectPicker
          value={projectKey}
          onChange={setProjectKey}
          allowAll
          className="min-w-[16rem]"
        />
        <label className="block text-sm">
          <span className="text-[var(--hb-muted)]">Sort by</span>
          <select
            className="mt-1 block rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5 text-sm"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="text-[var(--hb-muted)]">Order</span>
          <select
            className="mt-1 block rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5 text-sm"
            value={order}
            onChange={(e) => setOrder(e.target.value as 'asc' | 'desc')}
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </label>
      </div>

      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading versions…</p> : null}
      {error ? <EmptyState title="Could not load schedule versions" /> : null}

      {!isLoading && versions.length === 0 ? (
        <EmptyState title="No schedule versions yet" hint="Import a schedule to create the first version." />
      ) : null}

      {versions.length > 0 ? (
        <ScheduleTable
          headers={
            <>
              {!projectKey ? <ScheduleTh>Project</ScheduleTh> : null}
              <ScheduleTh>Version</ScheduleTh>
              <ScheduleTh>Data date</ScheduleTh>
              <ScheduleTh>Source</ScheduleTh>
              <ScheduleTh>Imported</ScheduleTh>
              <ScheduleTh>Activities</ScheduleTh>
              <ScheduleTh>Quality</ScheduleTh>
              <ScheduleTh>Score</ScheduleTh>
              <ScheduleTh>Cost loaded</ScheduleTh>
              <ScheduleTh />
            </>
          }
        >
          {versions.map((v: Record<string, unknown>) => {
            const svk = String(v.schedule_version_key)
            const pk = String(v.project_key ?? svk.split('|')[0] ?? '')
            const actLink = `/schedules/activities?version=${encodeURIComponent(svk)}&project=${encodeURIComponent(pk)}`
            return (
              <tr key={svk}>
                {!projectKey ? (
                  <ScheduleTd>
                    <div>{projectLabel(pk)}</div>
                    <div className="text-xs text-[var(--hb-muted)] font-mono">{pk}</div>
                  </ScheduleTd>
                ) : null}
                <ScheduleTd>{String(v.display_label)}</ScheduleTd>
                <ScheduleTd>{String(v.data_date ?? '—')}</ScheduleTd>
                <ScheduleTd>{String(v.source_format)}</ScheduleTd>
                <ScheduleTd>{String(v.imported_at ?? '—')}</ScheduleTd>
                <ScheduleTd>{String(v.activity_count)}</ScheduleTd>
                <ScheduleTd>{String(v.quality_status ?? 'not_evaluated')}</ScheduleTd>
                <ScheduleTd>
                  {String(v.quality_score ?? '—')} / {String(v.quality_grade ?? '—')}
                </ScheduleTd>
                <ScheduleTd>{String(v.cost_loaded_status)}</ScheduleTd>
                <ScheduleTd>
                  <div className="flex flex-wrap gap-2 text-sm">
                    <Link className="underline" to={actLink}>
                      Activities
                    </Link>
                    <Link
                      className="underline"
                      to={`/schedules/quality?version=${encodeURIComponent(svk)}&project=${encodeURIComponent(pk)}`}
                    >
                      Quality
                    </Link>
                    <Link className="underline" to={`/schedules/cost-mapping?project=${encodeURIComponent(pk)}`}>
                      Map
                    </Link>
                  </div>
                </ScheduleTd>
              </tr>
            )
          })}
        </ScheduleTable>
      ) : null}
    </ScheduleShell>
  )
}