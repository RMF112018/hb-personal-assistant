import { AlertTriangle, Ban, CheckCircle2, CircleDashed, HelpCircle, XCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const STATUS_LABEL: Record<string, { label: string; cls: string; icon: LucideIcon }> = {
  validated: {
    label: 'Ready',
    cls: 'text-emerald-300 border-emerald-700/80 bg-emerald-950/30',
    icon: CheckCircle2,
  },
  attention: {
    label: 'Needs attention',
    cls: 'text-amber-300 border-amber-700/80 bg-amber-950/25',
    icon: AlertTriangle,
  },
  invalid: {
    label: 'Unreadable',
    cls: 'text-rose-300 border-rose-700/80 bg-rose-950/25',
    icon: XCircle,
  },
  // Generation run/request outcomes — accurate copy for a request that ran but did not complete
  // (failed) or was refused before running (rejected). Kept distinct from `invalid`/"Unreadable",
  // which other readiness/confidence/health surfaces still rely on.
  failed: {
    label: 'Failed',
    cls: 'text-rose-300 border-rose-700/80 bg-rose-950/25',
    icon: XCircle,
  },
  rejected: {
    label: 'Rejected',
    cls: 'text-amber-300 border-amber-700/80 bg-amber-950/25',
    icon: Ban,
  },
  unsupported: {
    label: 'Unsupported',
    cls: 'text-[var(--hb-muted)] border-[var(--hb-border)] bg-[var(--hb-bg)]/40',
    icon: CircleDashed,
  },
  unknown: {
    label: 'Unknown',
    cls: 'text-[var(--hb-muted)] border-[var(--hb-border)] bg-[var(--hb-bg)]/40',
    icon: HelpCircle,
  },
}

/** Consistent advisory status badge across forecasting surfaces. */
export function ForecastStatusPill({ status }: { status: string }) {
  const s = STATUS_LABEL[status] || STATUS_LABEL.unknown
  const Icon = s.icon
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[0.68rem] font-medium tracking-wide ${s.cls}`}
    >
      <Icon size={11} strokeWidth={2.5} aria-hidden />
      {s.label}
    </span>
  )
}