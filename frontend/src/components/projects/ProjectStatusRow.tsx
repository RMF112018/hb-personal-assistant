import { useEffect } from 'react'
import { ConfidenceBadge, FreshnessBadge } from '../ui/Badge'
import { ProjectConnectionsLink } from './ProjectActions'
import { useHeaderNotifications } from '../../layouts/HeaderNotificationsContext'

type ProjectStatusRowProps = {
  freshness?: { overall?: 'fresh' | 'stale' | 'unknown'; minutes_ago_max?: number | null }
  confidence?: { overall?: 'source_backed' | 'not_available' | 'in_progress' }
  projectCount?: number | string | null
}

export function ProjectStatusRow({ freshness, confidence, projectCount }: ProjectStatusRowProps) {
  const { setNotifications } = useHeaderNotifications()

  useEffect(() => {
    setNotifications(
      <>
        <FreshnessBadge status={freshness?.overall || 'unknown'} minutesAgo={freshness?.minutes_ago_max} compact />
        <ConfidenceBadge level={confidence?.overall || 'not_available'} />
      </>
    )
    return () => setNotifications(null)
  }, [freshness?.overall, freshness?.minutes_ago_max, confidence?.overall, setNotifications])

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-[var(--hb-muted)]">{projectCount ?? '—'} projects</span>
      <ProjectConnectionsLink />
    </div>
  )
}
