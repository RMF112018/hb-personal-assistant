/* Shared helpers for the Project Staffing UI (Phase 4). */
import { getLocalUiRole } from '../../lib/api'

export const INPUT_CLASS =
  'w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm'
export const BTN_CLASS =
  'rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm disabled:opacity-50'

export function canEditStaffing(): boolean {
  const role = getLocalUiRole()
  return role === 'operator' || role === 'admin'
}

export function describeStaffingError(e: unknown): string {
  const message = e instanceof Error ? e.message : ''
  if (message.includes('operator_role_required')) return 'Operator access is required to save.'
  if (message.includes('forecast_staffing_not_available')) return 'Staffing data is not available.'
  return 'Could not save. Please try again.'
}

/** Humanize a coded reason/error label for display (no raw snake_case in the UI). */
export function humanizeCode(code: string): string {
  return code.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}
