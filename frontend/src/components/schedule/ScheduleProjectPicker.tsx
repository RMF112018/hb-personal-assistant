import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { api } from '../../lib/api'

export type ScheduleProjectOption = {
  project_key: string
  display_name?: string | null
  display_label?: string | null
  project_number?: string | null
  procore_project_id?: string | null
  source_system?: string
  selectable_for_import?: boolean
  has_schedule_imports?: boolean
}

export type ScheduleProjectsResponse = {
  catalog_status?: string
  projects?: ScheduleProjectOption[]
}

export function useScheduleProjects() {
  return useQuery({
    queryKey: ['schedules', 'projects'],
    queryFn: () => api.getScheduleProjects() as Promise<ScheduleProjectsResponse>,
  })
}

export function projectOptionLabel(project: ScheduleProjectOption): string {
  const name = project.display_name || project.display_label
  const parts = [name || project.project_key]
  if (project.project_number) parts.push(`#${project.project_number}`)
  if (project.procore_project_id) parts.push(`Procore ${project.procore_project_id}`)
  return parts.join(' · ')
}

export function useScheduleProjectParam(): [string, (next: string) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const project = searchParams.get('project') || ''
  const setProject = (next: string) => {
    const params = new URLSearchParams(searchParams)
    if (next) params.set('project', next)
    else params.delete('project')
    setSearchParams(params, { replace: true })
  }
  return [project, setProject]
}

export function ScheduleProjectPicker({
  value,
  onChange,
  label = 'Project',
  required = false,
  allowAll = false,
  importSelectableOnly = false,
  className = '',
}: {
  value: string
  onChange: (projectKey: string) => void
  label?: string
  required?: boolean
  allowAll?: boolean
  importSelectableOnly?: boolean
  className?: string
}) {
  const { data, isLoading } = useScheduleProjects()
  const projects = (data?.projects ?? []).filter((project) =>
    importSelectableOnly ? project.selectable_for_import : true,
  )

  return (
    <label className={`block text-sm ${className}`}>
      <span className="text-[var(--hb-muted)]">
        {label}
        {required ? ' (required)' : ''}
      </span>
      <select
        className="mt-1 block w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5 text-sm"
        value={value}
        disabled={isLoading}
        onChange={(e) => onChange(e.target.value)}
      >
        {allowAll ? <option value="">All projects</option> : <option value="">Select a project</option>}
        {isLoading ? <option value="" disabled>Loading projects…</option> : null}
        {!isLoading && importSelectableOnly && projects.length === 0 ? (
          <option value="" disabled>
            No Procore projects available for import
          </option>
        ) : null}
        {projects.map((project) => (
          <option key={project.project_key} value={project.project_key}>
            {projectOptionLabel(project)}
          </option>
        ))}
      </select>
      {!isLoading && importSelectableOnly && data?.catalog_status === 'empty' ? (
        <p className="mt-1 text-xs text-[var(--hb-muted)]">
          Populate procore_ep_projects via Procore projection replay before importing schedules.
        </p>
      ) : null}
    </label>
  )
}

export function ScheduleProjectContext({
  projectKey,
  projects,
}: {
  projectKey?: string | null
  projects?: ScheduleProjectOption[]
}) {
  if (!projectKey) return null
  const project = projects?.find((p) => p.project_key === projectKey)
  const display = project?.display_name || project?.display_label
  return (
    <p className="text-sm text-[var(--hb-muted)]">
      Project:{' '}
      <span className="text-[var(--hb-fg)] font-medium">
        {display || 'display name unavailable'}
      </span>{' '}
      <span className="font-mono text-xs">({projectKey})</span>
      {project?.project_number ? <span> · #{project.project_number}</span> : null}
    </p>
  )
}