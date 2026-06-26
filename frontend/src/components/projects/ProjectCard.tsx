import { Link } from 'react-router-dom'

import type { ProjectSummary } from '../../lib/api'

type ProjectCardProps = {
  project: ProjectSummary
}

export function ProjectCard({ project }: ProjectCardProps) {
  const name = cleanText(project.display_name) || project.project_key
  const address = formatAddress(project)

  return (
    <Link
      to={`/projects/${encodeURIComponent(project.project_key)}`}
      className="block rounded-md border border-[var(--hb-border)] bg-[var(--hb-bg)] p-3 transition-colors hover:border-[var(--hb-accent)]"
    >
      <div className="font-medium">{name}</div>
      <div className="mt-2 text-sm text-[var(--hb-muted)]">{address}</div>
    </Link>
  )
}

function formatAddress(project: ProjectSummary): string {
  const address = cleanText(project.address)
  const city = cleanText(project.city)
  const state = cleanText(project.state_code)
  const zip = cleanText(project.zip)
  const region = [state, zip].filter(Boolean).join(' ')
  const locality = [city, region].filter(Boolean).join(', ')

  if (address && locality) return `${address} · ${locality}`
  if (address) return address
  if (locality) return locality
  return 'Address not available'
}

function cleanText(value: string | null | undefined): string | null {
  const text = value?.trim()
  return text || null
}
