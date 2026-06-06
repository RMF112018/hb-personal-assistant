
export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {subtitle && <p className="text-sm text-[var(--hb-muted)]">{subtitle}</p>}
      <div className="advisory mt-1">
        Advisory signal only. No legal, financial, schedule, safety or entitlement determinations.
      </div>
    </div>
  )
}
