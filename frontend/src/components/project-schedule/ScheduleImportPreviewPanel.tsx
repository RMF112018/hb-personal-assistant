import type {
  ProjectScheduleImportPreview,
  ScheduleImportBaselineCandidate,
  ScheduleImportPackageFile,
} from './scheduleImportTypes'
import {
  countPreviewWarnings,
  ignoredPackageFiles,
  supportedPackageFiles,
} from './scheduleImportTypes'

type Props = {
  preview: ProjectScheduleImportPreview
  previewIsSupersede?: boolean
}

export function ScheduleImportPreviewPanel({ preview, previewIsSupersede }: Props) {
  const isPackage = preview.package_mode === 'zip_package'
  const packageFiles = Array.isArray(preview.files) ? preview.files : []
  const supported = supportedPackageFiles(packageFiles)
  const ignored = ignoredPackageFiles(packageFiles)
  const baselines: ScheduleImportBaselineCandidate[] = Array.isArray(preview.baseline_project_candidates)
    ? preview.baseline_project_candidates
    : []
  const equivalence = preview.equivalence_report || {}
  const warningCount = countPreviewWarnings(preview)
  const trustWarnings = preview.trust_preview?.warnings || []

  return (
    <div className="space-y-3 text-sm" data-testid="schedule-import-preview-panel">
      <div>
        <p className="font-medium">
          {preview.schedule_name || preview.source_filename || 'Schedule package'}
        </p>
        {preview.source_project_short_name ? (
          <p className="text-xs text-[var(--hb-muted)]">
            Source: {preview.source_project_short_name}
            {preview.source_project_id ? ` (${preview.source_project_id})` : ''}
          </p>
        ) : null}
      </div>

      {isPackage ? (
        <div className="rounded border border-[var(--hb-border)] p-3 space-y-2">
          <p className="font-medium">Package contents</p>
          {supported.length > 0 ? (
            <div>
              <p className="text-xs font-medium">Supported schedule files ({supported.length})</p>
              <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
                {supported.map((f: ScheduleImportPackageFile, i) => (
                  <li key={`${f.filename}-${i}`}>
                    {f.filename} — {f.source_format || 'unknown'} · {f.parse_status}
                    {f.detected_activities ? ` · ${f.detected_activities} activities` : ''}
                    {f.detected_relationships ? ` · ${f.detected_relationships} relationships` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {ignored.length > 0 || (preview.warnings?.length ?? 0) > 0 ? (
            <div>
              <p className="text-xs font-medium">Ignored metadata / unsupported files</p>
              <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
                {ignored.map((f, i) => (
                  <li key={`ignored-${f.filename}-${i}`}>{f.filename} — ignored</li>
                ))}
                {(preview.warnings || []).map((w, i) => (
                  <li key={`warn-${i}`}>
                    {w.filename ? `${w.filename}: ` : ''}
                    {w.message || w.code}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="rounded border border-[var(--hb-border)] p-3 space-y-1">
        <p className="font-medium">Current schedule</p>
        <p className="text-[var(--hb-muted)]">
          Format: {preview.source_format || '—'}
          {preview.data_date ? ` · Data date: ${String(preview.data_date).slice(0, 10)}` : ''}
        </p>
        <p>
          Activities: {preview.activity_count ?? '—'} · Relationships: {preview.relationship_count ?? '—'}
          {preview.code_count != null ? ` · Codes: ${preview.code_count}` : ''}
          {preview.udf_count != null ? ` · UDFs: ${preview.udf_count}` : ''}
        </p>
      </div>

      {baselines.length > 0 ? (
        <div className="rounded border border-[var(--hb-border)] p-3 space-y-1">
          <p className="font-medium">Linked baseline candidates ({baselines.length})</p>
          <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
            {baselines.map((b, i) => (
              <li key={`bl-${i}`}>
                {b.project_name || b.project_id || 'Unnamed'} — {b.activity_count} activities
                {b.relationship_count != null ? ` · ${b.relationship_count} relationships` : ''} ({b.source_format})
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="rounded border border-[var(--hb-border)] p-3 space-y-1">
        <p className="font-medium">Canonical merge</p>
        <p className="text-[var(--hb-muted)]">
          Equivalence: {equivalence.status || 'single_source'}
          {preview.assembly_mode ? ` · Assembly: ${preview.assembly_mode}` : ''}
        </p>
        {equivalence.companion_count != null ? (
          <p className="text-xs text-[var(--hb-muted)]">
            Companion files merged: {equivalence.equivalent_companion_count ?? 0} / {equivalence.companion_count}
          </p>
        ) : null}
        <p className="text-xs text-[var(--hb-muted)]">
          Expected current schedule count: 1 · Activities: {preview.activity_count ?? '—'} · Relationships:{' '}
          {preview.relationship_count ?? '—'}
        </p>
      </div>

      {warningCount > 0 ? (
        <div className="rounded border border-amber-700/40 bg-amber-950/20 p-3 space-y-1">
          <p className="font-medium">Warnings & conflicts ({warningCount})</p>
          <ul className="list-disc pl-5 text-xs text-[var(--hb-muted)]">
            {trustWarnings.slice(0, 3).map((w, i) => (
              <li key={`tw-${i}`}>{w.message || w.code}</li>
            ))}
            {(preview.merge_warnings || []).slice(0, 3).map((w, i) => (
              <li key={`mw-${i}`}>{w.message || w.code}</li>
            ))}
            {(preview.validation_findings || []).slice(0, 3).map((w, i) => (
              <li key={`vf-${i}`}>
                {w.severity || 'info'}: {w.message || w.code}
              </li>
            ))}
          </ul>
          <p className="text-xs text-[var(--hb-muted)]">Expand technical details for full diagnostics.</p>
        </div>
      ) : null}

      {preview.requires_column_mapping ? (
        <p className="text-amber-700 text-xs">CSV uploads require column mapping before commit.</p>
      ) : null}

      {previewIsSupersede ? (
        <p className="text-amber-700">This import will supersede the existing schedule version for this project.</p>
      ) : null}
    </div>
  )
}
