/* Forecast package review — headline metrics, validation, cost outlook (read-only). */
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import {
  ForecastAdvisoryStrip,
  ForecastBackLink,
  ForecastProgressRow,
  ForecastShell,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from '../components/forecast/ForecastPageChrome'
import { ForecastStatusPill } from '../components/forecast/ForecastStatusPill'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return '—'
  return String(value)
}

function HeadlineMetric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="forecast-metric-card">
      <div className="forecast-metric-label">{label}</div>
      <div className="forecast-metric-value text-lg">{displayValue(value)}</div>
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
  // Phase 5 review surfaces (read-only).
  const { data: monthlyResp } = useQuery({
    queryKey: ['forecast', 'monthly', packageId],
    queryFn: () => api.getForecastPackageMonthly(packageId),
    enabled: Boolean(packageId),
  })
  const { data: probResp } = useQuery({
    queryKey: ['forecast', 'probability', packageId],
    queryFn: () => api.getForecastPackageProbability(packageId),
    enabled: Boolean(packageId),
  })
  const { data: riskResp } = useQuery({
    queryKey: ['forecast', 'risk', packageId],
    queryFn: () => api.getForecastPackageRiskRegister(packageId),
    enabled: Boolean(packageId),
  })
  const { data: topRisksResp } = useQuery({
    queryKey: ['forecast', 'top-risks', packageId],
    queryFn: () => api.getForecastPackageTopRisks(packageId),
    enabled: Boolean(packageId),
  })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading forecast package…</div>
  }

  if (error) {
    const status = (error as { status?: number })?.status
    const message =
      status === 404
        ? 'This forecast package could not be found.'
        : 'We could not load this forecast package right now.'
    return (
      <div className="card">
        <ForecastBackLink label="Back to forecast overview" />
        <EmptyState title="Forecast package unavailable" hint={message} />
      </div>
    )
  }

  const s = (summary || {}) as Record<string, unknown>
  const headline = (s.headline || {}) as Record<string, unknown>
  const v = (validation || {}) as Record<string, unknown>
  const rows = (Array.isArray(rowsResp?.rows) ? rowsResp.rows : []) as Record<string, unknown>[]
  const reviewItems = (Array.isArray(reviewResp?.items) ? reviewResp.items : []) as Record<string, unknown>[]
  const failedChecks = Array.isArray(v.failed_checks) ? (v.failed_checks as string[]) : []
  const projectMonthly = (Array.isArray(monthlyResp?.project_monthly)
    ? monthlyResp.project_monthly
    : []) as Record<string, unknown>[]
  const probRows = (Array.isArray(probResp?.rows) ? probResp.rows : []) as Record<string, unknown>[]
  const riskRows = (Array.isArray(riskResp?.rows) ? riskResp.rows : []) as Record<string, unknown>[]
  const topRisks = (Array.isArray(topRisksResp?.rows) ? topRisksResp.rows : []) as Record<string, unknown>[]
  const maxMonthly = projectMonthly.reduce((m, p) => Math.max(m, Number(p.amount) || 0), 0)

  return (
    <ForecastShell>
      <ForecastBackLink label="Back to forecast overview" />

      <section className="forecast-panel">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="forecast-eyebrow mb-1">Package review</div>
            <h1 className="forecast-title">{String(s.display_label || 'Forecast package')}</h1>
            <div className="mt-2">
              <ForecastAdvisoryStrip>Advisory review — not a system-of-record posting</ForecastAdvisoryStrip>
            </div>
          </div>
          <ForecastStatusPill status={String(s.status || 'unknown')} />
        </div>
        <p className="text-sm text-[var(--hb-muted)]">
          {s.project_key ? `${s.project_key}` : ''}
          {s.job_reference ? ` · Job ${s.job_reference}` : ''}
          {s.period ? ` · ${s.period}` : ''}
          {s.generated_display ? ` · Generated ${s.generated_display}` : ''}
        </p>

        {Object.keys(headline).length > 0 && (
          <div className="forecast-metric-grid mt-4">
            {Object.entries(HEADLINE_LABELS)
              .filter(([k]) => k in headline)
              .map(([k, label]) => (
                <HeadlineMetric key={k} label={label} value={headline[k]} />
              ))}
          </div>
        )}
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Validation</h2>
        {v.total_checks ? (
          <p className="text-sm">
            {displayValue(v.passed)}/{displayValue(v.total_checks)} checks passed.{' '}
            {Number(v.failed) > 0 ? (
              <span className="text-amber-300">{displayValue(v.failed)} need attention.</span>
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
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Recommended final cost by cost code</h2>
        {rows.length === 0 ? (
          <EmptyState
            title="No cost-code rows"
            hint="This package type does not include per-cost-code final-cost rows."
          />
        ) : (
          <>
            <ForecastTable
              headers={
                <>
                  <ForecastTh>Cost code</ForecastTh>
                  <ForecastTh className="text-right">Recommended final cost</ForecastTh>
                  <ForecastTh className="text-right">Cost to complete</ForecastTh>
                  <ForecastTh className="text-right">Change</ForecastTh>
                  <ForecastTh>Acceptance</ForecastTh>
                </>
              }
            >
              {rows.slice(0, 500).map((r, idx: number) => (
                <tr key={(r.budget_code_key || r.cost_code || idx) + ''}>
                  <ForecastTd>{displayValue(r.cost_code)}</ForecastTd>
                  <ForecastTd className="text-right">{displayValue(r.recommended_final_cost)}</ForecastTd>
                  <ForecastTd className="text-right">{displayValue(r.cost_to_complete)}</ForecastTd>
                  <ForecastTd className="text-right">{displayValue(r.change_amount)}</ForecastTd>
                  <ForecastTd>{displayValue(r.acceptance_status)}</ForecastTd>
                </tr>
              ))}
            </ForecastTable>
            {rows.length > 500 && (
              <p className="text-xs text-[var(--hb-muted)] mt-2">Showing the first 500 of {rows.length} cost codes.</p>
            )}
          </>
        )}
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Review queue</h2>
        {reviewItems.length === 0 ? (
          <EmptyState title="No review items" hint="Items flagged for human review will appear here." />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Cost code</ForecastTh>
                <ForecastTh>Priority</ForecastTh>
                <ForecastTh>Reason</ForecastTh>
                <ForecastTh>Acceptance</ForecastTh>
              </>
            }
          >
            {reviewItems.slice(0, 500).map((it, idx: number) => (
              <tr key={(it.budget_code_key || it.cost_code || idx) + ''}>
                <ForecastTd>{displayValue(it.cost_code)}</ForecastTd>
                <ForecastTd>{displayValue(it.review_priority)}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{displayValue(it.review_reason)}</ForecastTd>
                <ForecastTd>{displayValue(it.acceptance_status)}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Monthly cost trend</h2>
        {projectMonthly.length === 0 ? (
          <EmptyState title="No monthly trend" hint="This package type does not include a monthly forecast." />
        ) : (
          <div className="space-y-2 mt-2">
            {projectMonthly.slice(0, 60).map((p, idx: number) => (
              <ForecastProgressRow
                key={(p.forecast_month || idx) + ''}
                label={displayValue(p.forecast_month)}
                value={Number(p.amount) || 0}
                max={maxMonthly}
                display={displayValue(p.amount)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Probability bands by cost code</h2>
        {probRows.length === 0 ? (
          <EmptyState title="No probability data" hint="This package type does not include probability bands." />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Cost code</ForecastTh>
                <ForecastTh className="text-right">Actual to date</ForecastTh>
                <ForecastTh className="text-right">P10</ForecastTh>
                <ForecastTh className="text-right">P50</ForecastTh>
                <ForecastTh className="text-right">P80</ForecastTh>
                <ForecastTh className="text-right">P90</ForecastTh>
                <ForecastTh className="text-right">P95</ForecastTh>
              </>
            }
          >
            {probRows.slice(0, 500).map((r, idx: number) => (
              <tr key={(r.budget_code_key || r.cost_code || idx) + ''}>
                <ForecastTd>{displayValue(r.cost_code)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.actual_cost_to_date)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.p10)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.p50)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.p80)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.p90)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.p95)}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Risk register</h2>
        {riskRows.length === 0 ? (
          <EmptyState title="No risk register" hint="This package type does not include a risk register." />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Cost code</ForecastTh>
                <ForecastTh className="text-right">Recommended final cost</ForecastTh>
                <ForecastTh className="text-right">Variance</ForecastTh>
                <ForecastTh className="text-right">Conflicts</ForecastTh>
                <ForecastTh>Severity</ForecastTh>
                <ForecastTh>Priority</ForecastTh>
              </>
            }
          >
            {riskRows.slice(0, 500).map((r, idx: number) => (
              <tr key={(r.budget_code_key || r.cost_code || idx) + ''}>
                <ForecastTd>{displayValue(r.cost_code)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.recommended_final_cost)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.variance_amount)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.conflict_count)}</ForecastTd>
                <ForecastTd>{displayValue(r.max_conflict_severity)}</ForecastTd>
                <ForecastTd>{displayValue(r.review_priority)}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Top overrun risks</h2>
        {topRisks.length === 0 ? (
          <EmptyState title="No overrun risks" hint="This package type does not include a top-risk ranking." />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Cost code</ForecastTh>
                <ForecastTh className="text-right">Recommended final cost</ForecastTh>
                <ForecastTh className="text-right">Overrun</ForecastTh>
                <ForecastTh>Direction</ForecastTh>
              </>
            }
          >
            {topRisks.slice(0, 500).map((r, idx: number) => (
              <tr key={(r.budget_code_key || r.cost_code || idx) + ''}>
                <ForecastTd>{displayValue(r.cost_code)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.recommended_final_cost)}</ForecastTd>
                <ForecastTd className="text-right">{displayValue(r.overrun_amount)}</ForecastTd>
                <ForecastTd>{displayValue(r.direction)}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </section>
    </ForecastShell>
  )
}
