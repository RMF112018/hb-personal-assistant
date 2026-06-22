/* Forecasting command center — package browser and executive summary (read-only). */
import { ClipboardList, Sparkles } from 'lucide-react'
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import { ForecastReadinessPanel } from '../components/forecast/ForecastReadinessPanel'
import {
  ForecastActionLink,
  ForecastAdvisoryStrip,
  ForecastPageHeader,
  ForecastQuickLink,
  ForecastQuickLinks,
  ForecastShell,
  ForecastSubnav,
  ForecastSummaryCard,
  ForecastSummaryGrid,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from '../components/forecast/ForecastPageChrome'
import { ForecastStatusPill } from '../components/forecast/ForecastStatusPill'
import { useEffectiveSelection } from '../components/forecast/useEffectiveSelection'
import { useForecastReadiness } from '../hooks/useForecastReadiness'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

/** @deprecated Import from `ForecastStatusPill` — kept for gradual migration. */
export { ForecastStatusPill as StatusPill }

type ForecastProject = { project_key?: string; project_name?: string; job_reference?: string }
type ForecastPeriod = { period: string; package_count?: number }
type ForecastPackage = {
  package_id: string
  display_label?: string
  status?: string
  generated_display?: string
  validation_total?: number
  validation_passed?: number
  validation_failed?: number
}

export function ForecastingPage() {
  const { data: readiness } = useForecastReadiness()

  const { data: projectsResp, isLoading: projLoading, error: projError } = useQuery({
    queryKey: ['forecast', 'projects'],
    queryFn: () => api.getForecastProjects(),
  })

  const projects: ForecastProject[] = Array.isArray(projectsResp?.projects) ? projectsResp.projects : []
  const projectKey = projects[0]?.project_key

  const { data: periodsResp } = useQuery({
    queryKey: ['forecast', 'periods', projectKey],
    queryFn: () => api.getForecastPeriods(projectKey as string),
    enabled: Boolean(projectKey),
  })

  const periods = useMemo(
    () => (Array.isArray(periodsResp?.periods) ? periodsResp.periods : []) as ForecastPeriod[],
    [periodsResp],
  )
  const periodOptions = useMemo(() => periods.map((p) => p.period), [periods])
  const [period, setPeriod] = useEffectiveSelection(periodOptions)

  const { data: packagesResp, isLoading: pkgLoading } = useQuery({
    queryKey: ['forecast', 'packages', projectKey, period],
    queryFn: () => api.getForecastPackages(projectKey as string, period as string),
    enabled: Boolean(projectKey && period),
  })

  const { data: runsResp } = useQuery({
    queryKey: ['forecast', 'runs'],
    queryFn: () => api.getForecastRuns(),
    staleTime: 30_000,
  })

  const { data: evalResp } = useQuery({
    queryKey: ['forecast', 'external', 'evaluations'],
    queryFn: () => api.getExternalEvaluations(),
    staleTime: 30_000,
  })

  const { data: configResp } = useQuery({
    queryKey: ['forecast', 'config', 'snapshots'],
    queryFn: () => api.getForecastConfigSnapshots(),
    staleTime: 30_000,
  })

  if (projLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading forecast overview…</div>
  }

  if (projError) {
    const status = (projError as { status?: number })?.status
    const isUnconfigured = status === 503
    const message = isUnconfigured
      ? 'Forecast packages are not available yet. Check storage readiness first.'
      : 'We could not load forecast packages right now.'
    return (
      <ForecastShell>
        <ForecastSubnav />
        {isUnconfigured && <ForecastReadinessPanel />}
        <section className="forecast-panel">
          <ForecastPageHeader title="Forecast command center" subtitle={message} />
          {isUnconfigured && (
            <div className="mt-3">
              <ForecastActionLink to="/forecasting/runtime" variant="primary">
                Open storage settings
              </ForecastActionLink>
            </div>
          )}
        </section>
      </ForecastShell>
    )
  }

  const packages: ForecastPackage[] = Array.isArray(packagesResp?.packages) ? packagesResp.packages : []
  const project = projects[0] || {}
  const latestPkg = packages[0]
  const reviewAttention = packages.reduce((n, p) => n + (p.validation_failed || 0), 0)
  const runs = Array.isArray(runsResp?.runs) ? runsResp.runs : []
  const evaluations = Array.isArray(evalResp?.evaluations) ? evalResp.evaluations : []
  const snapshots = Array.isArray(configResp?.snapshots) ? configResp.snapshots : []

  const storageReady = Boolean(readiness?.surfaces_ready?.catalog)
  const storageMode = readiness?.storage_mode === 'custom' ? 'Custom' : 'Managed by HB'

  return (
    <ForecastShell>
      <ForecastSubnav />
      <ForecastReadinessPanel />

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Forecast command center"
          subtitle={`Cost and completion forecasts for ${project.project_name || project.project_key || 'your project'}${project.job_reference ? ` (Job ${project.job_reference})` : ''}. All surfaces are advisory — nothing writes back to Procore or live project systems.`}
          actions={
            <>
              <ForecastActionLink to="/forecasting/runs" variant="primary">
                <Sparkles size={14} aria-hidden />
                Generate forecast
              </ForecastActionLink>
              {latestPkg && (
                <ForecastActionLink to={`/forecasting/${encodeURIComponent(latestPkg.package_id)}`}>
                  <ClipboardList size={14} aria-hidden />
                  Review latest
                </ForecastActionLink>
              )}
            </>
          }
        />
        <div className="mt-2">
          <ForecastAdvisoryStrip>Advisory only · No Procore writeback</ForecastAdvisoryStrip>
        </div>

        <ForecastSummaryGrid>
          <ForecastSummaryCard
            label="Local forecast storage"
            value={storageReady ? 'Ready' : 'Needs attention'}
            detail={storageMode}
            status={storageReady ? 'ready' : 'attention'}
          />
          <ForecastSummaryCard
            label="Packages this period"
            value={period ? String(packages.length) : '—'}
            detail={period ? `Period ${period}` : 'Select a period below'}
            status={packages.length > 0 ? 'ready' : 'neutral'}
          />
          <ForecastSummaryCard
            label="Latest forecast"
            value={latestPkg?.display_label || 'None yet'}
            detail={latestPkg?.generated_display ? `Generated ${latestPkg.generated_display}` : 'Generate to begin'}
            status={latestPkg ? 'ready' : 'neutral'}
          />
          <ForecastSummaryCard
            label="Open review signals"
            value={reviewAttention > 0 ? String(reviewAttention) : 'None'}
            detail={reviewAttention > 0 ? 'Validation checks need review' : 'No failed checks in listed packages'}
            status={reviewAttention > 0 ? 'attention' : 'ready'}
          />
          <ForecastSummaryCard
            label="External evaluations"
            value={String(evaluations.length)}
            detail={evaluations.length ? 'Prior operator comparisons on file' : 'Upload an operator forecast to compare'}
            status={evaluations.length > 0 ? 'ready' : 'neutral'}
          />
          <ForecastSummaryCard
            label="Configuration snapshot"
            value={snapshots.length ? (snapshots[0]?.snapshot_name as string) || 'Available' : 'Not available'}
            detail={
              snapshots.length
                ? `${snapshots[0]?.item_count ?? '—'} settings captured`
                : 'Database or snapshot not ready'
            }
            status={snapshots.length > 0 ? 'ready' : 'attention'}
          />
        </ForecastSummaryGrid>

        <ForecastQuickLinks>
          <ForecastQuickLink to="/forecasting/external">Evaluate external forecast</ForecastQuickLink>
          <ForecastQuickLink to="/forecasting/config">View configuration</ForecastQuickLink>
          <ForecastQuickLink to="/forecasting/runtime">Storage settings</ForecastQuickLink>
        </ForecastQuickLinks>
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Forecast packages</h2>
        <p className="text-sm text-[var(--hb-muted)] mt-1 leading-relaxed">
          Deterministic, validated forecast packages for review. Open a package to see recommended
          final cost, monthly outlook, risk indicators, and the human review queue.
        </p>

        {periodOptions.length > 0 && (
          <div className="flex items-center gap-2 mt-4 text-sm">
            <label htmlFor="forecast-period" className="text-[var(--hb-muted)] font-medium">
              Period
            </label>
            <select
              id="forecast-period"
              className="rounded-md border border-[var(--hb-border)] bg-[var(--hb-bg)]/40 px-2.5 py-1.5 text-sm"
              value={period || ''}
              onChange={(e) => setPeriod(e.target.value)}
            >
              {periods.map((p) => (
                <option key={p.period} value={p.period}>
                  {p.period} ({p.package_count ?? 0})
                </option>
              ))}
            </select>
          </div>
        )}

        {pkgLoading ? (
          <div className="text-sm text-[var(--hb-muted)] mt-3">Loading packages…</div>
        ) : packages.length === 0 ? (
          <EmptyState
            title="No forecast packages yet"
            hint="Local storage may be ready, but no packages have been generated for this period. Generate a forecast to begin."
            actions={
              <ForecastActionLink to="/forecasting/runs" variant="primary">
                Generate first forecast
              </ForecastActionLink>
            }
          />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Forecast</ForecastTh>
                <ForecastTh>Status</ForecastTh>
                <ForecastTh>Checks</ForecastTh>
                <ForecastTh>Generated</ForecastTh>
                <ForecastTh />
              </>
            }
          >
            {packages.map((pkg) => (
              <tr key={pkg.package_id}>
                <ForecastTd>{pkg.display_label}</ForecastTd>
                <ForecastTd>
                  <ForecastStatusPill status={pkg.status || 'unknown'} />
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {pkg.validation_total ? `${pkg.validation_passed}/${pkg.validation_total}` : '—'}
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{pkg.generated_display || '—'}</ForecastTd>
                <ForecastTd>
                  <ForecastActionLink to={`/forecasting/${encodeURIComponent(pkg.package_id)}`} variant="ghost">
                    Review
                  </ForecastActionLink>
                </ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}

        {runs.length > 0 && (
          <p className="text-xs text-[var(--hb-muted)] mt-3">
            {runs.length} generation run{runs.length === 1 ? '' : 's'} on file.{' '}
            <ForecastQuickLink to="/forecasting/runs">View run history</ForecastQuickLink>
          </p>
        )}
      </section>
    </ForecastShell>
  )
}