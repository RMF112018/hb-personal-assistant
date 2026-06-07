export function timeAgo(input: string | Date | null | undefined): string {
  if (!input) return '—'
  const d = input instanceof Date ? input : new Date(input)
  if (isNaN(d.getTime())) return '—'
  const diffMs = Date.now() - d.getTime()
  if (diffMs < 0) return 'just now'
  const sec = Math.floor(diffMs / 1000)
  if (sec < 60) return 'just now'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day === 1) return 'yesterday'
  if (day < 7) return `${day}d ago`
  return `${day}d ago`
}

export function formatLastUpdate(dateStr?: string | null): string {
  return `Last local update: ${timeAgo(dateStr)}`
}
