// Version-comparison readiness section (Phase 9A.2): "What Changed Since the Prior Schedule?".
// Identity-safe diff evidence only — no PM-facing causation/narrative (that is a later phase).
// Extracted verbatim; behavior unchanged.

import { Link } from 'react-router-dom'

import { ScheduleTable, ScheduleTd, ScheduleTh } from '../SchedulePageChrome'
import type { ScheduleHealthData } from '../../../lib/api'
import { capabilityStatusLabel, labelize, statusClass, text, type HealthModel } from './healthShared'
import { ScheduleHealthProvenanceBadge } from './ScheduleHealthProvenanceBadge'

export function ScheduleHealthVersionComparisonPanel({
  model,
  health,
  projectKey,
}: {
  model: HealthModel
  health: ScheduleHealthData
  projectKey: string
}) {
  const { comparisonBasis, comparisonIdentitySafe, diffFacts } = model

  return (
    <section className="forecast-panel p-4">
      <div className="flex items-center justify-between mb-2 gap-3">
        <h2 className="text-sm font-semibold">What Changed Since the Prior Schedule?</h2>
        <ScheduleHealthProvenanceBadge basis="identity_safe_version_diff" />
      </div>
      <div className="mb-3 rounded border border-[var(--hb-border)] p-3 text-sm">
        <div className="font-medium">
          {comparisonIdentitySafe ? 'Identity-safe comparison' : 'Default comparison unavailable'}
        </div>
        <div className="text-xs text-[var(--hb-muted)] mt-1">
          Current identity: {text(comparisonBasis.current_schedule_identity_key)} · Prior identity:{' '}
          {text(comparisonBasis.default_prior_schedule_identity_key)} · Reason:{' '}
          {text(comparisonBasis.default_prior_selection_reason ?? comparisonBasis.default_prior_unavailable_reason)}
        </div>
        {comparisonIdentitySafe && comparisonBasis.detailed_diff_id ? (
          <Link
            className="inline-flex text-sm underline mt-2"
            to={`/schedules/version-diff?project=${encodeURIComponent(String(health.project_key ?? projectKey))}&diff_id=${encodeURIComponent(String(comparisonBasis.detailed_diff_id))}`}
          >
            View detailed diff
          </Link>
        ) : null}
      </div>
      {diffFacts.length === 0 ? (
        <p className="text-sm text-[var(--hb-muted)]">
          No persisted prior-version diff is available. A schedule version only participates in default comparison
          when identity review is resolved and a prior committed version shares the same schedule identity.
        </p>
      ) : (
        <ScheduleTable
          headers={
            <>
              <ScheduleTh>Metric</ScheduleTh>
              <ScheduleTh>Value</ScheduleTh>
              <ScheduleTh>Status</ScheduleTh>
              <ScheduleTh>Basis</ScheduleTh>
            </>
          }
        >
          {diffFacts.slice(0, 12).map((fact, index) => (
            <tr key={String(fact.fact_id ?? fact.metric_key ?? index)}>
              <ScheduleTd>{labelize(fact.metric_key ?? fact.fact_key)}</ScheduleTd>
              <ScheduleTd>{text(fact.metric_value ?? fact.value)}</ScheduleTd>
              <ScheduleTd className={statusClass(String(fact.status))}>{capabilityStatusLabel(fact.status)}</ScheduleTd>
              <ScheduleTd>{labelize(fact.basis)}</ScheduleTd>
            </tr>
          ))}
        </ScheduleTable>
      )}
    </section>
  )
}
