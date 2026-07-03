/** Reason-aware schedule UI state taxonomy for PM-facing panels. */

export type ScheduleDataUiState =
  | 'loading'
  | 'refreshing'
  | 'no_schedule'
  | 'no_metric_payload'
  | 'metric_unsupported'
  | 'baseline_not_selected'
  | 'cpm_not_computed'
  | 'api_error'
  | 'data_stale'
  | 'ready'

export type ScheduleQueryActivity = {
  isLoading?: boolean
  isPending?: boolean
  isFetching?: boolean
  isError?: boolean
  hasData?: boolean
}

export function isScheduleQueryLoading({ isLoading, isPending, hasData }: ScheduleQueryActivity): boolean {
  return Boolean((isLoading || isPending) && !hasData)
}

export function isScheduleQueryRefreshing({ isFetching, hasData }: ScheduleQueryActivity): boolean {
  return Boolean(isFetching && hasData)
}

/** True when retained placeholder data does not match the requested as-of filter. */
export function isScheduleResponseStale(
  payload: { as_of_date?: string | null } | undefined,
  requestAsOf: string | undefined,
  isFetching: boolean,
): boolean {
  if (!isFetching || !payload?.as_of_date || !requestAsOf) return false
  return String(payload.as_of_date) !== requestAsOf
}

export function scheduleQueryKeySuffix(asOf: string): string {
  return asOf || 'latest'
}

export function cpmUnavailableLabel(
  computedCpmSummary: Record<string, unknown> | undefined,
  cpm: Record<string, unknown> | undefined,
  activity: ScheduleQueryActivity & { isStale?: boolean },
): { state: ScheduleDataUiState; message: string } {
  if (isScheduleQueryLoading(activity)) {
    return { state: 'loading', message: 'Loading computed CPM status…' }
  }
  if (activity.isStale || isScheduleQueryRefreshing(activity)) {
    return { state: 'refreshing', message: 'Refreshing computed CPM for the selected as-of date…' }
  }
  if (activity.isError) {
    return { state: 'api_error', message: 'Computed CPM status could not be loaded.' }
  }
  const available = computedCpmSummary?.available === true || cpm?.available === true
  if (available) {
    return { state: 'ready', message: 'Application-computed CPM is available for this schedule update.' }
  }
  const reason = String(
    computedCpmSummary?.reason ||
      (computedCpmSummary?.unavailable as Record<string, unknown> | undefined)?.reason ||
      cpm?.reason ||
      'no_computed_cpm',
  )
  return {
    state: 'cpm_not_computed',
    message: humanizeCpmReason(reason),
  }
}

function humanizeCpmReason(reason: string): string {
  switch (reason) {
    case 'no_computed_cpm':
    case 'no persisted computed CPM run':
      return 'CPM has not been computed for this schedule update on the local database.'
    case 'no_schedule':
      return 'Import a schedule update before CPM can be computed.'
    default:
      return reason.replace(/_/g, ' ')
  }
}

export function metricPanelUiState(
  metric: Record<string, unknown> | undefined,
  activity: ScheduleQueryActivity & { isStale?: boolean },
): ScheduleDataUiState {
  if (isScheduleQueryLoading(activity)) return 'loading'
  if (isScheduleQueryRefreshing(activity) || activity.isStale) return 'refreshing'
  if (activity.isError) return 'api_error'
  if (!metric) return 'no_metric_payload'
  if (metric.available === false) {
    const reason = String(metric.reason || metric.readiness_status || '')
    if (reason.includes('baseline')) return 'baseline_not_selected'
    if (reason.includes('unsupported')) return 'metric_unsupported'
    return 'no_metric_payload'
  }
  return 'ready'
}

export function metricPanelMessage(state: ScheduleDataUiState, metric?: Record<string, unknown>): string {
  switch (state) {
    case 'loading':
      return 'Loading schedule trend data…'
    case 'refreshing':
      return 'Refreshing schedule trend data for the selected as-of date…'
    case 'api_error':
      return 'Schedule trend data could not be loaded right now.'
    case 'no_metric_payload':
      return 'No trend metric payload returned for this comparison basis and as-of date.'
    case 'metric_unsupported':
      return 'This metric is not supported for the selected comparison basis.'
    case 'baseline_not_selected':
      return 'Select a baseline anchor before this trend metric can be shown.'
    case 'data_stale':
      return 'Trend data is refreshing; prior values are not shown as current.'
    default:
      return String(metric?.reason || '')
  }
}
