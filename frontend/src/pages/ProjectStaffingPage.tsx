import { useParams } from 'react-router-dom'

import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { StaffingAbsencePanel } from '../components/staffing/StaffingAbsencePanel'
import { StaffingAssumptionsPanel } from '../components/staffing/StaffingAssumptionsPanel'
import { StaffingAttributionReview } from '../components/staffing/StaffingAttributionReview'
import { StaffingConfigGrid } from '../components/staffing/StaffingConfigGrid'
import { StaffingMatSummary } from '../components/staffing/StaffingMatSummary'
import { StaffingReadinessSummary } from '../components/staffing/StaffingReadinessSummary'

export function ProjectStaffingPage() {
  const { projectKey = '' } = useParams()

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4">
        <div>
          <h3 className="section-title mb-0">Staffing</h3>
          <p className="mt-1 text-sm text-[var(--hb-muted)]">
            Configure project staffing, review labor actuals, and check readiness for forecasting.
          </p>
        </div>
        <StaffingReadinessSummary project={projectKey} />
        <StaffingConfigGrid project={projectKey} />
        <div className="grid gap-4 md:grid-cols-2">
          <StaffingAssumptionsPanel project={projectKey} />
          <StaffingAbsencePanel project={projectKey} />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <StaffingAttributionReview project={projectKey} />
          <StaffingMatSummary project={projectKey} />
        </div>
      </section>
    </ProjectWorkspaceShell>
  )
}
