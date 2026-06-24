import { Compass } from 'lucide-react'

import { ForecastPanel } from './ForecastPrimitives'
import { ForecastStatusPill } from './ForecastStatusPill'
import { ForecastSummaryCard, ForecastSummaryGrid } from './ForecastSummary'

export type ForecastReadinessPill = 'validated' | 'attention' | 'invalid' | 'unknown'

/**
 * Presentational context header for the Forecast Run Center. It answers, at a glance,
 * "which project / run / output am I looking at, and what is the next step?". All copy is
 * resolved by the caller and passed in as display-ready strings — this component owns no data
 * fetching and no code→copy maps, so it never emits raw stamps, paths, or payloads.
 */
export interface ForecastContextHeaderProps {
  /** Selected project display name, or null when nothing is selected. */
  projectName: string | null
  /** Selected project key, shown as a secondary identifier. */
  projectKey: string | null
  /** Readiness pill status, already mapped by the caller. Null when no project is selected. */
  readinessStatus: ForecastReadinessPill | null
  /** Plain-language readiness reason lines (already mapped from codes). Empty when ready/none. */
  readinessReasons: string[]
  /** Latest forecast display string (e.g. 'Jun 19, 2026'), or null when none exists. */
  latestForecastDisplay: string | null
  /** Selected run label + status when a run is opened; null when no run is opened. */
  selectedRun: { label: string; status: string } | null
  /** Viewed-output context line (e.g. 'No output selected'). */
  outputContext: string
  /** One plain-language next-action line, derived by the caller. */
  nextAction: string
}

export function ForecastContextHeader({
  projectName,
  projectKey,
  readinessStatus,
  readinessReasons,
  latestForecastDisplay,
  selectedRun,
  outputContext,
  nextAction,
}: ForecastContextHeaderProps) {
  return (
    <ForecastPanel
      icon={Compass}
      title="Forecast context"
      description="What you're viewing right now and the next step for this project."
    >
      <ForecastSummaryGrid>
        <ForecastSummaryCard
          label="Project"
          value={projectName ?? 'No project selected'}
          detail={projectKey ?? undefined}
        />
        <div className="forecast-metric-card">
          <div className="forecast-metric-label">Project readiness</div>
          <div className="forecast-metric-value mt-1">
            {readinessStatus ? (
              <ForecastStatusPill status={readinessStatus} />
            ) : (
              <span className="text-sm text-[var(--hb-muted)]">—</span>
            )}
          </div>
        </div>
        <ForecastSummaryCard label="Latest forecast" value={latestForecastDisplay ?? 'None yet'} />
        <ForecastSummaryCard label="Viewed output" value={outputContext} />
      </ForecastSummaryGrid>

      {readinessReasons.length > 0 && (
        <div className="text-sm text-rose-300 mt-3" role="status">
          {readinessReasons.map((reason) => (
            <p key={reason}>{reason}</p>
          ))}
        </div>
      )}

      {selectedRun && (
        <p className="text-sm mt-3">
          Selected run: <span className="font-medium">{selectedRun.label}</span>
          {' · '}Status: <span className="font-medium">{selectedRun.status}</span>
        </p>
      )}

      <p className="text-sm text-[var(--hb-muted)] mt-3">
        <span className="font-medium text-[var(--hb-fg,inherit)]">Next step:</span> {nextAction}
      </p>
    </ForecastPanel>
  )
}
