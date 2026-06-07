import { safeDisplayText } from '../../lib/errorCopy'

type TodayListProps = {
  items: unknown[]
  limit?: number
  fallback?: string
}

export function TodayList({ items, limit = 6, fallback = 'Details unavailable' }: TodayListProps) {
  if (items.length === 0) return null
  return (
    <ul className="space-y-2 text-sm">
      {items.slice(0, limit).map((item, index) => (
        <li key={itemKey(item, index)} className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-3 py-2">
          {safeDisplayText(item, fallback)}
        </li>
      ))}
    </ul>
  )
}

function itemKey(item: unknown, index: number): string {
  if (item && typeof item === 'object') {
    const record = item as Record<string, unknown>
    const id = record.id || record.key || record.title || record.name || record.subject
    if (typeof id === 'string' || typeof id === 'number') return String(id)
  }
  return `item-${index}`
}
