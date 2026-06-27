import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { BTN_CLASS, INPUT_CLASS, canEditStaffing, describeStaffingError } from './staffingShared'

type Form = {
  hours_per_business_day: string
  business_days_per_week: string
  full_time_hours_per_week: string
  holiday_calendar_id: string
}

function AssumptionsForm({
  project, initial, calendars, canEdit,
}: {
  project: string
  initial: Form
  calendars: Record<string, string>[]
  canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<Form>(initial)
  const [busy, setBusy] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const set = (k: keyof Form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  async function onSave() {
    setBusy(true)
    setSaveError(null)
    setSaved(false)
    try {
      const resp = (await api.updateProjectStaffingAssumptions(project, {
        ...form,
        holiday_calendar_id: form.holiday_calendar_id || null,
      })) as { ok?: boolean; errors?: { message?: string }[] }
      if (resp && resp.ok === false) {
        setSaveError(resp.errors?.[0]?.message || 'Those assumptions are not valid.')
        return
      }
      setSaved(true)
      await queryClient.invalidateQueries({ queryKey: ['staffing', 'assumptions', project] })
    } catch (e) {
      setSaveError(describeStaffingError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <input aria-label="Hours per business day" className={INPUT_CLASS} disabled={!canEdit}
          value={form.hours_per_business_day} onChange={(e) => set('hours_per_business_day')(e.target.value)} />
        <input aria-label="Business days per week" className={INPUT_CLASS} disabled={!canEdit}
          value={form.business_days_per_week} onChange={(e) => set('business_days_per_week')(e.target.value)} />
        <input aria-label="Full-time hours per week" className={INPUT_CLASS} disabled={!canEdit}
          value={form.full_time_hours_per_week} onChange={(e) => set('full_time_hours_per_week')(e.target.value)} />
        <select aria-label="Holiday calendar" className={INPUT_CLASS} disabled={!canEdit}
          value={form.holiday_calendar_id} onChange={(e) => set('holiday_calendar_id')(e.target.value)}>
          <option value="">No holiday calendar</option>
          {calendars.map((c) => (
            <option key={c.holiday_calendar_id} value={c.holiday_calendar_id}>{c.calendar_name}</option>
          ))}
        </select>
      </div>
      {canEdit && (
        <div className="flex items-center gap-3">
          <button type="button" className={BTN_CLASS} disabled={busy} onClick={onSave}>
            {busy ? 'Saving…' : 'Save assumptions'}
          </button>
          {saved && <span className="text-sm text-emerald-300">Saved.</span>}
          {saveError && <span className="text-sm text-rose-300">{saveError}</span>}
        </div>
      )}
    </div>
  )
}

export function StaffingAssumptionsPanel({ project }: { project: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['staffing', 'assumptions', project],
    queryFn: () => api.getProjectStaffingAssumptions(project),
  })
  const { data: calData } = useQuery({
    queryKey: ['staffing', 'holiday-calendars'],
    queryFn: () => api.getForecastHolidayCalendars(),
  })

  const a = data?.assumptions as Record<string, string | null> | undefined
  const calendars = (calData?.calendars ?? []) as Record<string, string>[]

  return (
    <SectionCard title="Staffing assumptions"
      description="Hours basis and holiday calendar used to prorate staffing.">
      {isLoading && <p className="text-sm text-[var(--hb-muted)]">Loading assumptions…</p>}
      {error && <p className="text-sm text-rose-300">Assumptions are unavailable.</p>}
      {a && (
        <AssumptionsForm
          key={project}
          project={project}
          canEdit={canEditStaffing()}
          calendars={calendars}
          initial={{
            hours_per_business_day: String(a.hours_per_business_day ?? ''),
            business_days_per_week: String(a.business_days_per_week ?? ''),
            full_time_hours_per_week: String(a.full_time_hours_per_week ?? ''),
            holiday_calendar_id: String(a.holiday_calendar_id ?? ''),
          }}
        />
      )}
    </SectionCard>
  )
}
