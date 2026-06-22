import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'

export function useScheduleVersions(projectKey?: string) {
  return useQuery({
    queryKey: ['schedules', 'versions', projectKey ?? '__all__'],
    queryFn: () =>
      projectKey
        ? api.getScheduleVersions(projectKey)
        : api.listScheduleVersions(),
  })
}

export function ScheduleVersionPicker({
  projectKey,
  value,
  onChange,
  label = 'Schedule version',
}: {
  projectKey: string
  value: string
  onChange: (versionKey: string) => void
  label?: string
}) {
  const { data, isLoading } = useScheduleVersions(projectKey || undefined)
  const versions = Array.isArray(data) ? (data as Record<string, unknown>[]) : []

  return (
    <label className="block text-sm">
      <span className="text-[var(--hb-muted)]">{label}</span>
      <select
        className="mt-1 block w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5 text-sm"
        value={value}
        disabled={!projectKey || isLoading || versions.length === 0}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{isLoading ? 'Loading versions…' : 'Select a version'}</option>
        {versions.map((v) => (
          <option key={String(v.schedule_version_key)} value={String(v.schedule_version_key)}>
            {String(v.display_label)} ({String(v.activity_count)} activities)
          </option>
        ))}
      </select>
    </label>
  )
}