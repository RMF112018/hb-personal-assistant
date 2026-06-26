import type { ForecastDbOutputSummary } from '../../lib/api'

export type ForecastOutputSelection = {
  /** The resolved, always-valid output id to read detail/monthly for (or null when none exist). */
  selectedOutputId: string | null
  /** True when a specific output was requested but is not in this project's output list. */
  isInvalidSelection: boolean
}

/**
 * Single source of truth for project-scoped forecast output selection, shared by the Forecasting
 * summary, the Monthly panel, and the selector so they resolve identically.
 *
 * - A requested id that belongs to the project's outputs is used as-is.
 * - A requested id that is NOT in the (non-empty) project output list is treated as invalid: it is
 *   never used for detail/monthly reads; instead we fall back to the latest output and flag it so
 *   the UI can warn. This is what keeps invalid or foreign output ids from being fetched.
 * - With no request, the latest output (the list is newest-first) is selected.
 *
 * `outputs` must already be the project-scoped list (`getForecastDbOutputs(projectKey)`); pass `[]`
 * while loading — the result is then `{ null, false }` (no false invalid flag mid-load).
 */
export function selectForecastOutput(
  outputs: ForecastDbOutputSummary[],
  requestedOutputId: string | null | undefined,
): ForecastOutputSelection {
  const latestId = outputs[0]?.output_id ?? null

  if (!requestedOutputId) {
    return { selectedOutputId: latestId, isInvalidSelection: false }
  }

  const isKnown = outputs.some((o) => o.output_id === requestedOutputId)
  if (isKnown) {
    return { selectedOutputId: requestedOutputId, isInvalidSelection: false }
  }

  // Requested id is not part of this project's outputs. Only flag invalid once outputs are loaded;
  // while the list is still empty we simply have nothing selected yet.
  return { selectedOutputId: latestId, isInvalidSelection: outputs.length > 0 }
}
