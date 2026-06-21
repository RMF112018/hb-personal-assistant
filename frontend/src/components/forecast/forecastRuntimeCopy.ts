/* Shared, business-facing copy for the forecast runtime data sources. Kept in one place so the
 * settings page and the onboarding readiness panel never drift. No paths or internals — labels only. */

export const ROOT_LABELS: Record<string, string> = {
  package_roots: 'Forecast packages',
  data_root: 'Source data folder',
  runs_root: 'Run output folder',
  eval_root: 'Evaluation output folder',
  db_path: 'Source database',
  cfr_src: 'Engine source',
  config_edit_root: 'Config proposal output folder',
}

export const BLOCKER_COPY: Record<string, string> = {
  not_configured: 'Not configured',
  not_absolute: 'Path must be absolute',
  missing: 'Path does not exist',
  not_a_directory: 'Not a directory',
  under_live_data_root: 'Must be outside the live data folder',
  not_creatable: 'Folder cannot be created',
}

/* The read-roots the operator must point at the live project inputs (write-roots auto-provision at
 * launch, so they are not part of onboarding). `unlocks` is the friendly "what this enables". */
export const READ_ROOTS: { key: string; label: string; unlocks: string }[] = [
  { key: 'package_roots', label: ROOT_LABELS.package_roots, unlocks: 'Unlocks the package browser' },
  { key: 'data_root', label: ROOT_LABELS.data_root, unlocks: 'Unlocks running forecasts' },
  { key: 'db_path', label: ROOT_LABELS.db_path, unlocks: 'Unlocks configuration & external evaluation' },
]

/* Per-root advisory line built from the redaction-safe status (ints only — never a path). */
export function rootAdvisory(key: string, root: Record<string, any> | undefined): string | null {
  if (!root || !root.valid) return null
  if (key === 'package_roots' && typeof root.count === 'number') {
    return root.count === 1 ? '1 forecast package found' : `${root.count} forecast packages found`
  }
  if (key === 'db_path' && typeof root.schema_version === 'number') {
    const snaps = typeof root.config_snapshot_count === 'number' ? root.config_snapshot_count : 0
    const snapLabel = snaps === 1 ? '1 config snapshot' : `${snaps} config snapshots`
    return `Ready · schema v${root.schema_version}, ${snapLabel}`
  }
  return null
}
