import type { ProjectScheduleImportPreview, ProjectScheduleImportCommitResult } from './scheduleImportTypes'

type Props = {
  preview?: ProjectScheduleImportPreview | null
  committed?: ProjectScheduleImportCommitResult | null
}

export function ScheduleImportTechnicalDetails({ preview, committed }: Props) {
  const hasPreview = Boolean(preview && Object.keys(preview).length)
  const hasCommitted = Boolean(committed && Object.keys(committed).length)
  if (!hasPreview && !hasCommitted) return null

  return (
    <details className="text-xs text-[var(--hb-muted)]" data-testid="schedule-import-technical-details">
      <summary className="cursor-pointer font-medium text-[var(--hb-text)]">Technical details</summary>
      <div className="mt-2 space-y-2 rounded border border-[var(--hb-border)] p-2 font-mono break-all">
        {preview?.import_id ? <p>import_id: {preview.import_id}</p> : null}
        {preview?.package_id ? <p>package_id: {preview.package_id}</p> : null}
        {preview?.file_sha256 ? <p>file_sha256: {preview.file_sha256}</p> : null}
        {committed?.cpm_run_id ? <p>cpm_run_id: {String(committed.cpm_run_id)}</p> : null}
        {preview?.field_family_lineage?.length ? (
          <pre className="whitespace-pre-wrap">{JSON.stringify(preview.field_family_lineage, null, 2)}</pre>
        ) : null}
        {hasPreview ? (
          <pre className="whitespace-pre-wrap max-h-48 overflow-auto">{JSON.stringify(preview, null, 2)}</pre>
        ) : null}
        {hasCommitted ? (
          <pre className="whitespace-pre-wrap max-h-48 overflow-auto">{JSON.stringify(committed, null, 2)}</pre>
        ) : null}
      </div>
    </details>
  )
}
