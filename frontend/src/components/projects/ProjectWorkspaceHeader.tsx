import type { ProjectSummary } from '../../lib/api'
import { cleanProjectText, formatProjectAddress, projectDisplayName } from './projectSummaryDisplay'

type ProjectWorkspaceHeaderProps = {
  project: ProjectSummary
}

export function ProjectWorkspaceHeader({ project }: ProjectWorkspaceHeaderProps) {
  const metadata = [
    ['Project number', cleanProjectText(project.project_number)],
    ['Project key', cleanProjectText(project.project_key)],
    ['Procore project ID', cleanProjectText(project.procore_project_id)],
  ].filter((item): item is [string, string] => Boolean(item[1]))

  return (
    <header className="card">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--hb-muted)]">
            Project workspace
          </div>
          <h2 className="mt-1 text-xl font-semibold">{projectDisplayName(project)}</h2>
          <p className="mt-1 text-sm text-[var(--hb-muted)]">{formatProjectAddress(project)}</p>
        </div>
        {metadata.length > 0 && (
          <dl className="grid gap-2 text-xs sm:grid-cols-3 md:max-w-xl">
            {metadata.map(([label, value]) => (
              <div key={label} className="rounded-md border border-[var(--hb-border)] px-3 py-2">
                <dt className="text-[var(--hb-muted)]">{label}</dt>
                <dd className="mt-1 font-medium text-[var(--hb-text)]">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </header>
  )
}
