import { Link } from 'react-router-dom'

function text(value: unknown, fallback = 'Not available') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function toneFor(status: unknown) {
  const value = String(status || '').toLowerCase()
  if (value === 'good' || value === 'trusted' || value === 'ready') return 'border-emerald-800/70'
  if (value === 'watch' || value === 'degraded') return 'border-amber-800/70'
  if (
    value === 'at_risk' ||
    value === 'blocked' ||
    value === 'review_required' ||
    value === 'excluded' ||
    value === 'mismatch' ||
    value === 'ambiguous'
  ) {
    return 'border-red-900/70'
  }
  return 'border-[var(--hb-border)]'
}

type Props = {
  scheduleTrust?: Record<string, unknown>
  identityReview?: Record<string, unknown>
  analyticsTrust?: Record<string, unknown>
}

export function TrustBanner({ scheduleTrust = {}, identityReview = {}, analyticsTrust = {} }: Props) {
  const identityTrust = (analyticsTrust.identity_trust as Record<string, unknown> | undefined) || {}
  const identityStatus = String(
    identityTrust.identity_trust_status ||
      identityReview.identity_trust_status ||
      scheduleTrust.status ||
      identityReview.status ||
      'unknown',
  )
  const analyticsStatus = String(analyticsTrust.analytics_trust_status || '')
  const gate = String(identityTrust.identity_gate || identityReview.identity_gate || analyticsTrust.identity_gate || '')

  if (identityStatus === 'trusted' && analyticsStatus === 'ready') return null
  if (identityStatus === 'trusted' && !analyticsStatus) return null

  const reasons = [
    ...(Array.isArray(identityTrust.safe_reasons) ? (identityTrust.safe_reasons as string[]) : []),
    ...(Array.isArray(scheduleTrust.review_reasons) ? (scheduleTrust.review_reasons as string[]) : []),
    ...(Array.isArray(identityReview.safe_reasons) ? (identityReview.safe_reasons as string[]) : []),
  ].filter(Boolean)

  const pmMessage = text(
    identityTrust.pm_message || identityReview.pm_message,
    gate === 'blocked'
      ? 'Schedule analytics are blocked until identity trust is resolved.'
      : 'Schedule comparisons are gated until identity and series membership are resolved.',
  )
  const reviewUrl = text(identityReview.identity_review_url, '/schedules/identity-review')

  return (
    <div className={`card ${toneFor(identityStatus === 'trusted' ? analyticsStatus || identityStatus : identityStatus)}`}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--hb-muted)]">Schedule Identity Trust</div>
          <div className="mt-1 font-semibold capitalize">{identityStatus.replaceAll('_', ' ')}</div>
          {analyticsStatus ? (
            <div className="text-xs text-[var(--hb-muted)]">
              Analytics trust: {analyticsStatus.replaceAll('_', ' ')}
              {gate ? ` · Identity gate: ${gate}` : ''}
            </div>
          ) : null}
          <p className="mt-1 text-sm text-[var(--hb-muted)]">{pmMessage}</p>
          {reasons.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {reasons.slice(0, 4).map((reason) => (
                <span key={reason} className="badge">
                  {reason}
                </span>
              ))}
            </div>
          )}
        </div>
        {(identityReview.operator_action_required || identityTrust.operator_action_required) && (
          <Link className="badge shrink-0" to={reviewUrl}>
            Open Identity Review
          </Link>
        )}
      </div>
    </div>
  )
}
