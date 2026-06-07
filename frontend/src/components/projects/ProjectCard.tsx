import { Link } from 'react-router-dom'

import { safeDisplayText } from '../../lib/errorCopy'
import { FreshnessBadge } from '../ui/Badge'

type ProjectCardProps = {
  project: Record<string, unknown>
  fallbackKey: string
}

export function ProjectCard({ project, fallbackKey }: ProjectCardProps) {
  const key = String(project.key || project.project_key || project.id || fallbackKey)
  const name = safeDisplayText(project, key)
  const status = typeof project.status === 'string' ? project.status : 'active'
  const freshness = project.freshness || project.freshness_status
  const freshnessStatus = typeof freshness === 'string'
    ? freshness
    : freshness && typeof freshness === 'object' && 'overall' in freshness
      ? String((freshness as { overall?: unknown }).overall || 'unknown')
      : 'unknown'

  return (
    <Link
      to={`/projects/${encodeURIComponent(key)}`}
      className="block rounded-md border border-[var(--hb-border)] bg-[var(--hb-bg)] p-3 hover:border-[var(--hb-accent)]"
    >
      <div className="font-medium">{name}</div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--hb-muted)]">
        <span className="badge">{status}</span>
        <FreshnessBadge status={asFreshness(freshnessStatus)} compact />
      </div>
    </Link>
  )
}

function asFreshness(status: string): 'fresh' | 'stale' | 'unknown' {
  if (status === 'fresh' || status === 'stale') return status
  return 'unknown'
}
