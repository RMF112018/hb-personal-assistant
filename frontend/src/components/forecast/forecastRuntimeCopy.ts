/* Shared, business-facing copy for forecast storage readiness. No paths or internals. */

export type RuntimeRootStatus = {
  valid?: boolean
  blocker?: string | null
  count?: number
  schema_version?: number
  config_snapshot_count?: number
}

export const ROOT_LABELS: Record<string, string> = {
  package_roots: 'Forecast package storage',
  data_root: 'Source data workspace',
  runs_root: 'Run output workspace',
  eval_root: 'Evaluation workspace',
  db_path: 'Local forecast database',
  cfr_src: 'Forecast engine',
  config_edit_root: 'Config proposal workspace',
}

export const BLOCKER_COPY: Record<string, string> = {
  not_configured: 'Not ready',
  not_absolute: 'Invalid location',
  missing: 'Not found',
  not_a_directory: 'Not a folder',
  under_live_data_root: 'Must stay outside source data',
  not_creatable: 'Cannot be created',
}

export const SURFACE_LABELS: Record<string, string> = {
  catalog: 'Package browser',
  config: 'Configuration viewer',
  run_center: 'Forecast generation',
  external_eval: 'External evaluation',
  config_edit: 'Config proposals',
  config_promotion: 'Live promotion',
  db_config_run: 'Config-backed generation',
}

export const READ_ROOTS: { key: string; label: string; unlocks: string }[] = [
  { key: 'package_roots', label: ROOT_LABELS.package_roots, unlocks: 'Browse forecast packages' },
  { key: 'data_root', label: ROOT_LABELS.data_root, unlocks: 'Generate forecasts' },
  { key: 'db_path', label: ROOT_LABELS.db_path, unlocks: 'View configuration and evaluate external forecasts' },
]

export function rootAdvisory(key: string, root: RuntimeRootStatus | undefined): string | null {
  if (!root || !root.valid) return null
  if (key === 'package_roots' && typeof root.count === 'number') {
    return root.count === 1 ? '1 package folder ready' : `${root.count} package folders ready`
  }
  if (key === 'db_path' && typeof root.schema_version === 'number') {
    const snaps = typeof root.config_snapshot_count === 'number' ? root.config_snapshot_count : 0
    const snapLabel = snaps === 1 ? '1 configuration snapshot' : `${snaps} configuration snapshots`
    return `Database ready · ${snapLabel}`
  }
  return null
}