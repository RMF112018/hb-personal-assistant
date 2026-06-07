export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return <div className="p-6 text-sm text-[var(--hb-muted)]">{label}</div>
}
