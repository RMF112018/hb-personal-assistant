import { useEffect } from 'react'
import { FreshnessBadge, ConfidenceBadge } from '../ui/Badge'
import { CheckDataHealthLink } from './TodayActions'
import { useHeaderNotifications } from '../../layouts/HeaderNotificationsContext'

type TodayStatusRowProps = {
  freshness?: { overall?: 'fresh' | 'stale' | 'unknown'; minutes_ago_max?: number | null }
  confidence?: { overall?: 'source_backed' | 'not_available' | 'in_progress' }
  projectCount?: number | string | null
}

export function TodayStatusRow({ freshness, confidence, projectCount }: TodayStatusRowProps) {
  const { setNotifications } = useHeaderNotifications()

  // Publish compact quality chips to the shell chrome header as notifications/warnings.
  // The body status row now focuses on the count + primary action; quality indicators live in chrome.
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
      <CheckDataHealthLink />
    </div>
  )
}
