import { Link, useParams } from 'react-router-dom'

import { SectionCard } from '../components/common/SectionCard'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'

export function ProjectMonthlyForecastingPage() {
  const { projectKey = '' } = useParams()
  const forecastingHref = `/projects/${encodeURIComponent(projectKey)}/forecasting`

  return (
    <ProjectWorkspaceShell>
      <SectionCard
        title="Monthly Forecasting"
        actions={
          <Link to={forecastingHref} className="badge">
            Back to Forecasting
          </Link>
        }
      >
        <p className="text-sm text-[var(--hb-muted)]">
          The project-specific monthly forecast matrix will be added here in the next phase.
        </p>
      </SectionCard>
    </ProjectWorkspaceShell>
  )
}
