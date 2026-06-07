import { safeDisplayText } from '../../lib/errorCopy'

type MyWorkQueueItemProps = {
  item: unknown
}

export function MyWorkQueueItem({ item }: MyWorkQueueItemProps) {
  const details = asItemDetails(item)
  const meta = [details.project, details.when].filter(Boolean).join(' • ')

  return (
    <li className="rounded-md border border-[var(--hb-border)] bg-[var(--hb-bg)] px-3 py-2 text-sm hover:border-[var(--hb-accent)] transition-colors">
      <div className="font-medium">{safeDisplayText(item)}</div>
      {meta && <div className="mt-1 text-xs text-[var(--hb-muted)]">{meta}</div>}
    </li>
  )
}

function asItemDetails(item: unknown) {
  if (!item || typeof item !== 'object') return {}
  const candidate = item as Record<string, unknown>
  return {
    project: stringValue(candidate.project),
    when: stringValue(candidate.age) || stringValue(candidate.when),
  }
}

function stringValue(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}
