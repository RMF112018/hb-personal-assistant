import { ConfidenceBadge, FreshnessBadge } from '../ui/Badge'
import { MyItemsSettingsLink, MyItemsTodayLink } from './MyItemsActions'

type MyItemsStatusRowProps = {
  freshness?: { overall?: string; minutes_ago_max?: number | null }
  confidence?: { overall?: string }
  itemCount?: number
}

export function MyItemsStatusRow({ freshness, confidence, itemCount = 0 }: MyItemsStatusRowProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <FreshnessBadge status={asFreshness(freshness?.overall)} minutesAgo={freshness?.minutes_ago_max} />
      <ConfidenceBadge level={asConfidence(confidence?.overall)} />
      <span className="text-xs text-[var(--hb-muted)]">{itemCount} items</span>
      <MyItemsTodayLink />
      <MyItemsSettingsLink />
    </div>
  )
}

function asFreshness(status?: string): 'fresh' | 'stale' | 'unknown' {
  if (status === 'fresh' || status === 'stale') return status
  return 'unknown'
}

function asConfidence(level?: string): 'source_backed' | 'not_available' | 'in_progress' {
  if (level === 'source_backed' || level === 'in_progress') return level
  return 'not_available'
}
