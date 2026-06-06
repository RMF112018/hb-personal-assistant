
export function FreshnessBadge({ status, minutesAgo, compact = false }: { status: 'fresh' | 'stale' | 'unknown'; minutesAgo?: number | null; compact?: boolean }) {
  const label = status === 'fresh' ? 'Fresh' : status === 'stale' ? 'Stale' : 'Unknown'
  const cls = status === 'fresh' ? 'badge-fresh' : status === 'stale' ? 'badge-stale' : 'badge-muted'
  return (
    <span className={`badge ${cls} ${compact ? 'text-[10px] px-1.5 py-0' : ''}`} title={minutesAgo != null ? `${minutesAgo}m ago` : undefined}>
      {label}{minutesAgo != null && !compact ? ` • ${minutesAgo}m` : ''}
    </span>
  )
}

export function ConfidenceBadge({ level }: { level: 'source_backed' | 'not_available' | 'in_progress' }) {
  const label = level === 'source_backed' ? 'Source-backed' : level === 'not_available' ? 'Limited data' : 'Building'
  return <span className="badge badge-confidence">{label}</span>
}
