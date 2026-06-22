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
} from '../components/schedule/ScheduleProjectPicker'
import { EmptyState } from '../components/ui/EmptyState'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

export function ScheduleCostWeightingPage() {
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const { data, isLoading, error } = useQuery({
    queryKey: ['schedules', 'weighting', projectKey],
    queryFn: () => api.getScheduleCostWeighting(projectKey),
  })

  const results = Array.isArray((data as { weighting_results?: unknown[] })?.weighting_results)
    ? (data as { weighting_results: Record<string, unknown>[] }).weighting_results
    : []

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Cost weighting"
        subtitle="Approved schedule-to-cost weighting outputs. Entries appear only after operator-approved mapping runs."
      />

      <div className="forecast-panel p-4 mb-3 max-w-md">
        <ScheduleProjectPicker value={projectKey} onChange={setProjectKey} />
      </div>

      <p className="text-sm text-[var(--hb-muted)] mb-3">
        Weighting is gated: unapproved mapping runs cannot feed downstream forecast weighting.
      </p>

      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading weighting…</p> : null}
      {error ? <EmptyState title="Could not load weighting results" /> : null}
      {!isLoading && results.length === 0 ? (
        <EmptyState
          title="No approved weighting yet"
          hint="Complete a cost mapping run and approve it to populate weighting."
        />
      ) : null}

      {results.length > 0 ? (
        <ScheduleTable
          headers={
            <>
              <ScheduleTh>Activity</ScheduleTh>
              <ScheduleTh>Cost code</ScheduleTh>
              <ScheduleTh>Weight</ScheduleTh>
              <ScheduleTh>Approved</ScheduleTh>
            </>
          }
        >
          {results.map((r, i) => (
            <tr key={i}>
              <ScheduleTd>{String(r.activity_id ?? '')}</ScheduleTd>
              <ScheduleTd>{String(r.cost_code ?? r.candidate_cost_code ?? '')}</ScheduleTd>
              <ScheduleTd>{String(r.weight_value ?? r.allocation_percent ?? '')}</ScheduleTd>
              <ScheduleTd>{String(r.operator_approved ?? r.approved ?? '')}</ScheduleTd>
            </tr>
          ))}
        </ScheduleTable>
      ) : null}
    </ScheduleShell>
  )
}