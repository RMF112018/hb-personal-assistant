// Computed CPM Intelligence section (Phase 9A.2 — SHELL). Surfaces availability + run-chain
// status of the Application-computed CPM and links to the Computed CPM tab. The rich render
// (longest-path, criticality/float cards, DCMA detail) lands in Phase 9A.3.

import { Link } from 'react-router-dom'

import type { ComputedCpmHealth } from '../../../lib/api'
import { ScheduleHealthProvenanceBadge } from './ScheduleHealthProvenanceBadge'

const RUN_KINDS: { key: string; label: string }[] = [
  { key: 'graph_diagnostics', label: 'Graph' },
  { key: 'forward_pass', label: 'Forward' },
  { key: 'backward_pass', label: 'Backward' },
  { key: 'float', label: 'Float' },
  { key: 'longest_path', label: 'Longest path' },
  { key: 'criticality', label: 'Criticality' },
]

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
            Application-computed CPM run chain. Detailed computed activities, longest path, and the
            DCMA critical-path metric are on the Computed CPM tab.
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
          <Link className="inline-flex text-sm underline" to={cpmLink}>
            View Computed CPM
          </Link>
        </div>
      )}
    </section>
  )
}
