export type StatusCopy = {
  label: string
  description: string
  tone: 'neutral' | 'success' | 'attention' | 'danger'
}

const authStatusCopy: Record<string, StatusCopy> = {
  never_connected: {
    label: 'Not connected',
    description: 'Connect this account before source data can appear.',
    tone: 'attention',
  },
  connected_valid: {
    label: 'Connected',
    description: 'The local connection is available.',
    tone: 'success',
  },
  connected_refreshing: {
    label: 'Refreshing',
    description: 'The local connection is refreshing.',
    tone: 'attention',
  },
  connected_stale_refreshable: {
    label: 'Needs refresh',
    description: 'Refresh the local connection to keep data current.',
    tone: 'attention',
  },
  connected_stale_reauth_required: {
    label: 'Reconnect required',
    description: 'Reconnect this account before new data can be collected.',
    tone: 'danger',
  },
  connected_error: {
    label: 'Connection issue',
    description: 'The local connection needs attention.',
    tone: 'danger',
  },
  disconnected_by_user: {
    label: 'Disconnected',
    description: 'This account was disconnected locally.',
    tone: 'neutral',
  },
}

const freshnessCopy: Record<string, StatusCopy> = {
  fresh: {
    label: 'Fresh',
    description: 'Data was updated recently.',
    tone: 'success',
  },
  stale: {
    label: 'Stale',
    description: 'Some data may need a refresh.',
    tone: 'attention',
  },
  unknown: {
    label: 'Unknown',
    description: 'Freshness is not available yet.',
    tone: 'neutral',
  },
}

const confidenceCopy: Record<string, StatusCopy> = {
  source_backed: {
    label: 'Source-backed',
    description: 'Signals are linked to approved local sources.',
    tone: 'success',
  },
  in_progress: {
    label: 'Building',
    description: 'Confidence is still being assembled.',
    tone: 'attention',
  },
  not_available: {
    label: 'Limited data',
    description: 'There is not enough source data yet.',
    tone: 'neutral',
  },
}

const dataQualityCopy: Record<string, StatusCopy> = {
  good: {
    label: 'Good',
    description: 'Approved sources are current.',
    tone: 'success',
  },
  degraded: {
    label: 'Needs attention',
    description: 'Some approved sources are stale or pending.',
    tone: 'attention',
  },
  unknown: {
    label: 'Needs attention',
    description: 'Data quality is not available yet.',
    tone: 'attention',
  },
  poor: {
    label: 'Poor',
    description: 'Approved source data has not been collected yet.',
    tone: 'danger',
  },
}

const sourceStateCopy: Record<string, StatusCopy> = {
  connected_valid: {
    label: 'Connected',
    description: 'The source is connected and verified.',
    tone: 'success',
  },
  reauth_required: {
    label: 'Reconnect required',
    description: 'Re-authorization is required for this source.',
    tone: 'danger',
  },
  connected_stale_reauth_required: {
    label: 'Reconnect required',
    description: 'Re-authorization is required for this source.',
    tone: 'danger',
  },
  cache_present_unverified: {
    label: 'Cache present (unverified)',
    description: 'Local cache exists but has not been verified.',
    tone: 'attention',
  },
  not_connected: {
    label: 'Not connected',
    description: 'This source is not connected.',
    tone: 'attention',
  },
  never_connected: {
    label: 'Not connected',
    description: 'This source is not connected.',
    tone: 'attention',
  },
  not_configured: {
    label: 'Not configured',
    description: 'This source has not been configured.',
    tone: 'neutral',
  },
  configured_not_connected: {
    label: 'Configured but not connected',
    description: 'Configuration is present but the source is not connected.',
    tone: 'attention',
  },
}

const fallbackCopy: StatusCopy = {
  label: 'Unknown',
  description: 'Status is not available yet.',
  tone: 'neutral',
}

export function getAuthStatusCopy(status: string | null | undefined): StatusCopy {
  return copyFrom(authStatusCopy, status)
}

export function getFreshnessCopy(status: string | null | undefined): StatusCopy {
  return copyFrom(freshnessCopy, status)
}

export function getConfidenceCopy(status: string | null | undefined): StatusCopy {
  return copyFrom(confidenceCopy, status)
}

export function getDataQualityCopy(status: string | null | undefined): StatusCopy {
  return copyFrom(dataQualityCopy, status)
}

export function getSourceStateCopy(status: string | null | undefined): StatusCopy {
  return copyFrom(sourceStateCopy, status)
}

function copyFrom(source: Record<string, StatusCopy>, status: string | null | undefined): StatusCopy {
  if (!status) return fallbackCopy
  return source[status.toLowerCase()] || fallbackCopy
}
