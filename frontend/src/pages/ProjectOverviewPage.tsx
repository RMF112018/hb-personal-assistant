import { DashboardGrid } from '../components/layout/DashboardGrid'
import { SectionCard } from '../components/common/SectionCard'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'

const overviewCards = [
  {
    title: 'Financial summary',
    hint: 'Project financial signals will appear here in a future phase.',
  },
  {
    title: 'Schedule status',
    hint: 'Project schedule status will appear here in a future phase.',
  },
  {
    title: 'Open items',
    hint: 'Project-specific open items will appear here in a future phase.',
  },
  {
    title: 'Recent activity',
    hint: 'Recent project activity will appear here in a future phase.',
  },
]

export function ProjectOverviewPage() {
  return (
    <ProjectWorkspaceShell>
      <section className="space-y-3">
        <div>
          <h3 className="section-title mb-0">Project Overview</h3>
          <p className="mt-1 text-sm text-[var(--hb-muted)]">
            This workspace will surface project-specific activity, controls, and reporting.
          </p>
        </div>
        <DashboardGrid columns="sections">
          {overviewCards.map((card) => (
            <SectionCard key={card.title} title={card.title}>
              <p className="text-sm text-[var(--hb-muted)]">{card.hint}</p>
            </SectionCard>
          ))}
        </DashboardGrid>
      </section>
    </ProjectWorkspaceShell>
  )
}
