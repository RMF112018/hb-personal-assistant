import { Link, useParams } from 'react-router-dom'

import { SectionCard } from '../components/common/SectionCard'
import { ProjectForecastingSummary } from '../components/projects/ProjectForecastingSummary'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'

export function ProjectForecastingPage() {
  const { projectKey = '' } = useParams()
  const monthlyHref = `/projects/${encodeURIComponent(projectKey)}/forecasting/monthly`

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4">
        <div>
          <h3 className="section-title mb-0">Forecasting</h3>
          <p className="mt-1 text-sm text-[var(--hb-muted)]">
            Review forecast status, latest forecast output, and project-specific forecasting tools.
          </p>
        </div>

        <ProjectForecastingSummary projectKey={projectKey} />

        <div className="grid gap-4 md:grid-cols-2">
          <SectionCard
            title="Monthly Forecasting"
            actions={
              <Link to={monthlyHref} className="badge">
                Open
              </Link>
            }
          >
            <p className="text-sm text-[var(--hb-muted)]">
              Review the month-by-month forecast matrix for this project.
            </p>
          </SectionCard>

          <SectionCard title="Create Forecast">
            <p className="text-sm text-[var(--hb-muted)]">
              Project-specific forecast creation will be wired in a future pass.
            </p>
          </SectionCard>
        </div>
      </section>
    </ProjectWorkspaceShell>
  )
}
