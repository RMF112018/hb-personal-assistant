export type ForecastHealthLevel = 'usable' | 'attention' | 'blocked_no_output' | 'failed_run'

export const HEALTH_PILL: Record<ForecastHealthLevel, string> = {
  usable: 'validated',
  attention: 'attention',
  blocked_no_output: 'invalid',
  failed_run: 'invalid',
}

/**
 * One-line "is this forecast usable?" verdict. Pure so it can be unit-tested directly. Priority:
 * a failed opened run first, then blocked/no-output, then a confidence/maturity caveat, else usable.
 *
 * Confidence/maturity are the HB readiness-based display labels from the DB-native v63 summary
 * ("High"/"Medium"/"Low"/"None"; "Full context" / "Schedule-informed" / "Cost-informed" /
 * "Baseline only" / "No financial basis") — NOT the v66 M0–M5 scorecard, which DB-native never
 * populates. A forecast is usable with strong confidence (High/Medium) and an informed maturity.
 */
export function deriveForecastHealth(i: {
  runFailed: boolean
  readinessBlocked: boolean
  hasOutput: boolean
  confidenceLabel: string | null | undefined
  maturityLabel: string | null | undefined
}): { level: ForecastHealthLevel; label: string; detail: string } {
  if (i.runFailed) {
    return {
      level: 'failed_run',
      label: 'Failed selected run',
      detail: 'The selected run did not complete; no forecast output was produced.',
    }
  }
  if (i.readinessBlocked || !i.hasOutput) {
    return {
      level: 'blocked_no_output',
      label: 'Blocked / no output',
      detail: 'No usable forecast output is available for this project yet.',
    }
  }
  const strongConfidence = i.confidenceLabel === 'High' || i.confidenceLabel === 'Medium'
  const informedMaturity =
    i.maturityLabel != null &&
    i.maturityLabel !== 'No financial basis' &&
    i.maturityLabel !== 'Baseline only'
  if (!strongConfidence || !informedMaturity) {
    return {
      level: 'attention',
      label: 'Needs attention',
      detail: 'Forecast output exists, but confidence or maturity is limited — review before relying on it.',
    }
  }
  return {
    level: 'usable',
    label: 'Usable',
    detail: 'Forecast output is available with adequate confidence and project maturity.',
  }
}
