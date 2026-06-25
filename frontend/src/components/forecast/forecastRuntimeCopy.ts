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

// Business-facing copy for a generation request/run failure_code. Path-free and curated; never
// render a raw failure_code or backend message verbatim. Unknown codes fall back via
// failureCodeCopy() so a new backend code never leaks as a raw token to the operator.
export const FAILURE_CODE_COPY: Record<string, string> = {
  source_package_missing: "Forecast source data isn't available yet.",
  db_persistence_failed: 'The forecast could not be saved.',
  forecast_output_write_failed: 'The forecast could not be saved.',
  generation_calculation_failed: 'The forecast could not be calculated.',
  generation_failed: 'The forecast did not complete.',
  generation_disabled: 'Configuration-backed generation is turned off.',
  generation_not_configured: 'Forecast generation is not configured yet.',
  generation_rejected: 'The request was rejected.',
}

export function failureCodeCopy(code: string | null | undefined): string | null {
  if (!code) return null
  return FAILURE_CODE_COPY[code] || 'The forecast request did not complete.'
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