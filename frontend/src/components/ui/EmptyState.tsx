
export function EmptyState({ title = 'No data', hint }: { title?: string; hint?: string }) {
  return (
    <div className="card text-sm text-[var(--hb-muted)]">
      {title}
      {hint && <div className="text-xs mt-1">{hint}</div>}
    </div>
  )
}
