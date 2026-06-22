import { useState } from 'react'

import {
  ScheduleActionButton,
  ScheduleActionLink,
  ScheduleBackLink,
  SchedulePageHeader,
  ScheduleShell,
  ScheduleSubnav,
} from '../components/schedule/SchedulePageChrome'
import {
  ScheduleProjectContext,
  ScheduleProjectPicker,
  useScheduleProjects,
} from '../components/schedule/ScheduleProjectPicker'
import { api, ScheduleApiError, ScheduleNetworkError } from '../lib/api'

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024

type DuplicateInfo = {
  schedule_version_key: string
  activity_count: number
  relationship_count: number
  view_path: string
}

function scheduleErrorMessage(err: unknown): string {
  if (err instanceof ScheduleNetworkError) {
    return 'Could not reach the schedule import service. Check that the backend is running and retry.'
  }
  if (err instanceof ScheduleApiError) {
    switch (err.code) {
      case 'schedule_file_too_large':
        return 'This file exceeds the 50 MB upload limit.'
      case 'schedule_schema_not_ready':
        return 'Schedule schema is not current. Apply pending database migrations from Data Health admin controls.'
      case 'schedule_multipart_unavailable':
        return 'Schedule import upload is unavailable. Reinstall analytics-ui dependencies (python-multipart) and restart the backend.'
      case 'unsupported_schedule_format':
        return 'Unsupported schedule format. Use Primavera XML (.xml, .pmxml) or CSV.'
      case 'schedule_parse_failed':
        return 'Could not parse the schedule file. Check that it is valid Primavera XML or CSV.'
      case 'schedule_project_required':
        return 'Select an existing project before uploading or committing a schedule.'
      case 'schedule_project_unknown':
        return 'Selected project is not available for schedule import.'
      case 'schedule_import_invalid':
        return err.message || 'Schedule import request was invalid.'
      default:
        return err.message || 'Schedule import failed.'
    }
  }
  return 'Schedule import failed. Check the file format and try again.'
}

export function ScheduleImportsPage() {
  const [projectKey, setProjectKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [busyAction, setBusyAction] = useState<'preview' | 'commit' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [duplicate, setDuplicate] = useState<DuplicateInfo | null>(null)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [committed, setCommitted] = useState<Record<string, unknown> | null>(null)
  const { data: projectsData } = useScheduleProjects()

  async function onUpload(file: File, confirmSupersede = false) {
    if (!projectKey) {
      setError('Select an existing project before uploading a schedule file.')
      return
    }
    setBusy(true)
    setBusyAction('preview')
    setError(null)
    if (!confirmSupersede) {
      setDuplicate(null)
      setCommitted(null)
      setPreview(null)
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError('This file exceeds the 50 MB upload limit.')
      setBusy(false)
      setBusyAction(null)
      return
    }
    try {
      const resp = await api.uploadScheduleImportPreview(
        file,
        projectKey,
        null,
        confirmSupersede,
      )
      setPreview(resp as Record<string, unknown>)
      setDuplicate(null)
    } catch (err) {
      if (err instanceof ScheduleApiError && err.code === 'duplicate_schedule_version') {
        const p = err.payload
        setDuplicate({
          schedule_version_key: String(p.schedule_version_key ?? ''),
          activity_count: Number(p.activity_count ?? 0),
          relationship_count: Number(p.relationship_count ?? 0),
          view_path: String(p.view_path ?? '/schedules/versions'),
        })
      } else {
        setError(scheduleErrorMessage(err))
      }
    } finally {
      setBusy(false)
      setBusyAction(null)
    }
  }

  async function onCommit(confirmSupersede = false) {
    if (!preview?.import_id || !projectKey) return
    setBusy(true)
    setBusyAction('commit')
    setError(null)
    try {
      const resp = await api.commitScheduleImport(
        String(preview.import_id),
        projectKey,
        null,
        confirmSupersede,
      )
      setCommitted(resp as Record<string, unknown>)
      setDuplicate(null)
    } catch (err) {
      if (err instanceof ScheduleApiError && err.code === 'duplicate_schedule_version') {
        const p = err.payload
        setDuplicate({
          schedule_version_key: String(p.schedule_version_key ?? ''),
          activity_count: Number(p.activity_count ?? 0),
          relationship_count: Number(p.relationship_count ?? 0),
          view_path: String(p.view_path ?? '/schedules/versions'),
        })
      } else {
        setError(scheduleErrorMessage(err))
      }
    } finally {
      setBusy(false)
      setBusyAction(null)
    }
  }

  const findings = Array.isArray(preview?.validation_findings)
    ? (preview.validation_findings as Record<string, string>[])
    : []

  return (
    <ScheduleShell>
      <ScheduleBackLink to="/schedules/versions" label="Schedule versions" />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule imports"
        subtitle="Upload Primavera XML or CSV schedules into the local database after preview and operator confirmation."
        actions={<ScheduleActionLink to="/schedules/versions">View versions</ScheduleActionLink>}
      />

      <div className="forecast-panel p-4 space-y-4 max-w-xl">
        <ScheduleProjectPicker
          value={projectKey}
          onChange={setProjectKey}
          required
          importSelectableOnly
        />
        {projectKey ? (
          <ScheduleProjectContext
            projectKey={projectKey}
            projects={projectsData?.projects}
          />
        ) : null}

        <label className="block text-sm">
          <span className="text-[var(--hb-muted)]">Schedule file (.xml, .csv) — max 50 MB</span>
          <input
            type="file"
            accept=".xml,.csv,.pmxml"
            className="mt-2 block w-full text-sm"
            disabled={busy || !projectKey}
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void onUpload(f)
            }}
          />
        </label>

        {busy && busyAction === 'preview' ? (
          <p className="text-sm text-[var(--hb-muted)]">Previewing schedule…</p>
        ) : null}

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        {duplicate ? (
          <div className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-2">
            <p className="font-medium">This schedule version is already imported for this project.</p>
            <ScheduleProjectContext
              projectKey={projectKey}
              projects={projectsData?.projects}
            />
            <p className="text-[var(--hb-muted)]">Version: {duplicate.schedule_version_key}</p>
            <p>
              Activities: {duplicate.activity_count} · Relationships: {duplicate.relationship_count}
            </p>
            <div className="flex flex-wrap gap-2">
              <ScheduleActionLink to={duplicate.view_path}>View existing activities</ScheduleActionLink>
              <ScheduleActionButton
                onClick={() => {
                  const input = document.querySelector('input[type="file"]') as HTMLInputElement | null
                  const file = input?.files?.[0]
                  if (file) void onUpload(file, true)
                }}
                disabled={busy}
              >
                Preview supersede
              </ScheduleActionButton>
              {preview ? (
                <ScheduleActionButton onClick={() => void onCommit(true)} disabled={busy}>
                  Commit supersede
                </ScheduleActionButton>
              ) : null}
            </div>
          </div>
        ) : null}

        {preview ? (
          <div className="space-y-2 text-sm">
            <ScheduleProjectContext
              projectKey={String(preview.project_key ?? projectKey)}
              projects={projectsData?.projects}
            />
            {preview.schedule_name ? (
              <p className="font-medium">{String(preview.schedule_name)}</p>
            ) : null}
            <p className="text-[var(--hb-muted)]">
              Format: {String(preview.source_format)} · Cost loaded: {String(preview.cost_loaded_status)}
              {preview.data_date ? ` · Data date: ${String(preview.data_date)}` : ''}
            </p>
            <p>
              Activities: {String(preview.activity_count)} · Relationships:{' '}
              {String(preview.relationship_count)}
            </p>
            <p>
              WBS: {String(preview.wbs_count)} · Calendars: {String(preview.calendar_count)}
            </p>
            {findings.length > 0 ? (
              <ul className="list-disc pl-5 text-[var(--hb-muted)]">
                {findings.map((f, i) => (
                  <li key={i}>
                    {String(f.severity || 'info')}: {String(f.message || f.code || '')}
                  </li>
                ))}
              </ul>
            ) : null}
            {Boolean(preview.requires_column_mapping) ? (
              <p className="text-[var(--hb-muted)]">CSV uploads require column mapping before commit.</p>
            ) : null}
            <ScheduleActionButton onClick={() => void onCommit()} disabled={busy || !projectKey}>
              {busy && busyAction === 'commit' ? 'Committing…' : 'Commit import to database'}
            </ScheduleActionButton>
          </div>
        ) : null}

        {committed ? (
          <div className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-2">
            <p className="font-medium">Import committed</p>
            <ScheduleProjectContext
              projectKey={String(committed.project_key ?? projectKey)}
              projects={projectsData?.projects}
            />
            <p>Version: {String(committed.schedule_version_key)}</p>
            <ScheduleActionLink
              to={`/schedules/activities?version=${encodeURIComponent(String(committed.schedule_version_key))}&project=${encodeURIComponent(String(committed.project_key ?? projectKey))}`}
            >
              Browse activities
            </ScheduleActionLink>
          </div>
        ) : null}
      </div>
    </ScheduleShell>
  )
}