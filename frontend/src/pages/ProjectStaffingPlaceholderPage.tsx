import { SectionCard } from '../components/common/SectionCard'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'

export function ProjectStaffingPlaceholderPage() {
  return (
    <ProjectWorkspaceShell>
      <SectionCard title="Staffing">
        <p className="text-sm text-[var(--hb-muted)]">
          Project staffing configuration and review tools will be added here in a future phase.
        </p>
      </SectionCard>
    </ProjectWorkspaceShell>
  )
}
