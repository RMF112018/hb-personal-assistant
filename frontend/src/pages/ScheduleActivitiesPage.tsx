import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

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
  DEFAULT_SCHEDULE_PROJECT,
  ScheduleVersionPicker,
} from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

const PAGE_SIZE = 500

export function ScheduleActivitiesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [versionKey, setVersionKey] = useState(searchParams.get('version') || '')
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const v = searchParams.get('version') || ''
    setVersionKey(v)
    setOffset(0)
  }, [searchParams])

  const { data, isLoading, error } = useQuery({
    queryKey: ['schedules', 'activities', versionKey, offset],
    queryFn: () => api.getScheduleActivities(versionKey, { limit: PAGE_SIZE, offset }),
    enabled: Boolean(versionKey),
  })

  const activities = Array.isArray((data as { activities?: unknown[] })?.activities)
    ? (data as { activities: Record<string, unknown>[] }).activities
    : []
  const total = Number((data as { total_count?: number })?.total_count ?? activities.length)
  const truncated = Boolean((data as { truncated?: boolean })?.truncated)

  function onVersionChange(next: string) {
    setVersionKey(next)
    setOffset(0)
    if (next) {
      setSearchParams({ version: next })
    } else {
      setSearchParams({})
    }
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule activities"
        subtitle="Activity browser for a committed schedule version."
      />

      <div className="forecast-panel p-4 mb-3 max-w-xl">
        <ScheduleVersionPicker
          projectKey={DEFAULT_SCHEDULE_PROJECT}
          value={versionKey}
          onChange={onVersionChange}
        />
      </div>

      {!versionKey ? (
        <EmptyState title="Select a schedule version" hint="Choose a version to browse activities." />
      ) : null}

      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading activities…</p> : null}
      {error ? <EmptyState title="Could not load activities" /> : null}

      {versionKey && !isLoading && activities.length === 0 ? (
        <EmptyState title="No activities for this version" />
      ) : null}

      {activities.length > 0 ? (
        <>
          <p className="text-sm text-[var(--hb-muted)] mb-2">
            Showing {offset + 1}–{offset + activities.length} of {total} activities
            {truncated ? ' (paginated)' : ''}
          </p>
          <ScheduleTable
            headers={
              <>
                <ScheduleTh>ID</ScheduleTh>
                <ScheduleTh>Name</ScheduleTh>
                <ScheduleTh>WBS</ScheduleTh>
                <ScheduleTh>Start</ScheduleTh>
                <ScheduleTh>Finish</ScheduleTh>
                <ScheduleTh>Cost code</ScheduleTh>
              </>
            }
          >
            {activities.map((a) => (
              <tr key={String(a.activity_id)}>
                <ScheduleTd>{String(a.activity_id)}</ScheduleTd>
                <ScheduleTd>{String(a.activity_name ?? '')}</ScheduleTd>
                <ScheduleTd>{String(a.wbs_code ?? '')}</ScheduleTd>
                <ScheduleTd>{String(a.start_date ?? '')}</ScheduleTd>
                <ScheduleTd>{String(a.finish_date ?? '')}</ScheduleTd>
                <ScheduleTd>{String(a.cost_code ?? '')}</ScheduleTd>
              </tr>
            ))}
          </ScheduleTable>
          <div className="flex gap-2 mt-3">
            <button
              type="button"
              className="forecast-btn-secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <button
              type="button"
              className="forecast-btn-secondary"
              disabled={!truncated && offset + activities.length >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </>
      ) : null}
    </ScheduleShell>
  )
}