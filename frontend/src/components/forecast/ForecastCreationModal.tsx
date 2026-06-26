/* Create Forecast modal. Holds the forecast parameter fields, operator month windows, and the
 * Forecast Assumptions section. Opening it must NOT run a forecast — only Submit does. Cancel,
 * backdrop click, and Escape close it without action (handled by ForecastDialog). All values and
 * change handlers are page-owned; this component is presentational. */
import { ForecastDialog } from './ForecastDialog'
import { ForecastAssumptionsSection } from './ForecastAssumptionsSection'

const FIELD_INPUT =
  'rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm'

export interface ForecastCreationModalProps {
  open: boolean
  projectKey: string | null
  projectDisplayName?: string | null

  forecastStartDate: string
  forecastCutoffDate: string
  cutoffBasisLabel: string
  dateWarnings: string[]
  dateError: string | null
  monthWindowError: string | null

  actualsStartMonth: string
  actualsThroughMonth: string
  forecastStartMonth: string
  forecastEndMonth: string

  generating: boolean
  submitError: string | null
  submitDisabled: boolean

  onClose: () => void
  onSubmit: () => void

  onForecastStartDateChange: (value: string) => void
  onForecastCutoffDateChange: (value: string) => void
  onActualsStartMonthChange: (value: string) => void
  onActualsThroughMonthChange: (value: string) => void
  onForecastStartMonthChange: (value: string) => void
  onForecastEndMonthChange: (value: string) => void
}

export function ForecastCreationModal({
  open,
  projectKey,
  projectDisplayName,
  forecastStartDate,
  forecastCutoffDate,
  cutoffBasisLabel,
  dateWarnings,
  dateError,
  monthWindowError,
  actualsStartMonth,
  actualsThroughMonth,
  forecastStartMonth,
  forecastEndMonth,
  generating,
  submitError,
  submitDisabled,
  onClose,
  onSubmit,
  onForecastStartDateChange,
  onForecastCutoffDateChange,
  onActualsStartMonthChange,
  onActualsThroughMonthChange,
  onForecastStartMonthChange,
  onForecastEndMonthChange,
}: ForecastCreationModalProps) {
  const title = projectDisplayName ? `Create forecast — ${projectDisplayName}` : 'Create forecast'

  return (
    <ForecastDialog
      open={open}
      onClose={onClose}
      title={title}
      description="Review the parameters and assumptions, then submit to generate a forecast."
      footer={
        <>
          <button type="button" className="forecast-btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="forecast-btn-primary"
            onClick={onSubmit}
            disabled={submitDisabled || generating || !projectKey}
          >
            {generating ? 'Generating…' : 'Submit'}
          </button>
        </>
      }
    >
      {/* Forecast parameters */}
      <h3 className="forecast-section-label">Forecast Parameters</h3>
      <div className="flex flex-wrap items-center gap-4 mt-2">
        <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
          Forecast start date
          <input
            type="date"
            aria-label="Forecast start date"
            value={forecastStartDate}
            onChange={(e) => onForecastStartDateChange(e.target.value)}
            className={FIELD_INPUT}
          />
        </label>
        <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
          Forecast cut-off date
          <input
            type="date"
            aria-label="Forecast cut-off date"
            value={forecastCutoffDate}
            onChange={(e) => onForecastCutoffDateChange(e.target.value)}
            className={FIELD_INPUT}
          />
        </label>
      </div>
      {projectKey && (
        <p className="text-xs text-[var(--hb-muted)] mt-1">Cut-off basis: {cutoffBasisLabel}</p>
      )}
      {dateWarnings.length > 0 && (
        <div className="text-xs text-amber-300 mt-1" role="status">
          {dateWarnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      {/* Operator month windows */}
      <h3 className="forecast-section-label mt-5">Forecast Month Windows</h3>
      <p className="text-xs text-[var(--hb-muted)] mt-0.5">
        Defaults populate from the project's actuals and schedule after selection — review and adjust,
        then submit.
      </p>
      <div className="flex flex-wrap items-center gap-4 mt-2">
        <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
          Actuals start month
          <input
            type="month"
            aria-label="Actuals start month"
            value={actualsStartMonth}
            onChange={(e) => onActualsStartMonthChange(e.target.value)}
            className={FIELD_INPUT}
          />
        </label>
        <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
          Actuals through month
          <input
            type="month"
            aria-label="Actuals through month"
            value={actualsThroughMonth}
            onChange={(e) => onActualsThroughMonthChange(e.target.value)}
            className={FIELD_INPUT}
          />
        </label>
        <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
          Forecast start month
          <input
            type="month"
            aria-label="Forecast start month"
            value={forecastStartMonth}
            onChange={(e) => onForecastStartMonthChange(e.target.value)}
            className={FIELD_INPUT}
          />
        </label>
        <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
          Forecast end month
          <input
            type="month"
            aria-label="Forecast end month"
            value={forecastEndMonth}
            onChange={(e) => onForecastEndMonthChange(e.target.value)}
            className={FIELD_INPUT}
          />
        </label>
      </div>
      {projectKey && monthWindowError && (
        <p className="text-xs text-amber-300 mt-1" role="status">
          {monthWindowError}
        </p>
      )}
      {dateError && (
        <p className="text-sm text-rose-300 mt-2" role="status">
          {dateError}
        </p>
      )}

      {/* Forecast assumptions */}
      <h3 className="forecast-section-label mt-5">Forecast Assumptions</h3>
      {projectKey ? (
        <ForecastAssumptionsSection project={projectKey} />
      ) : (
        <p className="text-sm text-[var(--hb-muted)] mt-2">Select a project to capture assumptions.</p>
      )}

      {submitError && (
        <p className="text-sm text-rose-300 mt-3" role="status">
          {submitError}
        </p>
      )}
    </ForecastDialog>
  )
}
