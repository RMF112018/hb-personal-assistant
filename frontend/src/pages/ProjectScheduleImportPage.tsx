import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { api, ScheduleApiError, ScheduleNetworkError } from '../lib/api'

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024

type PipelineStage = {
  stage?: string
  label?: string
  status?: string
}

function scheduleErrorMessage(err: unknown): string {
  if (err instanceof ScheduleNetworkError) {
    return 'Could not reach the schedule import service. Check that the backend is running and retry.'
  }
  if (err instanceof ScheduleApiError) {
    return err.message || 'Schedule import failed.'
  }
  return 'Schedule import failed. Check the file format and try again.'
}

function stageLabel(status: string | undefined) {
  switch (status) {
    case 'complete':
      return 'Complete'
    case 'running':
      return 'Running'
    case 'pending':
      return 'Pending'
    case 'partial':
      return 'Partial'
    case 'failed':
      return 'Failed'
    case 'blocked':
      return 'Blocked'
    case 'unavailable':
      return 'Unavailable'
    case 'not_applicable':
      return 'Not applicable'
    default:
      return 'Not started'
  }
}

export function ProjectScheduleImportPage() {
  const { projectKey = '' } = useParams()
  const [busy, setBusy] = useState(false)
  const [busyAction, setBusyAction] = useState<'preview' | 'commit' | 'retry' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [previewIsSupersede, setPreviewIsSupersede] = useState(false)
  const [committed, setCommitted] = useState<Record<string, unknown> | null>(null)
  const [importId, setImportId] = useState('')

  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  })
  const project = projectsData?.projects.find((item) => item.project_key === projectKey)

  const { data: pipelineStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['project', 'schedule', 'import-status', projectKey, importId],
    queryFn: () => api.getProjectScheduleImportStatus(projectKey, importId),
    enabled: Boolean(projectKey && importId && committed),
  })

  useEffect(() => {
    if (!committed?.import_id) return
    setImportId(String(committed.import_id))
  }, [committed])

  async function onUpload(file: File, confirmSupersede = false) {
    if (!projectKey) return
    setBusy(true)
    setBusyAction('preview')
    setError(null)
    setCommitted(null)
    if (!confirmSupersede) {
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
      const resp = await api.uploadProjectScheduleImportPreview(projectKey, file, null, confirmSupersede)
      setPreview(resp as Record<string, unknown>)
      setPreviewIsSupersede(confirmSupersede)
    } catch (err) {
      setError(scheduleErrorMessage(err))
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
      const resp = await api.commitProjectScheduleImport(
        projectKey,
        String(preview.import_id),
        null,
        confirmSupersede,
      )
      setCommitted(resp as Record<string, unknown>)
      setImportId(String(preview.import_id))
    } catch (err) {
      setError(scheduleErrorMessage(err))
    } finally {
      setBusy(false)
      setBusyAction(null)
    }
  }

  async function onRetryCpm() {
    if (!importId || !projectKey) return
    setBusy(true)
    setBusyAction('retry')
    setError(null)
    try {
      const resp = await api.retryProjectScheduleImportCpm(projectKey, importId)
      setCommitted((prev) => ({ ...(prev || {}), ...(resp as Record<string, unknown>) }))
      await refetchStatus()
    } catch (err) {
      setError(scheduleErrorMessage(err))
    } finally {
      setBusy(false)
      setBusyAction(null)
    }
  }

  const trustPreview =
    preview?.trust_preview && typeof preview.trust_preview === 'object'
      ? (preview.trust_preview as Record<string, unknown>)
      : {}
  const trustWarnings = Array.isArray(trustPreview.warnings)
    ? (trustPreview.warnings as Record<string, string>[])
    : []
  const committedPipeline =
    committed?.pipeline && typeof committed.pipeline === 'object'
      ? (committed.pipeline as Record<string, unknown>)
      : null
  const pipeline =
    pipelineStatus &&
    typeof pipelineStatus === 'object' &&
    Array.isArray((pipelineStatus as Record<string, unknown>).stages)
      ? ((pipelineStatus as Record<string, unknown>).stages as PipelineStage[])
      : committedPipeline && Array.isArray(committedPipeline.stages)
        ? (committedPipeline.stages as PipelineStage[])
        : []
  const cpmStatus = String(
    (pipelineStatus as Record<string, unknown> | undefined)?.cpm &&
      typeof (pipelineStatus as Record<string, unknown>).cpm === 'object'
      ? ((pipelineStatus as Record<string, unknown>).cpm as Record<string, unknown>).cpm_recompute_status
      : committed?.cpm_recompute_status || '',
  )

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4 max-w-2xl">
        <div>
          <h3 className="section-title mb-0">Upload schedule update</h3>
          <p className="mt-1 text-sm text-[var(--hb-muted)]">
            Preview and commit a schedule update for {project?.display_name || projectKey}. Project context is locked
            to this workspace.
          </p>
        </div>

        <div className="forecast-panel p-4 space-y-4">
          <div className="rounded border border-[var(--hb-border)] p-3 text-sm">
            <p className="font-medium">{project?.display_name || projectKey}</p>
            <p className="text-xs text-[var(--hb-muted)]">Project key: {projectKey}</p>
          </div>

          <label className="block text-sm">
            <span className="text-[var(--hb-muted)]">
              Upload Primavera XER, XML/PMXML, Microsoft Project XML, mapped CSV, or .zip package — max 50 MB
            </span>
            <input
              aria-label="Upload Primavera XER, XML/PMXML, Microsoft Project XML, mapped CSV, or zip package"
              type="file"
              accept=".xml,.pmxml,.xer,.csv,.zip"
              className="mt-2 block w-full text-sm"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void onUpload(f)
              }}
            />
          </label>

          {busy && busyAction === 'preview' ? (
            <p className="text-sm text-[var(--hb-muted)]">Previewing schedule update…</p>
          ) : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          {preview ? (
            <div className="space-y-2 text-sm">
              <p className="font-medium">{String(preview.schedule_name || preview.source_filename || 'Schedule preview')}</p>
              <p className="text-[var(--hb-muted)]">
                Format: {String(preview.source_format)} · Activities: {String(preview.activity_count)} · Relationships:{' '}
                {String(preview.relationship_count)}
                {preview.data_date ? ` · Data date ${String(preview.data_date)}` : ''}
              </p>
              {trustWarnings.length > 0 ? (
                <div className="rounded border border-amber-700/40 bg-amber-950/20 p-3 space-y-1">
                  <p className="font-medium">Identity / trust preview</p>
                  <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
                    {trustWarnings.map((warning, index) => (
                      <li key={index}>{warning.message || warning.code}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-xs text-[var(--hb-muted)]">
                  This file appears to belong to the current schedule series.
                </p>
              )}
              {previewIsSupersede ? (
                <p className="text-amber-700">This import will supersede the existing schedule version for this project.</p>
              ) : null}
              <button
                className="badge"
                type="button"
                disabled={busy}
                onClick={() => void onCommit(previewIsSupersede)}
              >
                {busy && busyAction === 'commit' ? 'Committing…' : 'Preview schedule update and commit'}
              </button>
            </div>
          ) : null}

          {committed ? (
            <div className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-3">
              <p className="font-medium">Import committed</p>
              <p className="text-[var(--hb-muted)]">
                Computed CPM status: {cpmStatus || String(committed.cpm_recompute_status || 'pending')}
              </p>
              {pipeline.length > 0 ? (
                <div>
                  <p className="text-xs font-medium mb-2">Processing checklist</p>
                  <ul className="space-y-1 text-xs">
                    {pipeline.map((stage) => (
                      <li key={stage.stage || stage.label} className="flex justify-between gap-3">
                        <span>{stage.label || stage.stage}</span>
                        <span className="text-[var(--hb-muted)]">{stageLabel(stage.status)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {(cpmStatus === 'failed' || cpmStatus === 'partial' || cpmStatus === 'unavailable') && (
                <button className="badge" type="button" disabled={busy} onClick={() => void onRetryCpm()}>
                  {busy && busyAction === 'retry' ? 'Retrying CPM…' : 'Retry computed CPM'}
                </button>
              )}
              <div className="flex flex-wrap gap-2">
                <Link className="badge" to={`/projects/${projectKey}/schedule`}>
                  Return to Project Schedule
                </Link>
                <Link className="badge" to={`/projects/${projectKey}/schedule/workbench`}>
                  Open Workbench
                </Link>
                <Link className="badge" to={`/schedules/identity-review?project=${encodeURIComponent(projectKey)}`}>
                  Open Identity Review
                </Link>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </ProjectWorkspaceShell>
  )
}