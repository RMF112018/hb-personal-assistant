import { Link, useParams, useSearchParams } from 'react-router-dom'

import { ProjectForecastOutputSelector } from '../components/projects/ProjectForecastOutputSelector'
import { ProjectMonthlyForecastingPanel } from '../components/projects/ProjectMonthlyForecastingPanel'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'

export function ProjectMonthlyForecastingPage() {
  const { projectKey = '' } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedOutputId = searchParams.get('outputId')

  const base = `/projects/${encodeURIComponent(projectKey)}`
  const forecastingHref = requestedOutputId
    ? `${base}/forecasting?outputId=${encodeURIComponent(requestedOutputId)}`
    : `${base}/forecasting`

  function selectOutput(outputId: string) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('outputId', outputId)
        return next
      },
      { replace: true },
    )
  }

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="section-title mb-0">Monthly Forecasting</h3>
            <p className="mt-1 text-sm text-[var(--hb-muted)]">
              Review month-by-month forecast values for this project.
            </p>
          </div>
          <Link to={forecastingHref} className="badge">
            Back to Forecasting
          </Link>
        </div>

        <ProjectForecastOutputSelector
          projectKey={projectKey}
          requestedOutputId={requestedOutputId}
          onSelectOutput={selectOutput}
        />

        <ProjectMonthlyForecastingPanel projectKey={projectKey} requestedOutputId={requestedOutputId} />
      </section>
    </ProjectWorkspaceShell>
  )
}
