import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { ForecastCreationModal } from '../forecast/ForecastCreationModal'
import { failureCodeCopy } from '../forecast/forecastRuntimeCopy'

// Cut-off basis code → plain-language label (table-name-free). Mirrors the global Run Center labels.
const CUTOFF_BASIS_LABEL: Record<string, string> = {
  schedule_data_date: 'Schedule data date',
  schedule_import_created_at: 'Schedule import date',
  latest_actual_activity_date: 'Latest actual activity date',
  operator_supplied: 'Operator supplied',
}

// Schedule date-default warning code → plain-language copy.
const DATE_DEFAULT_WARNING_TEXT: Record<string, string> = {
  schedule_data_date_missing_using_import_date:
    'No schedule data date was found; using the schedule import date instead.',
  schedule_data_date_missing_using_activity_actual_date:
    'No schedule data or import date was found; using the latest actual activity date instead.',
  no_schedule_cutoff_default_available:
    'No schedule-derived cut-off date is available for this project; enter one manually.',
  no_forecast_start_default_available: 'No forecast start date could be derived for this project.',
  project_has_no_schedule_versions: 'This project has no committed schedule versions yet.',
}

const GENERIC_SUBMIT_ERROR =
  'Forecast could not be created. Check the local data connection and try again.'

// Client-side date order check (the <input type="date"> already enforces ISO YYYY-MM-DD format).
function dateOrderError(start: string, cutoff: string): string | null {
  if (start && cutoff && start > cutoff) return 'Start date must be on or before the cut-off date.'
  return null
}

// Operator month-window validation (the <input type="month"> enforces YYYY-MM format). Mirrors the
// backend contract: all four required; each window ordered; the forecast window starts strictly after
// the actuals window. Returns operator-facing copy (no implementation terms) or null.
function monthWindowValidation(
  actualsStart: string,
  actualsThrough: string,
  forecastStart: string,
  forecastEnd: string,
): string | null {
  if (!actualsStart || !actualsThrough || !forecastStart || !forecastEnd) {
    return 'Select all four month windows to create a forecast.'
  }
  if (actualsStart > actualsThrough) {
    return 'Actuals start month must be on or before the actuals-through month.'
  }
  if (forecastStart > forecastEnd) {
    return 'Forecast start month must be on or before the forecast end month.'
  }
  if (forecastStart <= actualsThrough) {
    return 'The forecast window must start after the actuals window.'
  }
  return null
}

/**
 * Project-scoped forecast creation entry point. Renders the "Create Forecast" card + button and owns
 * the presentational {@link ForecastCreationModal}, driven entirely by the route projectKey. Window
 * fields prefill from the project's schedule-derived advisory defaults (override > default > blank —
 * never a global fallback). Submit calls the DB-native generation API with an explicit project_key;
 * on success it invalidates only the project-scoped forecast reads and closes the modal.
 */
export function ProjectForecastCreationCard({ projectKey }: { projectKey: string }) {
  const queryClient = useQueryClient()

  // Cached by the workspace shell; used only to resolve the modal title.
  const { data: projectsResp } = useQuery({ queryKey: ['projects'], queryFn: api.getProjects })
  const projectDisplayName =
    projectsResp?.projects.find((p) => p.project_key === projectKey)?.display_name ?? projectKey

  const { data: dateDefaults } = useQuery({
    queryKey: ['forecast', 'generation', 'date-defaults', projectKey],
    queryFn: () => api.getForecastGenerationDateDefaults(projectKey),
  })

  const [modalOpen, setModalOpen] = useState(false)
  const [startOverride, setStartOverride] = useState<string | null>(null)
  const [cutoffOverride, setCutoffOverride] = useState<string | null>(null)
  const [actualsStartOverride, setActualsStartOverride] = useState<string | null>(null)
  const [actualsThroughOverride, setActualsThroughOverride] = useState<string | null>(null)
  const [forecastStartMonthOverride, setForecastStartMonthOverride] = useState<string | null>(null)
  const [forecastEndMonthOverride, setForecastEndMonthOverride] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Override wins; otherwise the advisory schedule default fills the blank field; otherwise blank.
  // No effects/auto-fill writes, so operator edits are never clobbered and there is no global default.
  const forecastStartDate = startOverride ?? dateDefaults?.forecast_start_date ?? ''
  const forecastCutoffDate = cutoffOverride ?? dateDefaults?.forecast_cutoff_date ?? ''
  const cutoffBasis: string | null =
    cutoffOverride !== null
      ? cutoffOverride
        ? 'operator_supplied'
        : null
      : forecastCutoffDate
        ? (dateDefaults?.forecast_cutoff_date_basis ?? null)
        : null
  const actualsStartMonth = actualsStartOverride ?? dateDefaults?.actuals_start_month ?? ''
  const actualsThroughMonth = actualsThroughOverride ?? dateDefaults?.actuals_through_month ?? ''
  const forecastStartMonth = forecastStartMonthOverride ?? dateDefaults?.forecast_start_month ?? ''
  const forecastEndMonth = forecastEndMonthOverride ?? dateDefaults?.forecast_end_month ?? ''

  const monthWindowError = monthWindowValidation(
    actualsStartMonth,
    actualsThroughMonth,
    forecastStartMonth,
    forecastEndMonth,
  )
  const dateOrderErr = dateOrderError(forecastStartDate, forecastCutoffDate)
  const submitDisabled = Boolean(monthWindowError) || Boolean(dateOrderErr)

  const cutoffBasisLabel = cutoffBasis ? (CUTOFF_BASIS_LABEL[cutoffBasis] ?? cutoffBasis) : ''
  const dateWarnings = (dateDefaults?.warnings ?? []).map(
    (w) => DATE_DEFAULT_WARNING_TEXT[w] ?? 'Schedule date information is incomplete.',
  )

  function openModal() {
    setSubmitError(null)
    setModalOpen(true)
  }

  async function onSubmit() {
    const windowErr = monthWindowValidation(
      actualsStartMonth,
      actualsThroughMonth,
      forecastStartMonth,
      forecastEndMonth,
    )
    if (windowErr || dateOrderErr) {
      setSubmitError(windowErr ?? dateOrderErr)
      return
    }
    setGenerating(true)
    setSubmitError(null)
    try {
      const resp = await api.startForecastDbNativeRun({
        project_key: projectKey,
        forecast_start_date: forecastStartDate || null,
        forecast_cutoff_date: forecastCutoffDate || null,
        forecast_cutoff_date_basis: forecastCutoffDate ? cutoffBasis : null,
        actuals_start_month: actualsStartMonth || null,
        actuals_through_month: actualsThroughMonth || null,
        forecast_start_month: forecastStartMonth || null,
        forecast_end_month: forecastEndMonth || null,
      })
      if (resp.request_status === 'failed' || resp.request_status === 'rejected') {
        // Curated copy only — never the raw failure_code or any implementation detail.
        setSubmitError(resp.failure_message || failureCodeCopy(resp.failure_code) || GENERIC_SUBMIT_ERROR)
        return
      }
      if (resp.request_status === 'completed' && resp.db_persisted) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['forecast', 'db-outputs', projectKey] }),
          queryClient.invalidateQueries({ queryKey: ['forecast', 'db-output'] }),
          queryClient.invalidateQueries({ queryKey: ['forecast', 'db-monthly-table'] }),
        ])
        setModalOpen(false)
        return
      }
      // Defensive: a non-failed status that did not persist is not a success we can claim.
      setSubmitError(failureCodeCopy(resp.failure_code) || GENERIC_SUBMIT_ERROR)
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status
      setSubmitError(
        status === 503 ? 'Forecast generation is not enabled in this environment.' : GENERIC_SUBMIT_ERROR,
      )
    } finally {
      setGenerating(false)
    }
  }

  return (
    <>
      <SectionCard
        title="Create Forecast"
        actions={
          <button type="button" className="badge" onClick={openModal}>
            Create Forecast
          </button>
        }
      >
        <p className="text-sm text-[var(--hb-muted)]">
          Create a new forecast run for this project using the selected forecast window and
          assumptions.
        </p>
      </SectionCard>

      <ForecastCreationModal
        open={modalOpen}
        projectKey={projectKey}
        projectDisplayName={projectDisplayName}
        forecastStartDate={forecastStartDate}
        forecastCutoffDate={forecastCutoffDate}
        cutoffBasisLabel={cutoffBasisLabel}
        dateWarnings={dateWarnings}
        dateError={dateOrderErr}
        monthWindowError={monthWindowError}
        actualsStartMonth={actualsStartMonth}
        actualsThroughMonth={actualsThroughMonth}
        forecastStartMonth={forecastStartMonth}
        forecastEndMonth={forecastEndMonth}
        generating={generating}
        submitError={submitError}
        submitDisabled={submitDisabled}
        onClose={() => setModalOpen(false)}
        onSubmit={onSubmit}
        onForecastStartDateChange={setStartOverride}
        onForecastCutoffDateChange={setCutoffOverride}
        onActualsStartMonthChange={setActualsStartOverride}
        onActualsThroughMonthChange={setActualsThroughOverride}
        onForecastStartMonthChange={setForecastStartMonthOverride}
        onForecastEndMonthChange={setForecastEndMonthOverride}
      />
    </>
  )
}
