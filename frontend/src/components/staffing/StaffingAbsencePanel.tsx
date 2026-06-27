import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { BTN_CLASS, INPUT_CLASS, canEditStaffing, describeStaffingError } from './staffingShared'

type Form = { person_name: string; start_date: string; finish_date: string; absence_hours: string }
const EMPTY: Form = { person_name: '', start_date: '', finish_date: '', absence_hours: '' }

export function StaffingAbsencePanel({ project }: { project: string }) {
  const queryClient = useQueryClient()
  const canEdit = canEditStaffing()
  const { data, isLoading, error } = useQuery({
    queryKey: ['staffing', 'absences', project],
    queryFn: () => api.getProjectStaffingAbsences(project),
  })

  const [form, setForm] = useState<Form>(EMPTY)
  const [busy, setBusy] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const set = (k: keyof Form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ['staffing', 'absences', project] })
  }

  async function onCreate() {
    setBusy(true)
    setSaveError(null)
    try {
      const resp = (await api.createProjectStaffingAbsence(project, { ...form })) as {
        ok?: boolean
        errors?: { message?: string }[]
      }
      if (resp && resp.ok === false) {
        setSaveError(resp.errors?.[0]?.message || 'That absence is not valid.')
        return
      }
      setForm(EMPTY)
      await invalidate()
    } catch (e) {
      setSaveError(describeStaffingError(e))
    } finally {
      setBusy(false)
    }
  }

  const rows = (data?.rows ?? []) as Record<string, string>[]

  return (
    <SectionCard title="Absence overrides"
      description="Full-Time absences reduce calculated time during the selected window (employee-scoped).">
      {isLoading && <p className="text-sm text-[var(--hb-muted)]">Loading absences…</p>}
      {error && <p className="text-sm text-rose-300">Absences are unavailable.</p>}
      {data && (
        <div className="space-y-3">
          {rows.length === 0 && <p className="text-sm text-[var(--hb-muted)]">No absences recorded.</p>}
          <ul className="space-y-1 text-sm">
            {rows.map((r) => (
              <li key={r.absence_override_id} className="flex items-center justify-between gap-3">
                <span>
                  {r.person_name || 'Assigned row'} · {r.start_date} → {r.finish_date} ·{' '}
                  {r.absence_hours}h
                </span>
                {canEdit && (
                  <button type="button" className={BTN_CLASS} disabled={busy}
                    onClick={async () => {
                      setBusy(true)
                      try {
                        await api.deleteProjectStaffingAbsence(project, r.absence_override_id)
                        await invalidate()
                      } finally { setBusy(false) }
                    }}>Remove</button>
                )}
              </li>
            ))}
          </ul>
          {canEdit && (
            <div className="space-y-2 border-t border-[var(--hb-border)] pt-3">
              <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                <input aria-label="Person" placeholder="Person" className={INPUT_CLASS}
                  value={form.person_name} onChange={(e) => set('person_name')(e.target.value)} />
                <input aria-label="Absence start" type="date" className={INPUT_CLASS}
                  value={form.start_date} onChange={(e) => set('start_date')(e.target.value)} />
                <input aria-label="Absence finish" type="date" className={INPUT_CLASS}
                  value={form.finish_date} onChange={(e) => set('finish_date')(e.target.value)} />
                <input aria-label="Absence hours" placeholder="Hours" className={INPUT_CLASS}
                  value={form.absence_hours} onChange={(e) => set('absence_hours')(e.target.value)} />
              </div>
              <div className="flex items-center gap-3">
                <button type="button" className={BTN_CLASS} disabled={busy} onClick={onCreate}>
                  {busy ? 'Saving…' : 'Add absence'}
                </button>
                {saveError && <span className="text-sm text-rose-300">{saveError}</span>}
              </div>
            </div>
          )}
        </div>
      )}
    </SectionCard>
  )
}
