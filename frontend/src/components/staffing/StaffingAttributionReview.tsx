import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import type { StaffingConfigRow } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { BTN_CLASS, INPUT_CLASS, canEditStaffing, describeStaffingError } from './staffingShared'

export function StaffingAttributionReview({ project }: { project: string }) {
  const queryClient = useQueryClient()
  const canEdit = canEditStaffing()
  const { data, isLoading, error } = useQuery({
    queryKey: ['staffing', 'unmatched', project],
    queryFn: () => api.getProjectStaffingUnmatched(project),
  })
  const { data: configData } = useQuery({
    queryKey: ['staffing', 'config', project],
    queryFn: () => api.getProjectStaffingConfig(project),
  })

  const [selected, setSelected] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const items = (data?.review_items ?? []) as Record<string, string>[]
  const configRows = (configData?.rows ?? []) as StaffingConfigRow[]

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['staffing', 'unmatched', project] }),
      queryClient.invalidateQueries({ queryKey: ['staffing', 'readiness', project] }),
    ])
  }

  async function rebuild() {
    setBusy(true)
    setActionError(null)
    try {
      await api.rebuildProjectStaffingProjection(project)
      await invalidate()
    } catch (e) {
      setActionError(describeStaffingError(e))
    } finally {
      setBusy(false)
    }
  }

  async function resolve(reviewItemId: string) {
    const configId = selected[reviewItemId]
    if (!configId) {
      setActionError('Choose a staffing row to attribute to.')
      return
    }
    setBusy(true)
    setActionError(null)
    try {
      await api.resolveProjectStaffingReview(project, reviewItemId, { staffing_config_id: configId })
      await invalidate()
    } catch (e) {
      setActionError(describeStaffingError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard title="LAB/LBN actuals review"
      description="Unmatched labor actuals grouped by cost code. Resolve by attributing to a staffing row."
      actions={canEdit && (
        <button type="button" className={BTN_CLASS} disabled={busy} onClick={rebuild}>
          {busy ? 'Working…' : 'Rebuild projection'}
        </button>
      )}>
      {isLoading && <p className="text-sm text-[var(--hb-muted)]">Loading review queue…</p>}
      {error && <p className="text-sm text-rose-300">The review queue is unavailable.</p>}
      {data && (
        <div className="space-y-2">
          {items.length === 0 && <p className="text-sm text-[var(--hb-muted)]">Nothing to review.</p>}
          {actionError && <p className="text-sm text-rose-300">{actionError}</p>}
          <ul className="space-y-2">
            {items.map((it) => (
              <li key={it.review_item_id} className="rounded border border-[var(--hb-border)] p-2 text-sm">
                <div className="font-medium">{it.cost_code} · {it.category}</div>
                <div className="text-xs text-[var(--hb-muted)]">
                  {it.actual_amount} · {it.actuals_start_month} → {it.actuals_through_month}
                  {it.description_label ? ` · ${it.description_label}` : ''}
                </div>
                {canEdit && (
                  <div className="mt-2 flex items-center gap-2">
                    <select aria-label="Staffing row" className={INPUT_CLASS}
                      value={selected[it.review_item_id] ?? ''}
                      onChange={(e) => setSelected((s) => ({ ...s, [it.review_item_id]: e.target.value }))}>
                      <option value="">Choose a staffing row…</option>
                      {configRows.map((r) => (
                        <option key={r.staffing_config_id} value={r.staffing_config_id}>
                          {(r.role_title || 'Role')}{r.person_name ? ` — ${r.person_name}` : ''} ({r.cost_code})
                        </option>
                      ))}
                    </select>
                    <button type="button" className={BTN_CLASS} disabled={busy}
                      onClick={() => resolve(it.review_item_id)}>Attribute</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </SectionCard>
  )
}
