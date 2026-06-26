import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { DashboardGrid } from '../components/layout/DashboardGrid'
import { PrimaryPageLayout } from '../components/layout/PrimaryPageLayout'
import { ProjectCard } from '../components/projects/ProjectCard'
import { api } from '../lib/api'

export function ProjectsPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  })

  if (isLoading) {
    return <LoadingState label="Loading projects" />
  }

  if (error) {
    return (
      <ErrorState
        userMessage="Projects could not be loaded. Check the local data connection and try again."
        error={error}
        onRetry={() => { void refetch() }}
      />
    )
  }

  const projects = data?.projects ?? []

  return (
    <PrimaryPageLayout>
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Projects</h2>
          <p className="mt-1 text-sm text-[var(--hb-muted)]">Select a project to open its workspace.</p>
        </div>

        {projects.length > 0 ? (
          <DashboardGrid>
            {projects.map((project) => (
              <ProjectCard key={project.project_key} project={project} />
            ))}
          </DashboardGrid>
        ) : (
          <EmptyState
            title="No projects are available yet."
            hint="Project data will appear after project records are loaded."
          />
        )}
      </div>
    </PrimaryPageLayout>
  )
}
