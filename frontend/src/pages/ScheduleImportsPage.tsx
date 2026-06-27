import { useEffect, useState } from 'react'

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

type PackageFile = {
  filename: string
  source_format: string
  parse_status: string
  detected_activities: number
  detected_baseline_projects: number
  warnings: { code?: string; message?: string }[]
}

type PackageCandidate = {
  source_file_id: string
  project_id: string | null
  project_name: string | null
  data_date?: string | null
  activity_count: number
  source_format: string
}

type PackageWarning = { code?: string; filename?: string; message?: string }

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
        return 'Unsupported schedule format. Use Primavera XER, Primavera XML/PMXML, Microsoft Project XML, or CSV with operator mapping.'
      case 'schedule_zip_invalid':
        return 'This .zip package could not be opened. Re-export the package and try again.'
      case 'schedule_zip_too_many_files':
        return 'This .zip package has too many files. Keep it to the schedule files (and any baseline) and retry.'
      case 'schedule_zip_unsafe_path':
        return 'This .zip package contains an unsafe file path and was rejected.'
      case 'schedule_zip_nested_archive':
        return 'This .zip package contains another archive. Unzip it and upload the schedule files directly.'
      case 'schedule_zip_too_large':
        return 'This .zip package is too large once decompressed (150 MB limit). Upload a single schedule file instead.'
      case 'schedule_zip_read_failed':
        return 'A file inside this .zip package could not be read. Re-export the package and retry.'
      case 'schedule_package_no_valid_files':
        return 'This .zip package did not contain a readable Primavera XER, XML/PMXML, MS Project XML, or mapped CSV schedule.'
      case 'schedule_current_project_required':
        return 'This package did not contain a selectable current schedule. Include the current XER or XML schedule file.'
      case 'schedule_package_multiple_current_candidates':
        return 'This .zip package contains more than one current schedule (different data dates). Upload a single current schedule file, or a package that pairs one schedule with its baseline.'
      case 'schedule_parse_failed':
        return 'Could not parse the schedule file. Check that it is valid Primavera XER, Primavera XML/PMXML, Microsoft Project XML, or mapped CSV.'
      case 'schedule_project_required':
        return 'Select an existing project before uploading or committing a schedule.'
      case 'schedule_project_unknown':
        return 'Selected project is not available for schedule import.'
      case 'schedule_import_invalid':
        return err.message || 'Schedule import request was invalid.'
      case 'schedule_project_mismatch':
        return 'Selected project no longer matches the preview. Re-upload the file for the intended project.'
      case 'schedule_import_persistence_failed':
        return 'Schedule import could not be saved completely. No partial version was committed.'
      case 'duplicate_schedule_version':
        return 'This schedule version already exists. Preview supersede before committing.'
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
  const [ambiguousCandidates, setAmbiguousCandidates] = useState<PackageCandidate[] | null>(null)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [previewProjectKey, setPreviewProjectKey] = useState('')
  const [previewIsSupersede, setPreviewIsSupersede] = useState(false)
  const [committed, setCommitted] = useState<Record<string, unknown> | null>(null)
  const { data: projectsData } = useScheduleProjects()
  const committedIdentityMatch =
    committed?.identity_match && typeof committed.identity_match === 'object'
      ? (committed.identity_match as Record<string, unknown>)
      : {}
  const committedComparisonBasis =
    committed?.comparison_basis && typeof committed.comparison_basis === 'object'
      ? (committed.comparison_basis as Record<string, unknown>)
      : {}

  useEffect(() => {
    if (!previewProjectKey || projectKey === previewProjectKey) return
    setPreview(null)
    setPreviewProjectKey('')
    setPreviewIsSupersede(false)
    setDuplicate(null)
    setAmbiguousCandidates(null)
  }, [projectKey, previewProjectKey])

  async function onUpload(file: File, confirmSupersede = false) {
    if (!projectKey) {
      setError('Select an existing project before uploading a schedule file.')
      return
    }
    setBusy(true)
    setBusyAction('preview')
    setError(null)
    setAmbiguousCandidates(null)
    if (!confirmSupersede) {
      setDuplicate(null)
      setCommitted(null)
      setPreview(null)
      setPreviewIsSupersede(false)
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
      const body = resp as Record<string, unknown>
      setPreview(body)
      setPreviewProjectKey(String(body.project_key ?? projectKey))
      setPreviewIsSupersede(confirmSupersede)
      if (!confirmSupersede) {
        setDuplicate(null)
      }
    } catch (err) {
      if (err instanceof ScheduleApiError && err.code === 'duplicate_schedule_version') {
        const p = err.payload
        setDuplicate({
          schedule_version_key: String(p.schedule_version_key ?? ''),
          activity_count: Number(p.activity_count ?? 0),
          relationship_count: Number(p.relationship_count ?? 0),
          view_path: String(p.view_path ?? '/schedules/versions'),
        })
      } else if (
        err instanceof ScheduleApiError &&
        err.code === 'schedule_package_multiple_current_candidates'
      ) {
        const cands = Array.isArray(err.payload.candidates)
          ? (err.payload.candidates as PackageCandidate[])
          : []
        setAmbiguousCandidates(cands)
        setError(scheduleErrorMessage(err))
      } else {
        setError(scheduleErrorMessage(err))
      }
    } finally {
      setBusy(false)
      setBusyAction(null)
    }
  }

  async function onCommit(confirmSupersede = false) {
    if (!preview?.import_id || !previewProjectKey) return
    setBusy(true)
    setBusyAction('commit')
    setError(null)
    try {
      const resp = await api.commitScheduleImport(
        String(preview.import_id),
        previewProjectKey,
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
        setError(scheduleErrorMessage(err))
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

  const isPackage = preview?.package_mode === 'zip_package'
  const packageFiles = Array.isArray(preview?.files) ? (preview.files as PackageFile[]) : []
  const baselineCandidates = Array.isArray(preview?.baseline_project_candidates)
    ? (preview.baseline_project_candidates as PackageCandidate[])
    : []
  const packageWarnings = Array.isArray(preview?.warnings)
    ? (preview.warnings as PackageWarning[])
    : []
  const selectedIsXer = String(preview?.source_format ?? '') === 'primavera_xer'
  const packageHasXml = packageFiles.some((f) => f.source_format === 'primavera_pmxml')

  return (
    <ScheduleShell>
      <ScheduleBackLink to="/schedules/versions" label="Schedule versions" />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule imports"
        subtitle="Upload Primavera XER, XML/PMXML, Microsoft Project XML, or mapped CSV schedules — individually or as a .zip package — after preview and operator confirmation."
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
          <span className="text-[var(--hb-muted)]">
            Upload Primavera XER, Primavera XML/PMXML, Microsoft Project XML, or mapped CSV — or a .zip
            package of those files — max 50 MB
          </span>
          <input
            type="file"
            accept=".xml,.pmxml,.xer,.csv,.zip"
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

        {ambiguousCandidates ? (
          <div className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-2">
            <p className="font-medium">Multiple current schedules found in this package</p>
            <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
              {ambiguousCandidates.map((c, i) => (
                <li key={i}>
                  {c.project_name || c.project_id || 'Unnamed schedule'} — {c.activity_count} activities (
                  {c.source_format})
                  {c.data_date ? ` · data date ${String(c.data_date).slice(0, 10)}` : ''}
                </li>
              ))}
            </ul>
            <p className="text-[var(--hb-muted)]">
              Upload a single current schedule file, or a package that pairs one schedule with its
              baseline.
            </p>
          </div>
        ) : null}

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
            </div>
          </div>
        ) : null}

        {preview ? (
          <div className="space-y-2 text-sm">
            <ScheduleProjectContext
              projectKey={previewProjectKey}
              projects={projectsData?.projects}
            />
            {preview.schedule_name ? (
              <p className="font-medium">{String(preview.schedule_name)}</p>
            ) : null}
            {preview.source_project_short_name ? (
              <p className="text-xs text-[var(--hb-muted)]">
                Source schedule: {String(preview.source_project_short_name)}
                {preview.source_project_id ? ` (${String(preview.source_project_id)})` : ''}
              </p>
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
            {isPackage ? (
              <div className="rounded border border-[var(--hb-border)] p-3 space-y-2">
                <p className="font-medium">
                  ZIP package — {packageFiles.length} file{packageFiles.length === 1 ? '' : 's'}
                </p>
                <p className="text-xs text-[var(--hb-muted)]">
                  Selected current schedule:{' '}
                  {String(preview.schedule_name ?? preview.source_project_short_name ?? '')} (
                  {String(preview.source_format)})
                  {selectedIsXer && packageHasXml ? ' — XER preferred over XML' : ''}
                </p>
                <div>
                  <p className="text-xs font-medium">Files discovered</p>
                  <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
                    {packageFiles.map((f, i) => (
                      <li key={i}>
                        {f.filename} — {f.source_format || 'unknown'} · {f.parse_status}
                        {f.detected_activities ? ` · ${f.detected_activities} activities` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
                {baselineCandidates.length > 0 ? (
                  <div>
                    <p className="text-xs font-medium">Baseline / supporting candidates</p>
                    <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
                      {baselineCandidates.map((c, i) => (
                        <li key={i}>
                          {c.project_name || c.project_id || 'Unnamed'} — {c.activity_count} activities (
                          {c.source_format})
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {packageWarnings.length > 0 ? (
                  <div>
                    <p className="text-xs font-medium">Ignored files &amp; warnings</p>
                    <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
                      {packageWarnings.map((w, i) => (
                        <li key={i}>
                          {w.filename ? `${w.filename}: ` : ''}
                          {w.message || w.code}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}
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
            {previewIsSupersede ? (
              <p className="text-amber-700">
                This import will supersede the existing schedule version for this project.
              </p>
            ) : null}
            <ScheduleActionButton
              onClick={() => void onCommit(previewIsSupersede)}
              disabled={busy || !previewProjectKey || projectKey !== previewProjectKey}
            >
              {busy && busyAction === 'commit'
                ? 'Committing…'
                : previewIsSupersede
                  ? 'Commit supersede import to database'
                  : 'Commit import to database'}
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
            {committed.schedule_identity_key || committed.identity_match ? (
              <div className="rounded border border-[var(--hb-border)] bg-[var(--hb-surface)] p-2 text-xs space-y-1">
                <p className="font-medium text-sm">Schedule identity</p>
                <p className="font-mono break-all">
                  {String(committed.schedule_identity_key ?? committedIdentityMatch.schedule_identity_key ?? '—')}
                </p>
                <p>
                  Match: {String(committedIdentityMatch.match_status ?? 'unknown')} ·{' '}
                  {String(committedIdentityMatch.match_type ?? 'not reported')}
                  {committedIdentityMatch.requires_review ? ' · review required' : ''}
                </p>
                {committed.comparison_basis ? (
                  <p>
                    Default comparison:{' '}
                    {committedComparisonBasis.identity_safe
                      ? 'identity-safe prior available'
                      : String(committedComparisonBasis.default_prior_unavailable_reason ?? 'not available')}
                  </p>
                ) : null}
              </div>
            ) : null}
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
