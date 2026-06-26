import { SectionCard } from '../components/common/SectionCard'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'

export function ProjectExposuresPlaceholderPage() {
  return (
    <ProjectWorkspaceShell>
      <SectionCard title="Exposures">
        <p className="text-sm text-[var(--hb-muted)]">
          Project-level exposure tracking will be added here in a future phase.
        </p>
      </SectionCard>
    </ProjectWorkspaceShell>
  )
}
