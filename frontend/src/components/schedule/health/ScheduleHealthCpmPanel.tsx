// Computed CPM Intelligence section (Phase 9A.3 — rich render). Surfaces the 9A.1
// computed_cpm_health envelope: run-chain status, computed activity counts, the computed longest
// path, the DCMA critical-path metric availability/measurability, and any caveats (notably
// computed_critical_outside_longest_path, which is never suppressed). Every value is
// Application-computed CPM (evidence_class application_computed_cpm) and is kept distinct from the
// source-export critical-path/float evidence rendered elsewhere on Schedule Health. Read-only.

import { Link } from 'react-router-dom'

import type { ComputedCpmHealth } from '../../../lib/api'
import { numberText } from './healthShared'
import { HealthCard } from './healthCards'
import { ScheduleHealthProvenanceBadge } from './ScheduleHealthProvenanceBadge'

const RUN_KINDS: { key: string; label: string }[] = [
  { key: 'graph_diagnostics', label: 'Graph' },
  { key: 'forward_pass', label: 'Forward' },
  { key: 'backward_pass', label: 'Backward' },
  { key: 'float', label: 'Float' },
  { key: 'longest_path', label: 'Longest path' },
  { key: 'criticality', label: 'Criticality' },
]

// Human-readable copy for DCMA caveats carried verbatim from the computed evaluator. Unknown codes
// fall back to a de-underscored rendering so a new caveat is still surfaced, never hidden.
const CAVEAT_LABELS: Record<string, string> = {
  computed_critical_outside_longest_path:
    'Computed-critical activities exist outside the longest path (parallel critical chains).',
}

function caveatLabel(code: string): string {
  return CAVEAT_LABELS[code] ?? code.replaceAll('_', ' ')
}

export function ScheduleHealthCpmPanel({
  data,
  versionKey,
}: {
  data?: ComputedCpmHealth | null
  versionKey: string
}) {
  const cpmLink = data?.links?.computed_cpm ?? `/schedules/cpm?version=${encodeURIComponent(versionKey)}`
  const available = Boolean(data?.available)
  const runChain = data?.run_chain ?? {}
  const counts = data?.counts ?? {}
  const longestPath = data?.longest_path_summary
  const dcma = data?.dcma_critical_path_metric
  const caveats = dcma?.caveats ?? []

  return (
    <section className="forecast-panel p-4">
      <div className="flex items-center justify-between mb-2 gap-3">
        <h2 className="text-sm font-semibold">Computed CPM Intelligence</h2>
        <ScheduleHealthProvenanceBadge basis="application_computed_cpm" />
      </div>
      {!available ? (
        <div className="space-y-2 text-sm text-[var(--hb-muted)]">
          <p>No application-computed CPM is available for this schedule version yet.</p>
          <Link className="inline-flex text-sm underline" to={cpmLink}>
            Open Computed CPM
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-[var(--hb-muted)]">
            Application-computed CPM (evidence_class application_computed_cpm). Distinct from the
            source-export critical-path and float evidence reported separately on this page.
          </p>

          <div className="flex flex-wrap gap-2">
            {RUN_KINDS.map((kind) => {
              const ok = Boolean(runChain[kind.key]?.available)
              return (
                <span
                  key={kind.key}
                  className={`inline-flex items-center rounded border px-2 py-0.5 text-xs ${
                    ok
                      ? 'border-emerald-300 text-emerald-700'
                      : 'border-[var(--hb-border)] text-[var(--hb-muted)]'
                  }`}
                >
                  {kind.label}: {ok ? 'available' : 'missing'}
                </span>
              )
            })}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
            <HealthCard
              title="Computed activities"
              value={numberText(counts.computed_activity_count, '—')}
              status="available"
            />
            <HealthCard
              title="Computed critical"
              value={numberText(counts.computed_critical_activity_count, '—')}
              detail={
                counts.critical_float_threshold_days != null
                  ? `Total float ≤ ${numberText(counts.critical_float_threshold_days)} d`
                  : undefined
              }
              status="available"
            />
            <HealthCard
              title="Computed near-critical"
              value={numberText(counts.computed_near_critical_activity_count, '—')}
              detail={
                counts.near_critical_float_threshold_days != null
                  ? `Float ≤ ${numberText(counts.near_critical_float_threshold_days)} d`
                  : undefined
              }
              status="available"
            />
            <HealthCard
              title="Computed noncritical"
              value={numberText(counts.computed_noncritical_activity_count, '—')}
              status="available"
            />
            <HealthCard
              title="Longest path members"
              value={numberText(counts.longest_path_member_count ?? longestPath?.activity_count, '—')}
              status="available"
            />
          </div>

          <div className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-1">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">
              Computed longest path
            </h3>
            {longestPath?.available ? (
              <>
                <p>
                  Start → End: {numberText(longestPath.start_activity_id, '—')} →{' '}
                  {numberText(longestPath.end_activity_id, '—')}
                </p>
                <p>
                  Members: {numberText(longestPath.activity_count, '—')} | Duration:{' '}
                  {numberText(longestPath.path_duration, '—')} d | Path total float:{' '}
                  {numberText(longestPath.path_total_float, '—')} d
                </p>
              </>
            ) : (
              <p className="text-[var(--hb-muted)]">Computed longest path is not available.</p>
            )}
          </div>

          <div className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-1">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">
              DCMA critical-path metric
            </h3>
            <p>
              Availability: {dcma?.available ? 'Available' : 'Unavailable'} | Measurability:{' '}
              {dcma?.measurable ? 'Measurable' : 'Not measurable'}
            </p>
            {caveats.length > 0 ? (
              <ul className="mt-1 space-y-1">
                {caveats.map((code) => (
                  <li key={code} className="text-xs text-amber-700" title={code}>
                    {caveatLabel(code)}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          <Link className="inline-flex text-sm underline" to={cpmLink}>
            View Computed CPM
          </Link>
        </div>
      )}
    </section>
  )
}
