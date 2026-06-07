/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { DashboardCard } from '../components/layout/DashboardCard'
import { DashboardGrid } from '../components/layout/DashboardGrid'
import { PrimaryPageLayout } from '../components/layout/PrimaryPageLayout'
import { SectionCard } from '../components/common/SectionCard'
import { AllProjectsLink, ProjectConnectionsLink } from '../components/projects/ProjectActions'
import { ProjectCard } from '../components/projects/ProjectCard'
import { ProjectSetupState } from '../components/projects/ProjectSetupState'
import { ProjectStatusRow } from '../components/projects/ProjectStatusRow'
import { api } from '../lib/api'

export function ProjectsPage() {
  const { data: portfolio, isLoading, error } = useQuery({
    queryKey: ['projects', 'portfolio'],
    queryFn: api.getProjectsPortfolio,
  })

  if (isLoading) {
    return <LoadingState label="Loading projects" />
  }

  if (error) {
    return (
      <ErrorState
        userMessage="We could not load project data."
        error={error}
        actions={<ProjectConnectionsLink />}
      />
    )
  }

  const individuals = getProjectList(portfolio)
  const activeProjects = individuals.filter((project) => !isSetupNeeded(project))
  const needsSetup = individuals.filter(isSetupNeeded)
  const recentlyUpdated = [...individuals].slice(0, 4)

  return (
    <PrimaryPageLayout
      status={
        <ProjectStatusRow
          freshness={portfolio?.freshness}
          confidence={portfolio?.confidence_summary}
          projectCount={individuals.length}
        />
      }
    >
      <DashboardGrid>
        <DashboardCard title="Active Projects" span="wide" tone="success">
          {activeProjects.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {activeProjects.map((project, index) => (
                <ProjectCard key={getProjectKey(project, index)} project={project} fallbackKey={`project-${index}`} />
              ))}
            </div>
          ) : (
            <ProjectSetupState />
          )}
        </DashboardCard>

        <DashboardCard
          title="Projects that need setup"
          subtitle="Items that need connections or approval before project data can appear."
        >
          {needsSetup.length > 0 ? (
            <div className="space-y-3">
              {needsSetup.map((project, index) => (
                <ProjectCard key={getProjectKey(project, index)} project={project} fallbackKey={`setup-${index}`} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Setup is current."
              hint="Review project connections in Settings when a project is missing."
              actions={<ProjectConnectionsLink />}
            />
          )}
        </DashboardCard>

        <DashboardCard title="Recently updated projects" subtitle="Projects with the latest visible activity.">
          {recentlyUpdated.length > 0 ? (
            <div className="space-y-3">
              {recentlyUpdated.map((project, index) => (
                <ProjectCard key={getProjectKey(project, index)} project={project} fallbackKey={`recent-${index}`} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No recent project updates."
              hint="Project data will appear after sources are connected and approved."
            />
          )}
        </DashboardCard>

        <SectionCard
          title="Project Connections"
          description="Connect and approve project sources before project details are shown here."
          actions={<ProjectConnectionsLink />}
        >
          <p className="text-sm text-[var(--hb-muted)]">
            Project data will appear after sources are connected and approved.
          </p>
        </SectionCard>

        <SectionCard
          title="All Projects"
          description="Review portfolio-wide signals and drill into project details."
          actions={<AllProjectsLink label="Open All Projects" />}
        >
          <p className="text-sm text-[var(--hb-muted)]">
            The combined project view remains available for cross-project review.
          </p>
        </SectionCard>
      </DashboardGrid>
    </PrimaryPageLayout>
  )
}

function getProjectList(portfolio: any): any[] {
  const raw = portfolio?.projects || portfolio?.items || portfolio
  if (Array.isArray(raw) && raw.length > 0) {
    return raw
  }

  if (Array.isArray(portfolio?.project_keys)) {
    return portfolio.project_keys.map((key: string) => ({ key, name: key, status: 'active' }))
  }

  return []
}

function getProjectKey(project: any, index: number) {
  return String(project?.key || project?.project_key || project?.id || `project-${index}`)
}

function isSetupNeeded(project: any) {
  const status = String(project?.status || project?.health || '').toLowerCase()
  return ['setup', 'needs_setup', 'not_configured', 'pending', 'inactive', 'missing'].some((term) => status.includes(term))
}
