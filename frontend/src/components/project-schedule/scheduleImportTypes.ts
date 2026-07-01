/** PM-facing schedule import types (project-scoped API payloads). */

export type ScheduleImportWarning = { code?: string; message?: string; filename?: string; severity?: string }

export type ScheduleImportPackageFile = {
  filename: string
  source_format: string
  parse_status: string
  detected_activities: number
  detected_relationships?: number
  detected_baseline_projects: number
  warnings: ScheduleImportWarning[]
}

export type ScheduleImportBaselineCandidate = {
  source_file_id?: string
  project_id: string | null
  project_name: string | null
  data_date?: string | null
  activity_count: number
  relationship_count?: number
  source_format: string
}

export type ScheduleImportEquivalenceReport = {
  status?: string
  companion_count?: number
  equivalent_companion_count?: number
  incompatible_candidate_count?: number
  block_reason?: string
}

export type ScheduleImportFieldLineage = {
  field_family?: string
  source_format?: string
  merge_strategy?: string
  records_contributed?: number
}

export type ScheduleImportTrustPreview = {
  posture?: string
  warnings?: ScheduleImportWarning[]
}

export type ProjectScheduleImportPreview = {
  import_id?: string
  source_filename?: string
  schedule_name?: string
  source_format?: string
  source_project_id?: string
  source_project_short_name?: string
  data_date?: string
  activity_count?: number
  relationship_count?: number
  code_count?: number
  udf_count?: number
  wbs_count?: number
  calendar_count?: number
  cost_loaded_status?: string
  package_mode?: string
  assembly_mode?: string
  package_id?: string
  requires_column_mapping?: boolean
  equivalence_report?: ScheduleImportEquivalenceReport
  files?: ScheduleImportPackageFile[]
  baseline_project_candidates?: ScheduleImportBaselineCandidate[]
  warnings?: ScheduleImportWarning[]
  merge_warnings?: ScheduleImportWarning[]
  validation_findings?: ScheduleImportWarning[]
  field_family_lineage?: ScheduleImportFieldLineage[]
  trust_preview?: ScheduleImportTrustPreview
  file_sha256?: string
  [key: string]: unknown
}

export type PipelineStage = {
  stage?: string
  label?: string
  status?: string
}

export type ProjectScheduleImportStatus = {
  import_id?: string
  overall_status?: string
  stages?: PipelineStage[]
  cpm?: {
    cpm_recompute_status?: string
    failure_code?: string
    failure_message_redacted?: string
    failed_step?: string
    canonical_input_activity_count?: number
    canonical_input_relationship_count?: number
    [key: string]: unknown
  }
  [key: string]: unknown
}

export type ProjectScheduleImportCommitResult = {
  import_id?: string
  schedule_version_key?: string
  activity_count?: number
  relationship_count?: number
  baseline_project_count?: number
  cpm_recompute_status?: string
  cpm_recompute_triggered?: boolean
  cpm_run_id?: string
  cpm_observability?: Record<string, unknown>
  canonical_input_activity_count?: number
  canonical_input_relationship_count?: number
  cpm_failure_reason?: string
  failure_message_redacted?: string
  analytics_trust?: Record<string, unknown>
  pipeline?: ProjectScheduleImportStatus
  supersede_performed?: boolean
  [key: string]: unknown
}

export type ScheduleImportDuplicateInfo = {
  schedule_version_key: string
  activity_count: number
  relationship_count: number
  view_path: string
}

export function asImportPreview(raw: Record<string, unknown> | null): ProjectScheduleImportPreview | null {
  return raw as ProjectScheduleImportPreview | null
}

export function isCommitAllowed(preview: ProjectScheduleImportPreview | null): boolean {
  if (!preview?.import_id) return false
  if (preview.requires_column_mapping) return false
  const eq = preview.equivalence_report
  if (eq?.status === 'incompatible') return false
  return true
}

export function isRetryAvailable(
  cpmStatus: string,
  committed?: ProjectScheduleImportCommitResult | null,
): boolean {
  if (cpmStatus === 'failed') return true
  const obs = committed?.cpm_observability as Record<string, unknown> | undefined
  return String(obs?.status || '') === 'failed'
}

export function countPreviewWarnings(preview: ProjectScheduleImportPreview | null): number {
  if (!preview) return 0
  const buckets = [
    preview.warnings,
    preview.merge_warnings,
    preview.validation_findings,
    preview.trust_preview?.warnings,
  ]
  return buckets.reduce((sum, list) => sum + (Array.isArray(list) ? list.length : 0), 0)
}

export function ignoredPackageFiles(files: ScheduleImportPackageFile[]): ScheduleImportPackageFile[] {
  return files.filter(
    (f) =>
      f.parse_status === 'ignored' ||
      (Array.isArray(f.warnings) &&
        f.warnings.some((w) => String(w.code || '').includes('ignored'))),
  )
}

export function supportedPackageFiles(files: ScheduleImportPackageFile[]): ScheduleImportPackageFile[] {
  return files.filter((f) => f.parse_status !== 'ignored' && f.parse_status !== 'unsupported')
}
