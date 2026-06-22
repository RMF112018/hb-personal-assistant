import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, BarChart3, CheckCircle2, Circle, Database, FileSpreadsheet, LayoutDashboard, Settings2 } from 'lucide-react'

function SummaryCardIcon({ icon: Icon, label }: { icon?: LucideIcon; label: string }) {
  const props = { size: 13, strokeWidth: 2, 'aria-hidden': true as const, className: 'text-[var(--hb-accent)]' }
  if (Icon) return <Icon {...props} />
  const lower = label.toLowerCase()
  if (lower.includes('storage')) return <Database {...props} />
  if (lower.includes('package')) return <FileSpreadsheet {...props} />
  if (lower.includes('config')) return <Settings2 {...props} />
  if (lower.includes('eval')) return <BarChart3 {...props} />
  return <LayoutDashboard {...props} />
}

export function ForecastSummaryGrid({ children }: { children: React.ReactNode }) {
  return <div className="forecast-metric-grid mt-4">{children}</div>
}

export function ForecastSummaryCard({
  label,
  value,
  detail,
  status,
  icon: Icon,
}: {
  label: string
  value: string
  detail?: string
  status?: 'ready' | 'attention' | 'neutral'
  icon?: LucideIcon
}) {
  const statusClass =
    status === 'ready' ? 'is-ready' : status === 'attention' ? 'is-attention' : ''
  const statusColor =
    status === 'ready'
      ? 'text-emerald-400'
      : status === 'attention'
        ? 'text-amber-400'
        : 'text-[var(--hb-muted)]'

  return (
    <div className={`forecast-metric-card ${statusClass}`}>
      <div className="forecast-metric-label">
        <SummaryCardIcon icon={Icon} label={label} />
        {label}
      </div>
      <div className="forecast-metric-value">{value}</div>
      {detail && (
        <div className="forecast-metric-detail flex items-center gap-1.5">
          {status === 'ready' && <CheckCircle2 size={11} className={statusColor} aria-hidden />}
          {status === 'attention' && <AlertTriangle size={11} className={statusColor} aria-hidden />}
          {status === 'neutral' && <Circle size={11} className={statusColor} aria-hidden />}
          <span>{detail}</span>
        </div>
      )}
    </div>
  )
}