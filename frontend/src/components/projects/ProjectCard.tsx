import { Link } from 'react-router-dom'

import type { ProjectSummary } from '../../lib/api'
import { formatProjectAddress, projectDisplayName } from './projectSummaryDisplay'

type ProjectCardProps = {
  project: ProjectSummary
}

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Link
      to={`/projects/${encodeURIComponent(project.project_key)}`}
      className="block rounded-md border border-[var(--hb-border)] bg-[var(--hb-bg)] p-3 transition-colors hover:border-[var(--hb-accent)]"
    >
      <div className="font-medium">{projectDisplayName(project)}</div>
      <div className="mt-2 text-sm text-[var(--hb-muted)]">{formatProjectAddress(project)}</div>
    </Link>
  )
}
