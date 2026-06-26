import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../common/EmptyState'
import { ErrorState } from '../common/ErrorState'
import { LoadingState } from '../common/LoadingState'
import { PrimaryPageLayout } from '../layout/PrimaryPageLayout'
import { api } from '../../lib/api'
import { ProjectWorkspaceHeader } from './ProjectWorkspaceHeader'
import { ProjectWorkspaceNav } from './ProjectWorkspaceNav'

type ProjectWorkspaceShellProps = {
  children: ReactNode
}

export function ProjectWorkspaceShell({ children }: ProjectWorkspaceShellProps) {
  const { projectKey = '' } = useParams()
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  })

  if (isLoading) {
    return <LoadingState label="Loading project workspace..." />
  }

  if (error) {
    return (
      <ErrorState
        userMessage="Project workspace could not be loaded. Check the local data connection and try again."
        error={error}
        onRetry={() => { void refetch() }}
      />
    )
  }

  const project = data?.projects.find((item) => item.project_key === projectKey)

  if (!project) {
    return (
      <EmptyState
        title="Project not found"
        hint="The selected project could not be found in the local project list."
        actions={<Link to="/projects" className="badge">Back to Projects</Link>}
      />
    )
  }

  return (
    <PrimaryPageLayout>
      <div className="space-y-4">
        <ProjectWorkspaceHeader project={project} />
        <ProjectWorkspaceNav projectKey={project.project_key} />
        {children}
      </div>
    </PrimaryPageLayout>
  )
}
