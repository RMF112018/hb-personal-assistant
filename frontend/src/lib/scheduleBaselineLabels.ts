import type { ReviewWorkbenchComparisonBasis, ScheduleControlsComparisonBasis } from './api'

const SLOT_LABELS: Record<string, string> = {
  prior_update: 'Prior Update',
  baseline: 'Selected Baseline',
  current_contract_baseline: 'Current Contract Baseline',
  previous_progress_update_baseline: 'Previous Progress Update Baseline',
  secondary_progress_update_baseline: 'Secondary Progress Update Baseline',
}

export const SCHEDULE_CONTROLS_COMPARISON_BASIS_VALUES: readonly ScheduleControlsComparisonBasis[] = [
  'prior_update',
  'current_contract_baseline',
  'previous_progress_update_baseline',
  'secondary_progress_update_baseline',
] as const

export function labelForComparisonBasis(basis: string): string {
  return SLOT_LABELS[basis] || basis.replace(/_/g, ' ')
}

export function isAllowedControlsComparisonBasis(
  basis: string,
): basis is ScheduleControlsComparisonBasis | 'baseline' {
  return (
    basis === 'prior_update' ||
    basis === 'baseline' ||
    SCHEDULE_CONTROLS_COMPARISON_BASIS_VALUES.includes(basis as ScheduleControlsComparisonBasis)
  )
}

export type NormalizedBaselineContext = {
  slotLabel: string | null
  versionKey: string | null
  dataDate: string | null
  displayName: string | null
  selectionStatus: string | null
}

export function normalizeBaselineContext(ctx: Record<string, unknown> | null | undefined): NormalizedBaselineContext {
  if (!ctx) {
    return { slotLabel: null, versionKey: null, dataDate: null, displayName: null, selectionStatus: null }
  }
  return {
    slotLabel: (ctx.slot_label as string) || null,
    versionKey:
      (ctx.schedule_version_key as string) || (ctx.baseline_schedule_version_key as string) || null,
    dataDate: (ctx.schedule_data_date as string) || (ctx.baseline_schedule_data_date as string) || null,
    displayName: (ctx.display_name as string) || (ctx.baseline_display_name as string) || null,
    selectionStatus: (ctx.selection_status as string) || null,
  }
}

export function formatBaselineSelectionSummary(opts: {
  displayName?: string | null
  dataDate?: string | null
}): string {
  const name = opts.displayName?.trim() || null
  const date = opts.dataDate?.trim() || null
  if (date && name) return `${date} · ${name}`
  if (name) return name
  if (date) return `Data date ${date}`
  return '—'
}

export function formatNamedComparisonContextLine(opts: {
  slotLabel?: string | null
  displayName?: string | null
  dataDate?: string | null
  asOf?: string | null
}): string {
  const slot = opts.slotLabel?.trim() || 'Comparison anchor'
  const anchor = formatBaselineSelectionSummary({ displayName: opts.displayName, dataDate: opts.dataDate })
  const parts = [`Comparing against ${slot}`]
  if (anchor !== '—') parts.push(anchor)
  if (opts.asOf) parts.push(`As of ${opts.asOf}`)
  return parts.join(' · ')
}

export function workbenchHref(
  projectKey: string,
  opts?: { asOf?: string; comparisonBasis?: ReviewWorkbenchComparisonBasis | 'baseline' },
): string {
  const params = new URLSearchParams()
  if (opts?.comparisonBasis && opts.comparisonBasis !== 'prior_update') {
    params.set('comparison_basis', opts.comparisonBasis)
  }
  if (opts?.asOf) params.set('as_of', opts.asOf)
  const qs = params.toString()
  return `/projects/${projectKey}/schedule/workbench${qs ? `?${qs}` : ''}`
}

export function driverDetailHref(
  projectKey: string,
  activityId: string,
  opts?: { asOf?: string; comparisonBasis?: ReviewWorkbenchComparisonBasis | 'baseline' },
): string {
  const params = new URLSearchParams()
  params.set('activity_id', activityId)
  if (opts?.comparisonBasis) {
    params.set('comparison_basis', opts.comparisonBasis)
  }
  if (opts?.asOf) params.set('as_of', opts.asOf)
  return `/projects/${projectKey}/schedule/driver-detail?${params.toString()}`
}
