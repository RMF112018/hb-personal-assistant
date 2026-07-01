/* eslint-disable @typescript-eslint/no-explicit-any */
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api, getLocalUiRole } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'

function text(value: unknown, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

export type ScheduleBaselineSelectorProps = {
  projectKey: string
  baselines?: Record<string, any>
  loading?: boolean
  asOf?: string
}

export function ScheduleBaselineSelector({ projectKey, baselines, loading = false, asOf }: ScheduleBaselineSelectorProps) {
  const queryClient = useQueryClient()
  const canEdit = getLocalUiRole() === 'operator' || getLocalUiRole() === 'admin'

  const mutation = useMutation({
    mutationFn: (payload: { slotKey: string; versionKey: string | null; displayName?: string }) =>
      api.updateProjectScheduleBaselines(
        projectKey,
        {
          selections: {
            [payload.slotKey]: payload.versionKey
              ? {
                  schedule_version_key: payload.versionKey,
                  display_name: payload.displayName,
                }
              : null,
          },
        },
        { asOf: asOf || undefined },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', projectKey, 'baselines'] })
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', 'controls', projectKey] })
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', 'review-items', projectKey] })
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', projectKey] })
    },
  })

  if (loading) {
    return (
      <SectionCard title="Baseline Anchors">
        <p className="text-sm text-[var(--hb-muted)]">Loading baseline selections...</p>
      </SectionCard>
    )
  }

  if (!baselines?.available) {
    return null
  }

  const versions = Array.isArray(baselines.available_versions) ? baselines.available_versions : []
  const slots = Array.isArray(baselines.slots) ? baselines.slots : []

  return (
    <SectionCard title="Baseline Anchors">
      <p className="mb-3 text-xs text-[var(--hb-muted)]">
        Assign prior schedule versions to named comparison anchors for Schedule Controls.
      </p>
      <div className="space-y-3">
        {slots.map((slot: any) => {
          const slotKey = String(slot.slot_key || '')
          const label = text(slot.slot_label, slotKey)
          const selection = slot.selection || null
          const status = String(slot.status || 'missing')
          const selectedKey = selection?.schedule_version_key ? String(selection.schedule_version_key) : ''
          return (
            <div key={slotKey} className="rounded border border-[var(--hb-border)] p-3">
              <div className="text-sm font-medium">{label}</div>
              {status === 'missing' && (
                <p className="mt-1 text-sm text-[var(--hb-muted)]">No {label} selected.</p>
              )}
              {status === 'selected' && selection && (
                <p className="mt-1 text-sm text-[var(--hb-muted)]">
                  {text(selection.display_name)} · data date {text(selection.schedule_data_date)}
                </p>
              )}
              {status === 'invalid' && (
                <p className="mt-1 text-sm text-amber-400">Selected baseline is invalid for the current as-of context.</p>
              )}
              {canEdit ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <select
                    className="rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
                    value={selectedKey}
                    onChange={(event) => {
                      const value = event.target.value
                      const version = versions.find((row: any) => String(row.schedule_version_key) === value)
                      mutation.mutate({
                        slotKey,
                        versionKey: value || null,
                        displayName: version ? String(version.display_name || '') : undefined,
                      })
                    }}
                  >
                    <option value="">Clear selection</option>
                    {versions
                      .filter((row: any) => row.eligible_baseline)
                      .map((row: any) => (
                        <option key={String(row.schedule_version_key)} value={String(row.schedule_version_key)}>
                          {text(row.schedule_data_date)} · {text(row.display_name || row.source_label)}
                        </option>
                      ))}
                  </select>
                </div>
              ) : (
                <p className="mt-2 text-xs text-[var(--hb-muted)]">Viewer access: selections are read-only.</p>
              )}
            </div>
          )
        })}
      </div>
    </SectionCard>
  )
}
