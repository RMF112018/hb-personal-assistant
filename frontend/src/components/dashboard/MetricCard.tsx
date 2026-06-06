
export function MetricCard({ label, value, unit, status }: { label: string; value: number | string; unit?: string; status?: 'ok' | 'attention' | 'warn' }) {
  const tone = status === 'attention' ? 'text-amber-300' : status === 'warn' ? 'text-orange-300' : 'text-[var(--hb-text)]'
  return (
    <div className="card">
      <div className="text-xs text-[var(--hb-muted)]">{label}</div>
      <div className={`text-2xl font-semibold tabular-nums mt-1 ${tone}`}>{value}</div>
      {unit && <div className="text-xs text-[var(--hb-muted)]">{unit}</div>}
    </div>
  )
}
