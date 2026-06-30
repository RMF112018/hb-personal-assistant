import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { ScheduleImportFlow } from '../components/project-schedule/ScheduleImportFlow'
import { api } from '../lib/api'

export function ProjectScheduleImportPage() {
  const { projectKey = '' } = useParams()

  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  })
  const project = projectsData?.projects.find((item) => item.project_key === projectKey)

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4 max-w-2xl">
        <div>
          <h3 className="section-title mb-0">Upload schedule update</h3>
          <p className="mt-1 text-sm text-[var(--hb-muted)]">
            Preview and commit a schedule update for {project?.display_name || projectKey}. Project context is locked
            to this workspace.
          </p>
        </div>

        <ScheduleImportFlow
          projectKey={projectKey}
          projectDisplayName={project?.display_name}
          variant="page"
        />

        <p className="text-xs text-[var(--hb-muted)]">
          <Link className="underline" to={`/projects/${projectKey}/schedule`}>
            Back to Project Schedule
          </Link>
        </p>
      </section>
    </ProjectWorkspaceShell>
  )
}
