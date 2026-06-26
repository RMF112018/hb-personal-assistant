import { Link, useParams } from 'react-router-dom'

import { ProjectMonthlyForecastingPanel } from '../components/projects/ProjectMonthlyForecastingPanel'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'

export function ProjectMonthlyForecastingPage() {
  const { projectKey = '' } = useParams()
  const forecastingHref = `/projects/${encodeURIComponent(projectKey)}/forecasting`

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

        <ProjectMonthlyForecastingPanel projectKey={projectKey} />
      </section>
    </ProjectWorkspaceShell>
  )
}
