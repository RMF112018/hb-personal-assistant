/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecasting — package detail / review (Implementation Phase 1, read-only).
 * Shows a single forecast package: headline metrics, validation status, the recommended
 * final cost by cost code, and the human-review queue. Business-facing only — no paths,
 * run stamps, directory names, commands, or internals. */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'
import { StatusPill } from './ForecastingPage'

function HeadlineMetric({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded border border-[var(--hb-border)] px-3 py-2">
      <div className="text-xs text-[var(--hb-muted)]">{label}</div>
      <div className="text-lg font-medium">{value ?? '—'}</div>
    </div>
  )
}

const HEADLINE_LABELS: Record<string, string> = {
  canonical_codes_covered: 'Cost codes covered',
  integrated_final_cost_recommendations: 'Final-cost recommendations',
  integrated_monthly_rows: 'Monthly rows',
  integrated_probability_rows: 'Probability rows',
  human_review_items: 'Human-review items',
  evidence_conflicts: 'Evidence conflicts',
}

export function ForecastPackagePage() {
  const { packageId = '' } = useParams()

  const { data: summary, isLoading, error } = useQuery({
    queryKey: ['forecast', 'summary', packageId],
    queryFn: () => api.getForecastPackageSummary(packageId),
    enabled: Boolean(packageId),
  })
  const { data: validation } = useQuery({
    queryKey: ['forecast', 'validation', packageId],
    queryFn: () => api.getForecastPackageValidation(packageId),
    enabled: Boolean(packageId),
  })
  const { data: rowsResp } = useQuery({
    queryKey: ['forecast', 'rows', packageId],
    queryFn: () => api.getForecastPackageRows(packageId),
    enabled: Boolean(packageId),
  })
  const { data: reviewResp } = useQuery({
    queryKey: ['forecast', 'review', packageId],
    queryFn: () => api.getForecastPackageReviewItems(packageId),
    enabled: Boolean(packageId),
  })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading forecast package…</div>
  }

  if (error) {
    const status = (error as any)?.status
    const message =
      status === 404
        ? 'This forecast package could not be found.'
        : 'We could not load this forecast package right now.'
    return (
      <div className="card">
        <div className="text-xs mb-2">
          <Link to="/forecasting" className="underline">
            ← Back to forecast packages
          </Link>
        </div>
        <EmptyState title="Forecast package unavailable" hint={message} />
      </div>
    )
  }

  const s = summary || {}
  const headline = s.headline || {}
  const v = validation || {}
  const rows: any[] = Array.isArray(rowsResp?.rows) ? rowsResp.rows : []
  const reviewItems: any[] = Array.isArray(reviewResp?.items) ? reviewResp.items : []
  const failedChecks: string[] = Array.isArray(v.failed_checks) ? v.failed_checks : []

  return (
    <div>
      <div className="text-xs mb-2">
        <Link to="/forecasting" className="underline">
          ← Back to forecast packages
        </Link>
      </div>

      <div className="card">
        <div className="flex items-center justify-between gap-3">
          <div className="section-title">{s.display_label || 'Forecast package'}</div>
          <StatusPill status={s.status || 'unknown'} />
        </div>
        <p className="text-sm text-[var(--hb-muted)]">
          {s.project_key ? `${s.project_key}` : ''}
          {s.job_reference ? ` · Job ${s.job_reference}` : ''}
          {s.period ? ` · ${s.period}` : ''}
          {s.generated_display ? ` · Generated ${s.generated_display}` : ''}
        </p>

        {Object.keys(headline).length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-3">
            {Object.entries(HEADLINE_LABELS)
              .filter(([k]) => k in headline)
              .map(([k, label]) => (
                <HeadlineMetric key={k} label={label} value={headline[k]} />
              ))}
          </div>
        )}
      </div>

      <div className="card mt-3">
        <div className="section-title">Validation</div>
        {v.total_checks ? (
          <p className="text-sm">
            {v.passed}/{v.total_checks} checks passed.{' '}
            {v.failed > 0 ? (
              <span className="text-amber-300">{v.failed} need attention.</span>
            ) : (
              <span className="text-emerald-300">All checks passed.</span>
            )}
          </p>
        ) : (
          <p className="text-sm text-[var(--hb-muted)]">No validation report is available for this package.</p>
        )}
        {failedChecks.length > 0 && (
          <ul className="list-disc ml-5 mt-2 text-sm text-[var(--hb-muted)]">
            {failedChecks.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="card mt-3">
        <div className="section-title">Recommended final cost by cost code</div>
        {rows.length === 0 ? (
          <EmptyState
            title="No cost-code rows"
            hint="This package type does not include per-cost-code final-cost rows."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                  <th className="py-2 pr-3">Cost code</th>
                  <th className="py-2 pr-3 text-right">Recommended final cost</th>
                  <th className="py-2 pr-3 text-right">Cost to complete</th>
                  <th className="py-2 pr-3 text-right">Change</th>
                  <th className="py-2 pr-3">Acceptance</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 500).map((r: any, idx: number) => (
                  <tr key={(r.budget_code_key || r.cost_code || idx) + ''} className="border-b border-[var(--hb-border)]">
                    <td className="py-2 pr-3">{r.cost_code || '—'}</td>
                    <td className="py-2 pr-3 text-right">{r.recommended_final_cost ?? '—'}</td>
                    <td className="py-2 pr-3 text-right">{r.cost_to_complete ?? '—'}</td>
                    <td className="py-2 pr-3 text-right">{r.change_amount ?? '—'}</td>
                    <td className="py-2 pr-3">{r.acceptance_status || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > 500 && (
              <p className="text-xs text-[var(--hb-muted)] mt-2">Showing the first 500 of {rows.length} cost codes.</p>
            )}
          </div>
        )}
      </div>

      <div className="card mt-3">
        <div className="section-title">Human-review queue</div>
        {reviewItems.length === 0 ? (
          <EmptyState title="No review items" hint="Items flagged for human review will appear here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                  <th className="py-2 pr-3">Cost code</th>
                  <th className="py-2 pr-3">Priority</th>
                  <th className="py-2 pr-3">Reason</th>
                  <th className="py-2 pr-3">Acceptance</th>
                </tr>
              </thead>
              <tbody>
                {reviewItems.slice(0, 500).map((it: any, idx: number) => (
                  <tr key={(it.budget_code_key || it.cost_code || idx) + ''} className="border-b border-[var(--hb-border)]">
                    <td className="py-2 pr-3">{it.cost_code || '—'}</td>
                    <td className="py-2 pr-3">{it.review_priority || '—'}</td>
                    <td className="py-2 pr-3 text-[var(--hb-muted)]">{it.review_reason || '—'}</td>
                    <td className="py-2 pr-3">{it.acceptance_status || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
