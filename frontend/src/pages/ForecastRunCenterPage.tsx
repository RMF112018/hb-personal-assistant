/* Forecast Run Center — command surface. Generation is DB-native and persisted; it is launched only
 * from the Create Forecast modal (opening the modal never runs a forecast). */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  ForecastActionButton,
  ForecastBackLink,
  ForecastPageHeader,
  ForecastShell,
  ForecastSubnav,
} from '../components/forecast/ForecastPageChrome'
import {
  ForecastContextHeader,
  type ForecastReadinessPill,
} from '../components/forecast/ForecastContextHeader'
import { ForecastContextHealthCard } from '../components/forecast/ForecastContextHealthCard'
import { ForecastCreationModal } from '../components/forecast/ForecastCreationModal'
import { ForecastHistoryModal } from '../components/forecast/ForecastHistoryModal'
import { ForecastResultsSummary } from '../components/forecast/ForecastResultsSummary'
import { ForecastMonthlyMatrixPanel } from '../components/forecast/ForecastMonthlyMatrixPanel'
import { ForecastNarrativesPanel } from '../components/forecast/ForecastNarrativesPanel'
import { failureCodeCopy } from '../components/forecast/forecastRuntimeCopy'
import { api } from '../lib/api'

// UI-A: per-project readiness status → context-header pill variant.
function projectReadinessPill(status: string | undefined): ForecastReadinessPill {
  if (status === 'ready') return 'validated'
  if (status === 'degraded') return 'attention'
  if (status === 'blocked') return 'invalid'
  return 'unknown'
}

// UI-A: one plain-language "next step" line derived from the current selection.
function deriveNextAction(args: {
  projectKey: string | undefined
  selectedProjectObj: { readiness_status?: string; has_prior_forecast_output?: boolean } | undefined
}): string {
  const { projectKey, selectedProjectObj } = args
  if (!projectKey || !selectedProjectObj) {
    return 'Select a project to view its forecast.'
  }
  if (selectedProjectObj.readiness_status === 'blocked') {
    return 'Resolve readiness items before creating a forecast.'
  }
  if (selectedProjectObj.readiness_status === 'ready') {
    return selectedProjectObj.has_prior_forecast_output
      ? 'Review the latest forecast or create a new one.'
      : 'Create a forecast for this project.'
  }
  return 'Review readiness, then create a forecast for this project.'
}

// Client-side date order check (the <input type="date"> already enforces ISO YYYY-MM-DD format).
function dateOrderError(start: string, cutoff: string): string | null {
  if (start && cutoff && start > cutoff) return 'Start date must be on or before the cut-off date.'
  return null
}

// Operator month-window validation (the <input type="month"> enforces YYYY-MM format). Mirrors the
// backend contract: all four required; each window ordered; the forecast window starts strictly after
// the actuals window (no overlap). Returns operator-facing copy (no implementation terms) or null.
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

// P-D: cut-off basis code → plain-language label (table-name-free).
const CUTOFF_BASIS_LABEL: Record<string, string> = {
  schedule_data_date: 'Schedule data date',
  schedule_import_created_at: 'Schedule import date',
  latest_actual_activity_date: 'Latest actual activity date',
  operator_supplied: 'Operator supplied',
}
// P-D: schedule date-default warning code → plain-language copy.
const DATE_DEFAULT_WARNING_TEXT: Record<string, string> = {
  schedule_data_date_missing_using_import_date:
    'No schedule data date was found; using the schedule import date instead.',
  schedule_data_date_missing_using_activity_actual_date:
    'No schedule data or import date was found; using the latest actual activity date instead.',
  no_schedule_cutoff_default_available:
    'No schedule-derived cut-off date is available for this project; enter one manually.',
  no_forecast_start_default_available: 'No forecast start date could be derived for this project.',
  project_has_no_schedule_versions: 'This project has no committed schedule versions yet.',
  invalid_schedule_dates_ignored: 'Some schedule dates were invalid and were ignored.',
}

// Per-project readiness reason codes → actionable, table-name-free copy (P-B). Mirrors the backend
// reason codes from GET /api/forecast/generation/projects.
const PROJECT_READINESS_REASON_TEXT: Record<string, string> = {
  no_financial_basis: 'No budget, cost, or baseline data is available to forecast from yet.',
  missing_config_snapshot:
    'No configuration snapshot is available; a methodology default would be used (lower confidence).',
  missing_budget_cost_data: 'Budget and cost data is not available for this project yet.',
  missing_schedule_data: 'No schedule data has been imported for this project yet.',
  generation_disabled: "Generating from live configuration isn't enabled in this environment.",
  no_project_identity: 'This project cannot be resolved to a known source.',
  no_prior_forecast_output: 'No prior forecast has been generated for this project yet.',
}

export function ForecastRunCenterPage() {
  // P-E: bumped after a successful generation to force the DB-backed read-model panels to refetch.
  const [refreshNonce, setRefreshNonce] = useState(0)

  // Primary path: true DB-native generation (persists v63 outputs when the write gate is enabled).
  const [genDb, setGenDb] = useState(false)
  const [dbError, setDbError] = useState<string | null>(null)
  // True only when the primary run completed AND persisted — drives honest "saved" success copy.
  const [genCompleted, setGenCompleted] = useState(false)
  const [lastRequestId, setLastRequestId] = useState<string | null>(null)

  // Modal open state. Opening the Create Forecast modal must never run a forecast.
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [historyModalOpen, setHistoryModalOpen] = useState(false)

  // P-C/P-D: forecast window. Values are DERIVED at render from the schedule-derived resolver
  // defaults unless the operator has overridden them (null override = use the advisory default).
  const [startOverride, setStartOverride] = useState<string | null>(null)
  const [cutoffOverride, setCutoffOverride] = useState<string | null>(null)

  // Operator month windows (YYYY-MM) — the source of truth for the monthly matrix.
  const [actualsStartOverride, setActualsStartOverride] = useState<string | null>(null)
  const [actualsThroughOverride, setActualsThroughOverride] = useState<string | null>(null)
  const [forecastStartMonthOverride, setForecastStartMonthOverride] = useState<string | null>(null)
  const [forecastEndMonthOverride, setForecastEndMonthOverride] = useState<string | null>(null)

  // Page-owned active persisted output: the Forecast Summary selector and Forecast History modal
  // write it; every output-scoped panel (summary, monthly, decision support, narratives, health)
  // reads it so they stay in lockstep. Undefined = each panel falls back to its own latest output.
  const [activeOutputId, setActiveOutputId] = useState<string | undefined>(undefined)

  // P-B: project selector driven by the generation-ready project projection.
  const { data: projectsResp } = useQuery({
    queryKey: ['forecast', 'generation', 'projects'],
    queryFn: () => api.getForecastGenerationProjects(),
  })
  const projects = projectsResp?.projects ?? []
  const [projectKey, setProjectKey] = useState<string | undefined>(undefined)
  const selectedProjectObj = projects.find((p) => p.project_key === projectKey)
  const selectedBlocked = selectedProjectObj?.readiness_status === 'blocked'

  // P-C: durable request history for the selected project (history modal).
  const { data: requestsResp, refetch: refetchRequests } = useQuery({
    queryKey: ['forecast', 'generation', 'requests', projectKey],
    queryFn: () => api.getForecastGenerationRequests(projectKey),
    enabled: Boolean(projectKey),
  })
  const recentRequests = requestsResp?.requests ?? []

  // Persisted forecast outputs for the selected project (history modal). Shares the query key with
  // the output-scoped panels so React Query serves a single request.
  const { data: outputsResp } = useQuery({
    queryKey: ['forecast', 'db-outputs', projectKey],
    queryFn: () => api.getForecastDbOutputs(projectKey as string),
    enabled: Boolean(projectKey),
  })
  const outputs = outputsResp?.outputs ?? []

  // P-D: schedule-derived advisory date defaults for the selected project.
  const { data: dateDefaults } = useQuery({
    queryKey: ['forecast', 'generation', 'date-defaults', projectKey],
    queryFn: () => api.getForecastGenerationDateDefaults(projectKey as string),
    enabled: Boolean(projectKey),
  })

  // Derived forecast window: an operator override wins; otherwise the advisory resolver default fills
  // the (blank) field. No effects/auto-fill writes → operator edits are never clobbered.
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

  // Derived operator month windows (override wins; else the resolver default; else blank).
  const actualsStartMonth = actualsStartOverride ?? dateDefaults?.actuals_start_month ?? ''
  const actualsThroughMonth = actualsThroughOverride ?? dateDefaults?.actuals_through_month ?? ''
  const forecastStartMonth = forecastStartMonthOverride ?? dateDefaults?.forecast_start_month ?? ''
  const forecastEndMonth = forecastEndMonthOverride ?? dateDefaults?.forecast_end_month ?? ''

  // Live validation (no implementation terminology). Drives the modal's Submit disabled state.
  const monthWindowError = projectKey
    ? monthWindowValidation(actualsStartMonth, actualsThroughMonth, forecastStartMonth, forecastEndMonth)
    : null
  const dateOrderErr = dateOrderError(forecastStartDate, forecastCutoffDate)

  function onProjectChange(value: string) {
    setProjectKey(value || undefined)
    setStartOverride(null) // new project → fall back to its advisory defaults
    setCutoffOverride(null)
    setActualsStartOverride(null)
    setActualsThroughOverride(null)
    setForecastStartMonthOverride(null)
    setForecastEndMonthOverride(null)
    setLastRequestId(null)
    setGenCompleted(false)
    setDbError(null)
    setCreateModalOpen(false) // closing on project change is intentional (clears stale modal context)
    setActiveOutputId(undefined) // new project → fall back to its own latest persisted output
  }

  function onOpenCreateForecast() {
    if (!projectKey || selectedBlocked) return
    setDbError(null)
    setCreateModalOpen(true)
  }

  // Primary operator path: true DB-native generation. A request fails closed with HTTP 200 +
  // request_status="failed"/"rejected" and a curated failure_code; that is NOT a success. Success is
  // request_status="completed" AND db_persisted=true. Returns true only on that success.
  async function onGenerateDbNative(): Promise<boolean> {
    if (!projectKey) return false
    const windowErr = monthWindowValidation(
      actualsStartMonth,
      actualsThroughMonth,
      forecastStartMonth,
      forecastEndMonth,
    )
    if (windowErr || dateOrderErr) {
      setDbError(windowErr ?? dateOrderErr)
      return false
    }
    setGenDb(true)
    setDbError(null)
    setLastRequestId(null)
    setGenCompleted(false)
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
        // Curated copy only — never the raw failure_code. No success banner.
        setDbError(
          resp.failure_message ||
            failureCodeCopy(resp.failure_code) ||
            'The forecast request did not complete.',
        )
        return false
      }
      if (resp.request_status === 'completed' && resp.db_persisted) {
        setLastRequestId(resp.request_id ?? null)
        setGenCompleted(true)
        setRefreshNonce((n) => n + 1)
        await refetchRequests()
        return true
      }
      // Defensive: a non-failed status that did not persist is not a success we can claim.
      setDbError(failureCodeCopy(resp.failure_code) || 'The forecast request did not complete.')
      return false
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status
      setDbError(
        status === 503
          ? 'Forecast generation is not enabled in this environment.'
          : 'The forecast could not be started.',
      )
      return false
    } finally {
      setGenDb(false)
      await refetchRequests()
    }
  }

  async function submitCreateForecast() {
    const ok = await onGenerateDbNative()
    if (ok) setCreateModalOpen(false)
  }

  // UI-A: display-ready context-header props. The header is presentational, so the page resolves
  // reason codes here (via PROJECT_READINESS_REASON_TEXT, the single source of that copy).
  const headerReadinessReasons =
    selectedProjectObj && selectedProjectObj.readiness_status !== 'ready'
      ? selectedProjectObj.readiness_reasons.map(
          (code) =>
            PROJECT_READINESS_REASON_TEXT[code] ?? 'This project is not ready for generation.',
        )
      : []
  const nextAction = deriveNextAction({ projectKey, selectedProjectObj })
  const outputContext = activeOutputId
    ? 'Selected output'
    : outputs.length > 0
      ? 'Latest output'
      : 'No output selected'

  const cutoffBasisLabel = cutoffBasis
    ? (CUTOFF_BASIS_LABEL[cutoffBasis] ?? cutoffBasis)
    : 'No schedule-derived default available'
  const dateWarnings = (dateDefaults?.warnings ?? []).map(
    (w) => DATE_DEFAULT_WARNING_TEXT[w] ?? 'Schedule date information is incomplete.',
  )

  return (
    <ForecastShell>
      <ForecastBackLink />
      <ForecastSubnav />

      {/* Construction Forecasting / Project — primary entry point */}
      <section className="forecast-panel">
        <ForecastPageHeader
          eyebrow="Construction Forecasting"
          title="Project"
          subtitle="Select a project, then create a forecast using reviewed parameters and assumptions."
          actions={
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
                Project
                <select
                  aria-label="Forecast project"
                  className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm disabled:opacity-50"
                  value={projectKey ?? ''}
                  onChange={(e) => onProjectChange(e.target.value)}
                  disabled={projects.length === 0}
                >
                  <option value="" disabled>
                    Select a project
                  </option>
                  {projects.map((p) => (
                    <option key={p.project_key} value={p.project_key}>
                      {(p.display_name || p.project_key) +
                        (p.readiness_status !== 'ready' ? ` — ${p.readiness_status}` : '')}
                    </option>
                  ))}
                </select>
              </label>
              <ForecastActionButton
                onClick={onOpenCreateForecast}
                disabled={!projectKey || selectedBlocked || genDb}
              >
                Create Forecast
              </ForecastActionButton>
            </div>
          }
        />
        {projects.length === 0 && (
          <p className="text-sm text-[var(--hb-muted)] mt-2">No projects are available yet.</p>
        )}
        {projectKey && (
          <p className="text-sm text-[var(--hb-muted)] mt-3">
            Latest forecast:{' '}
            <span className="font-medium text-[var(--hb-text)]">
              {selectedProjectObj?.latest_forecast_display ?? 'None yet'}
            </span>
          </p>
        )}
        {selectedBlocked && (
          <p className="text-sm text-rose-300 mt-2" role="status">
            Resolve the readiness items below before creating a forecast.
          </p>
        )}
        {genCompleted && lastRequestId && (
          <p className="text-sm text-emerald-300 mt-2" role="status">
            Forecast generated and saved (tracking id {lastRequestId}).
          </p>
        )}
      </section>

      <ForecastContextHeader
        projectName={selectedProjectObj?.display_name ?? null}
        projectKey={projectKey ?? null}
        readinessStatus={
          selectedProjectObj ? projectReadinessPill(selectedProjectObj.readiness_status) : null
        }
        readinessReasons={headerReadinessReasons}
        latestForecastDisplay={selectedProjectObj?.latest_forecast_display ?? null}
        selectedRun={null}
        outputContext={outputContext}
        nextAction={nextAction}
        onOpenHistory={projectKey ? () => setHistoryModalOpen(true) : undefined}
        healthSlot={
          projectKey ? (
            <ForecastContextHealthCard
              key={`fh-${projectKey}-${refreshNonce}`}
              project={projectKey}
              readinessStatus={selectedProjectObj?.readiness_status ?? null}
              runFailed={false}
              activeOutputId={activeOutputId}
            />
          ) : undefined
        }
      />

      {projectKey ? (
        <>
          <ForecastResultsSummary
            key={`rs-${projectKey}-${refreshNonce}`}
            project={projectKey}
            activeOutputId={activeOutputId}
            onSelectOutput={setActiveOutputId}
          />
          <ForecastMonthlyMatrixPanel
            key={`mm-${projectKey}-${refreshNonce}`}
            project={projectKey}
            activeOutputId={activeOutputId}
          />
          <ForecastNarrativesPanel
            key={`nr-${projectKey}-${refreshNonce}`}
            project={projectKey}
            activeOutputId={activeOutputId}
          />
        </>
      ) : (
        <section className="forecast-panel">
          <h2 className="forecast-section-label">Forecast results</h2>
          <p className="text-sm text-[var(--hb-muted)]">
            Select a project to view its forecast results.
          </p>
        </section>
      )}

      <ForecastCreationModal
        open={createModalOpen}
        projectKey={projectKey ?? null}
        projectDisplayName={selectedProjectObj?.display_name ?? null}
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
        generating={genDb}
        submitError={dbError}
        submitDisabled={Boolean(monthWindowError) || Boolean(dateOrderErr) || selectedBlocked}
        onClose={() => setCreateModalOpen(false)}
        onSubmit={submitCreateForecast}
        onForecastStartDateChange={setStartOverride}
        onForecastCutoffDateChange={setCutoffOverride}
        onActualsStartMonthChange={setActualsStartOverride}
        onActualsThroughMonthChange={setActualsThroughOverride}
        onForecastStartMonthChange={setForecastStartMonthOverride}
        onForecastEndMonthChange={setForecastEndMonthOverride}
      />

      <ForecastHistoryModal
        open={historyModalOpen}
        onClose={() => setHistoryModalOpen(false)}
        outputs={outputs}
        requests={recentRequests}
        activeOutputId={activeOutputId}
        onSelectOutput={setActiveOutputId}
      />
    </ForecastShell>
  )
}
