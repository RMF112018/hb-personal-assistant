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
import { DEFAULT_SCHEDULE_PROJECT, useScheduleVersions } from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'

export function ScheduleVersionsPage() {
  const projectKey = DEFAULT_SCHEDULE_PROJECT
  const { data, isLoading, error } = useScheduleVersions(projectKey)
  const versions = Array.isArray(data) ? data : []

  return (
    <ScheduleShell>
      <ScheduleBackLink to="/schedules/imports" label="Schedule Intelligence" />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule versions"
        subtitle="Committed schedule versions stored in the local database."
      />

      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading versions…</p> : null}
      {error ? <EmptyState title="Could not load schedule versions" /> : null}

      {!isLoading && versions.length === 0 ? (
        <EmptyState title="No schedule versions yet" hint="Import a schedule to create the first version." />
      ) : null}

      {versions.length > 0 ? (
        <ScheduleTable
          headers={
            <>
              <ScheduleTh>Version</ScheduleTh>
              <ScheduleTh>Data date</ScheduleTh>
              <ScheduleTh>Source</ScheduleTh>
              <ScheduleTh>Activities</ScheduleTh>
              <ScheduleTh>Quality</ScheduleTh>
              <ScheduleTh>Cost loaded</ScheduleTh>
              <ScheduleTh />
            </>
          }
        >
          {versions.map((v: Record<string, unknown>) => {
            const svk = String(v.schedule_version_key)
            const actLink = `/schedules/activities?version=${encodeURIComponent(svk)}`
            return (
              <tr key={svk}>
                <ScheduleTd>{String(v.display_label)}</ScheduleTd>
                <ScheduleTd>{String(v.data_date ?? '—')}</ScheduleTd>
                <ScheduleTd>{String(v.source_format)}</ScheduleTd>
                <ScheduleTd>{String(v.activity_count)}</ScheduleTd>
                <ScheduleTd>{String(v.quality_finding_count ?? 0)}</ScheduleTd>
                <ScheduleTd>{String(v.cost_loaded_status)}</ScheduleTd>
                <ScheduleTd>
                  <div className="flex flex-wrap gap-2 text-sm">
                    <Link className="underline" to={actLink}>
                      Activities
                    </Link>
                    <Link className="underline" to={`/schedules/quality?version=${encodeURIComponent(svk)}`}>
                      Quality
                    </Link>
                    <Link className="underline" to="/schedules/cost-mapping">
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