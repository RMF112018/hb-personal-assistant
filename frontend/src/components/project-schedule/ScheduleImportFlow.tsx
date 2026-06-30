import { useCallback, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api, ScheduleApiError } from '../../lib/api'
import { scheduleImportErrorMessage } from './scheduleImportErrors'
import { ScheduleImportCommitResultPanel } from './ScheduleImportCommitResult'
import { ScheduleImportPreviewPanel } from './ScheduleImportPreviewPanel'
import { ScheduleImportTechnicalDetails } from './ScheduleImportTechnicalDetails'
import type {
  ProjectScheduleImportCommitResult,
  ProjectScheduleImportPreview,
  ProjectScheduleImportStatus,
  ScheduleImportBaselineCandidate,
  ScheduleImportDuplicateInfo,
} from './scheduleImportTypes'
import { asImportPreview, isCommitAllowed } from './scheduleImportTypes'

export const MAX_SCHEDULE_IMPORT_BYTES = 50 * 1024 * 1024

export type ScheduleImportFlowProps = {
  projectKey: string
  projectDisplayName?: string | null
  variant?: 'page' | 'modal'
  onCommitSuccess?: (result: ProjectScheduleImportCommitResult) => void
  onClose?: () => void
}

export function ScheduleImportFlow({
  projectKey,
  projectDisplayName,
  variant = 'page',
  onCommitSuccess,
  onClose,
}: ScheduleImportFlowProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [busyAction, setBusyAction] = useState<'preview' | 'commit' | 'retry' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<ProjectScheduleImportPreview | null>(null)
  const [previewIsSupersede, setPreviewIsSupersede] = useState(false)
  const [committed, setCommitted] = useState<ProjectScheduleImportCommitResult | null>(null)
  const [importId, setImportId] = useState('')
  const [duplicate, setDuplicate] = useState<ScheduleImportDuplicateInfo | null>(null)
  const [ambiguousCandidates, setAmbiguousCandidates] = useState<ScheduleImportBaselineCandidate[] | null>(
    null,
  )
  const [pendingFile, setPendingFile] = useState<File | null>(null)

  const { data: pipelineStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['project', 'schedule', 'import-status', projectKey, importId],
    queryFn: () => api.getProjectScheduleImportStatus(projectKey, importId) as Promise<ProjectScheduleImportStatus>,
    enabled: Boolean(projectKey && importId && committed),
  })

  const cpmStatus = String(
    pipelineStatus?.cpm?.cpm_recompute_status ||
      committed?.cpm_recompute_status ||
      (committed?.pipeline?.cpm as Record<string, unknown> | undefined)?.cpm_recompute_status ||
      '',
  )

  const runPreview = useCallback(
    async (file: File, confirmSupersede = false) => {
      if (!projectKey || busy) return
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
      if (file.size > MAX_SCHEDULE_IMPORT_BYTES) {
        setError('This file exceeds the 50 MB upload limit.')
        setBusy(false)
        setBusyAction(null)
        return
      }
      try {
        const resp = await api.uploadProjectScheduleImportPreview(projectKey, file, null, confirmSupersede)
        setPreview(asImportPreview(resp as Record<string, unknown>))
        setPreviewIsSupersede(confirmSupersede)
        setPendingFile(file)
        if (!confirmSupersede) setDuplicate(null)
      } catch (err) {
        if (err instanceof ScheduleApiError && err.code === 'duplicate_schedule_version') {
          const p = err.payload || {}
          setDuplicate({
            schedule_version_key: String(p.schedule_version_key ?? ''),
            activity_count: Number(p.activity_count ?? 0),
            relationship_count: Number(p.relationship_count ?? 0),
            view_path: String(p.view_path ?? `/projects/${projectKey}/schedule`),
          })
          setPendingFile(file)
        } else if (
          err instanceof ScheduleApiError &&
          err.code === 'schedule_package_multiple_current_candidates'
        ) {
          const cands = Array.isArray(err.payload?.candidates)
            ? (err.payload.candidates as ScheduleImportBaselineCandidate[])
            : []
          setAmbiguousCandidates(cands)
        }
        setError(scheduleImportErrorMessage(err))
      } finally {
        setBusy(false)
        setBusyAction(null)
      }
    },
    [projectKey, busy],
  )

  const runCommit = useCallback(
    async (confirmSupersede = false) => {
      if (!preview?.import_id || !projectKey || busy) return
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
        const body = resp as ProjectScheduleImportCommitResult
        setCommitted(body)
        setImportId(String(preview.import_id))
        setDuplicate(null)
        onCommitSuccess?.(body)
      } catch (err) {
        if (err instanceof ScheduleApiError && err.code === 'duplicate_schedule_version') {
          const p = err.payload || {}
          setDuplicate({
            schedule_version_key: String(p.schedule_version_key ?? ''),
            activity_count: Number(p.activity_count ?? 0),
            relationship_count: Number(p.relationship_count ?? 0),
            view_path: String(p.view_path ?? `/projects/${projectKey}/schedule`),
          })
        }
        setError(scheduleImportErrorMessage(err))
      } finally {
        setBusy(false)
        setBusyAction(null)
      }
    },
    [preview, projectKey, busy, onCommitSuccess],
  )

  const runRetry = useCallback(async () => {
    if (!importId || !projectKey || busy) return
    setBusy(true)
    setBusyAction('retry')
    setError(null)
    try {
      const resp = await api.retryProjectScheduleImportCpm(projectKey, importId)
      setCommitted((prev) => ({ ...(prev || {}), ...(resp as ProjectScheduleImportCommitResult) }))
      await refetchStatus()
    } catch (err) {
      setError(scheduleImportErrorMessage(err))
    } finally {
      setBusy(false)
      setBusyAction(null)
    }
  }, [importId, projectKey, busy, refetchStatus])

  const commitAllowed = isCommitAllowed(preview)
  const previewLoading = busy && busyAction === 'preview'
  const commitLoading = busy && busyAction === 'commit'

  return (
    <div className="forecast-panel p-4 space-y-4" data-testid="schedule-import-flow">
      {variant === 'page' ? (
        <div className="rounded border border-[var(--hb-border)] p-3 text-sm">
          <p className="font-medium">{projectDisplayName || projectKey}</p>
          <p className="text-xs text-[var(--hb-muted)]">Project key: {projectKey}</p>
        </div>
      ) : null}

      {!committed ? (
        <>
          <label className="block text-sm">
            <span className="text-[var(--hb-muted)]">
              Upload Primavera XER, XML/PMXML, Microsoft Project XML, mapped CSV, or .zip package — max 50 MB
            </span>
            <input
              ref={fileInputRef}
              aria-label="Upload Primavera XER, XML/PMXML, Microsoft Project XML, mapped CSV, or zip package"
              type="file"
              accept=".xml,.pmxml,.xer,.csv,.zip"
              className="mt-2 block w-full text-sm"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void runPreview(f)
              }}
            />
          </label>

          {previewLoading ? <p className="text-sm text-[var(--hb-muted)]">Previewing schedule package…</p> : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          {ambiguousCandidates ? (
            <div className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-2">
              <p className="font-medium">Multiple current schedules found in this package</p>
              <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
                {ambiguousCandidates.map((c, i) => (
                  <li key={i}>
                    {c.project_name || c.project_id || 'Unnamed'} — {c.activity_count} activities ({c.source_format})
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {duplicate ? (
            <div className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-2" data-testid="schedule-import-supersede">
              <p className="font-medium">This schedule version is already imported for this project.</p>
              <p className="text-[var(--hb-muted)]">Version: {duplicate.schedule_version_key}</p>
              <p>
                Activities: {duplicate.activity_count} · Relationships: {duplicate.relationship_count}
              </p>
              <button
                className="badge"
                type="button"
                disabled={busy}
                onClick={() => {
                  if (pendingFile) void runPreview(pendingFile, true)
                }}
              >
                Preview supersede
              </button>
            </div>
          ) : null}

          {preview ? (
            <div className="space-y-3">
              <ScheduleImportPreviewPanel preview={preview} previewIsSupersede={previewIsSupersede} />
              <ScheduleImportTechnicalDetails preview={preview} />
              <button
                className="badge"
                type="button"
                disabled={busy || !commitAllowed}
                onClick={() => void runCommit(previewIsSupersede)}
                data-testid="schedule-import-commit"
              >
                {commitLoading
                  ? 'Committing…'
                  : previewIsSupersede
                    ? 'Commit supersede import'
                    : 'Commit import'}
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <ScheduleImportCommitResultPanel
            projectKey={projectKey}
            committed={committed}
            pipelineStatus={pipelineStatus}
            cpmStatus={cpmStatus}
            busy={busy}
            onRetry={() => void runRetry()}
            variant={variant}
            onClose={onClose}
          />
          <ScheduleImportTechnicalDetails preview={preview} committed={committed} />
        </>
      )}
    </div>
  )
}
