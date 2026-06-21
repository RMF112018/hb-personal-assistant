/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecasting — package & run history (Implementation Phase 1, read-only).
 * Lists the deterministic forecast packages the backend has already produced for a project
 * and period. Business-facing only: friendly labels, validation status, and a friendly date.
 * No paths, run stamps, directory names, or internals are shown. */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/ui/EmptyState'
import { ForecastReadinessPanel } from '../components/forecast/ForecastReadinessPanel'
import { api } from '../lib/api'

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  validated: { label: 'Validated', cls: 'text-emerald-300 border-emerald-700' },
  attention: { label: 'Needs attention', cls: 'text-amber-300 border-amber-700' },
  invalid: { label: 'Unreadable', cls: 'text-rose-300 border-rose-700' },
  unsupported: { label: 'Unsupported', cls: 'text-[var(--hb-muted)] border-[var(--hb-border)]' },
  unknown: { label: 'Unknown', cls: 'text-[var(--hb-muted)] border-[var(--hb-border)]' },
}

export function StatusPill({ status }: { status: string }) {
  const s = STATUS_LABEL[status] || STATUS_LABEL.unknown
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs ${s.cls}`}>{s.label}</span>
  )
}

export function ForecastingPage() {
  const { data: projectsResp, isLoading: projLoading, error: projError } = useQuery({
    queryKey: ['forecast', 'projects'],
    queryFn: () => api.getForecastProjects(),
  })

  const projects: any[] = Array.isArray(projectsResp?.projects) ? projectsResp.projects : []
  const projectKey: string | undefined = projects[0]?.project_key

  const { data: periodsResp } = useQuery({
    queryKey: ['forecast', 'periods', projectKey],
    queryFn: () => api.getForecastPeriods(projectKey as string),
    enabled: Boolean(projectKey),
  })

  const periods: any[] = Array.isArray(periodsResp?.periods) ? periodsResp.periods : []
  const [period, setPeriod] = useState<string | undefined>(undefined)
  useEffect(() => {
    if (!period && periods.length > 0) setPeriod(periods[0].period)
  }, [periods, period])

  const { data: packagesResp, isLoading: pkgLoading } = useQuery({
    queryKey: ['forecast', 'packages', projectKey, period],
    queryFn: () => api.getForecastPackages(projectKey as string, period as string),
    enabled: Boolean(projectKey && period),
  })

  if (projLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading forecast packages…</div>
  }

  if (projError) {
    const status = (projError as any)?.status
    const isUnconfigured = status === 503
    const message = isUnconfigured
      ? 'Forecast packages are not configured for this environment yet.'
      : 'We could not load forecast packages right now.'
    return (
      <div>
        {isUnconfigured && <ForecastReadinessPanel />}
        <div className={isUnconfigured ? 'card mt-3' : 'card'}>
          <div className="section-title">Forecasting</div>
          <EmptyState
            title="Forecast packages unavailable"
            hint={message}
            actions={
              isUnconfigured ? (
                <Link to="/forecasting/runtime" className="underline">
                  Configure data sources →
                </Link>
              ) : undefined
            }
          />
        </div>
      </div>
    )
  }

  const packages: any[] = Array.isArray(packagesResp?.packages) ? packagesResp.packages : []
  const project = projects[0] || {}

  return (
    <div>
      <ForecastReadinessPanel />
      <div className="card mt-3">
        <div className="flex items-center justify-between gap-3">
          <div className="section-title">Forecasting</div>
          <div className="flex gap-3">
            <Link to="/forecasting/runs" className="text-sm underline">
              Run a forecast
            </Link>
            <Link to="/forecasting/external" className="text-sm underline">
              Evaluate external forecast
            </Link>
            <Link to="/forecasting/config" className="text-sm underline">
              View configuration
            </Link>
            <Link to="/forecasting/runtime" className="text-sm underline">
              Data sources
            </Link>
          </div>
        </div>
        <p className="text-sm">
          Forecast packages generated for{' '}
          <span className="font-medium">{project.project_name || project.project_key || 'this project'}</span>
          {project.job_reference ? ` (Job ${project.job_reference})` : ''}. Each entry is a deterministic,
          validated forecast run. Open a package to review the recommended final cost, monthly outlook, and
          human-review items.
        </p>

        {periods.length > 0 && (
          <div className="flex items-center gap-2 mt-3 mb-1 text-sm">
            <label htmlFor="forecast-period" className="text-[var(--hb-muted)]">
              Period
            </label>
            <select
              id="forecast-period"
              className="rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
              value={period || ''}
              onChange={(e) => setPeriod(e.target.value)}
            >
              {periods.map((p: any) => (
                <option key={p.period} value={p.period}>
                  {p.period} ({p.package_count})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="card mt-3">
        <div className="section-title">Package &amp; run history</div>
        {pkgLoading ? (
          <div className="text-sm text-[var(--hb-muted)]">Loading packages…</div>
        ) : packages.length === 0 ? (
          <EmptyState
            title="No forecast packages found"
            hint="Generated forecast packages for the selected period will appear here."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                  <th className="py-2 pr-3">Forecast</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Checks</th>
                  <th className="py-2 pr-3">Generated</th>
                  <th className="py-2 pr-3"></th>
                </tr>
              </thead>
              <tbody>
                {packages.map((pkg: any) => (
                  <tr key={pkg.package_id} className="border-b border-[var(--hb-border)]">
                    <td className="py-2 pr-3">{pkg.display_label}</td>
                    <td className="py-2 pr-3">
                      <StatusPill status={pkg.status} />
                    </td>
                    <td className="py-2 pr-3 text-[var(--hb-muted)]">
                      {pkg.validation_total ? `${pkg.validation_passed}/${pkg.validation_total}` : '—'}
                    </td>
                    <td className="py-2 pr-3 text-[var(--hb-muted)]">{pkg.generated_display || '—'}</td>
                    <td className="py-2 pr-3">
                      <Link to={`/forecasting/${encodeURIComponent(pkg.package_id)}`} className="underline">
                        Open
                      </Link>
                    </td>
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
