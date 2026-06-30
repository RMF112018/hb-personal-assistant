import { Link } from 'react-router-dom'

import type {
  PipelineStage,
  ProjectScheduleImportCommitResult,
  ProjectScheduleImportStatus,
} from './scheduleImportTypes'
import { isRetryAvailable } from './scheduleImportTypes'

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
    case 'unavailable':
      return 'Unavailable'
    case 'not_applicable':
      return 'Not applicable'
    default:
      return 'Not started'
  }
}

type Props = {
  projectKey: string
  committed: ProjectScheduleImportCommitResult
  pipelineStatus?: ProjectScheduleImportStatus | null
  cpmStatus: string
  busy?: boolean
  onRetry?: () => void
  variant?: 'page' | 'modal'
  onClose?: () => void
}

export function ScheduleImportCommitResultPanel({
  projectKey,
  committed,
  pipelineStatus,
  cpmStatus,
  busy,
  onRetry,
  variant = 'page',
  onClose,
}: Props) {
  const canonicalOk = Boolean(committed.schedule_version_key && (committed.activity_count ?? 0) > 0)
  const cpmComplete = cpmStatus === 'complete'
  const cpmPartial = cpmStatus === 'partial'
  const cpmFailed = cpmStatus === 'failed'
  const overallClean = canonicalOk && cpmComplete
  const needsAttention = canonicalOk && (cpmFailed || cpmPartial)

  const pipeline: PipelineStage[] =
    pipelineStatus?.stages ||
    (committed.pipeline?.stages as PipelineStage[] | undefined) ||
    []

  const headline = overallClean
    ? 'Import succeeded'
    : needsAttention
      ? 'Import needs attention'
      : cpmFailed && !canonicalOk
        ? 'Import failed'
        : 'Import committed'

  const showRetry = isRetryAvailable(cpmStatus, committed) && Boolean(onRetry)

  return (
    <div
      className="rounded border border-[var(--hb-border)] p-3 text-sm space-y-3"
      data-testid="schedule-import-commit-result"
      data-overall-status={overallClean ? 'success' : needsAttention ? 'partial' : 'failed'}
    >
      <p className="font-medium">{headline}</p>

      <div className="space-y-1 text-[var(--hb-muted)]">
        <p>
          Canonical merge: {canonicalOk ? 'complete' : 'unknown'} · Activities:{' '}
          {committed.activity_count ?? committed.canonical_input_activity_count ?? '—'} · Relationships:{' '}
          {committed.relationship_count ?? committed.canonical_input_relationship_count ?? '—'}
        </p>
        {committed.baseline_project_count != null ? (
          <p>Baselines persisted: {committed.baseline_project_count}</p>
        ) : null}
        <p>
          CPM recompute: {cpmStatus || 'pending'}
          {committed.cpm_run_id ? ` · run ${String(committed.cpm_run_id).slice(0, 12)}…` : ''}
        </p>
        {cpmFailed && committed.cpm_failure_reason ? (
          <p className="text-red-600">CPM failure: {committed.cpm_failure_reason}</p>
        ) : null}
        {needsAttention && !cpmFailed ? (
          <p className="text-amber-700">
            Schedule data was imported, but computed CPM is incomplete. Review before relying on critical-path metrics.
          </p>
        ) : null}
      </div>

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

      {showRetry ? (
        <button className="badge" type="button" disabled={busy} onClick={onRetry} data-testid="schedule-import-retry">
          {busy ? 'Retrying CPM…' : 'Retry computed CPM'}
        </button>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {variant === 'modal' && onClose ? (
          <button className="badge" type="button" onClick={onClose}>
            Return to schedule
          </button>
        ) : (
          <Link className="badge" to={`/projects/${projectKey}/schedule`}>
            Return to Project Schedule
          </Link>
        )}
        <Link className="badge" to={`/projects/${projectKey}/schedule/workbench`}>
          Open Workbench
        </Link>
      </div>
    </div>
  )
}
