/* Forecast generation — isolated packages; never writes live data (Phase 3). */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  ForecastActionButton,
  ForecastBackLink,
  ForecastPageHeader,
  ForecastQuickLink,
  ForecastShell,
  ForecastSubnav,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from '../components/forecast/ForecastPageChrome'
import {
  ForecastContextHeader,
  type ForecastReadinessPill,
} from '../components/forecast/ForecastContextHeader'
import { ForecastErrorCallout } from '../components/forecast/ForecastErrorCallout'
import { ForecastGeneratePanel } from '../components/forecast/ForecastGeneratePanel'
import { ForecastHealthSummary } from '../components/forecast/ForecastHealthSummary'
import { ForecastResultsSummary } from '../components/forecast/ForecastResultsSummary'
import { ForecastMonthlyMatrixPanel } from '../components/forecast/ForecastMonthlyMatrixPanel'
import { ForecastDecisionSupportPanel } from '../components/forecast/ForecastDecisionSupportPanel'
import { ForecastNarrativesPanel } from '../components/forecast/ForecastNarrativesPanel'
import { ForecastOperatorAssumptionsPanel } from '../components/forecast/ForecastOperatorAssumptionsPanel'
import { ForecastStatusPill } from '../components/forecast/ForecastStatusPill'
import { failureCodeCopy } from '../components/forecast/forecastRuntimeCopy'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'
import type { ForecastGeneratorKind } from '../lib/api'

type Selected = { id: string; source: 'file' | 'live_config' }

const GENERATOR_KINDS: { value: ForecastGeneratorKind; label: string }[] = [
  { value: 'comprehensive', label: 'Comprehensive' },
  { value: 'model_controls', label: 'Model controls' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'probability', label: 'Probabilistic' },
]

function runStatusPill(status: string | undefined): string {
  if (status === 'succeeded' || status === 'generated' || status === 'completed') return 'validated'
  if (status === 'rejected') return 'rejected'
  if (status === 'failed') return 'failed'
  return 'attention'
}

// UI-A: per-project readiness status → context-header pill variant.
function projectReadinessPill(status: string | undefined): ForecastReadinessPill {
  if (status === 'ready') return 'validated'
  if (status === 'degraded') return 'attention'
  if (status === 'blocked') return 'invalid'
  return 'unknown'
}

// UI-A: one plain-language "next step" line derived from the current selection. A failed opened run
// takes priority so the operator is told explicitly that no output was produced.
function deriveNextAction(args: {
  projectKey: string | undefined
  selectedProjectObj: { readiness_status?: string; has_prior_forecast_output?: boolean } | undefined
  detail: Record<string, unknown> | null
}): string {
  const { projectKey, selectedProjectObj, detail } = args
  const runStatus = detail?.status as string | undefined
  if (detail && (runStatus === 'failed' || runStatus === 'rejected')) {
    return 'The selected run did not complete; no forecast output was produced.'
  }
  if (!projectKey || !selectedProjectObj) {
    return 'Select a project to view its forecast.'
  }
  if (selectedProjectObj.readiness_status === 'blocked') {
    return 'Resolve readiness items before generating.'
  }
  if (selectedProjectObj.readiness_status === 'ready') {
    return selectedProjectObj.has_prior_forecast_output
      ? 'Review the latest forecast or generate a new one.'
      : 'Generate a forecast for this project.'
  }
  return 'Review readiness, then generate a forecast for this project.'
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
    return 'Select all four month windows to generate a forecast.'
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

// Coded readiness reasons → actionable, path-free copy. Mirrors the backend reason codes from
// GET /api/forecast/generation/readiness so an operator sees WHY generation is blocked before click.
const READINESS_REASON_TEXT: Record<string, string> = {
  db_config_run_disabled: "Generating from live configuration isn't enabled in this environment.",
  forecast_runtime_storage_not_configured: 'Forecast storage is not configured yet.',
  config_db_not_ready: 'The configuration database is not available yet.',
  cfr_src_not_available: 'The forecast engine source is not available.',
}

// Non-blocking readiness advisories (generation is allowed, but may not produce useful output).
const READINESS_WARNING_TEXT: Record<string, string> = {
  config_db_has_no_snapshots:
    'No configuration snapshot has been promoted yet, so generation may have nothing to run.',
}

// Action codes from the backend mapped to UI routes (the backend stays path/route-free). Codes
// without a route render as plain label text.
const READINESS_ACTION_ROUTE: Record<string, string> = {
  enable_db_config_run: '/forecasting/runtime',
  open_storage_settings: '/forecasting/runtime',
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
  const { data: runsResp, isLoading, error, refetch } = useQuery({
    queryKey: ['forecast', 'runs'],
    queryFn: () => api.getForecastRuns(),
  })
  const { data: dbRunsResp, refetch: refetchDb } = useQuery({
    queryKey: ['forecast', 'runs', 'db-config'],
    queryFn: () => api.getForecastDbConfigRuns(),
  })
  // Readiness for DB-config-backed generation: lets us disable the control BEFORE click and explain
  // why, instead of catching a raw 503 afterwards. The backend POST stays fail-closed regardless.
  const { data: readiness } = useQuery({
    queryKey: ['forecast', 'generation', 'readiness'],
    queryFn: () => api.getForecastGenerationReadiness(),
    staleTime: 15_000,
  })

  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [genUnconfigured, setGenUnconfigured] = useState(false)
  // P-E: bumped after a successful generation to force the DB-backed read-model panels to refetch.
  const [refreshNonce, setRefreshNonce] = useState(0)

  // Primary path: true DB-native generation (persists v63 outputs when the write gate is enabled).
  const [genDb, setGenDb] = useState(false)
  const [dbError, setDbError] = useState<string | null>(null)
  const [dbDisabled, setDbDisabled] = useState(false)
  // True only when the primary run completed AND persisted — drives honest "saved" success copy.
  const [genCompleted, setGenCompleted] = useState(false)

  // Legacy package-backed DB-config (live-config snapshot) path — kept behind the advanced disclosure.
  const [genDbCfg, setGenDbCfg] = useState(false)
  const [dbCfgError, setDbCfgError] = useState<string | null>(null)
  const [dbCfgDisabled, setDbCfgDisabled] = useState(false)
  const [genKind, setGenKind] = useState<ForecastGeneratorKind>('comprehensive')

  // P-C/P-D: forecast window. Values are DERIVED at render from the schedule-derived resolver
  // defaults unless the operator has overridden them (null override = use the advisory default).
  // Editing flips the cut-off basis to operator_supplied. (Derived below, after the defaults query.)
  const [startOverride, setStartOverride] = useState<string | null>(null)
  const [cutoffOverride, setCutoffOverride] = useState<string | null>(null)
  const [dateError, setDateError] = useState<string | null>(null)
  const [lastRequestId, setLastRequestId] = useState<string | null>(null)

  // Operator month windows (YYYY-MM) — the source of truth for the monthly matrix. Like the dates,
  // values are derived from the schedule-resolver defaults unless the operator overrides them.
  const [actualsStartOverride, setActualsStartOverride] = useState<string | null>(null)
  const [actualsThroughOverride, setActualsThroughOverride] = useState<string | null>(null)
  const [forecastStartMonthOverride, setForecastStartMonthOverride] = useState<string | null>(null)
  const [forecastEndMonthOverride, setForecastEndMonthOverride] = useState<string | null>(null)

  const [selected, setSelected] = useState<Selected | undefined>(undefined)

  // Page-owned active persisted output: the Forecast Summary selector writes it; every output-scoped
  // panel (summary, decision support, narratives, health) reads it so they stay in lockstep. Undefined
  // = each panel falls back to its own latest output (same list → same default, still consistent).
  const [activeOutputId, setActiveOutputId] = useState<string | undefined>(undefined)

  // P-B: project selector driven by the generation-ready project projection (procore identity + committed
  // schedule + forecast outputs), with per-project readiness. No 'tropical' fallback for generation.
  const { data: projectsResp } = useQuery({
    queryKey: ['forecast', 'generation', 'projects'],
    queryFn: () => api.getForecastGenerationProjects(),
  })
  const projects = projectsResp?.projects ?? []
  const [projectKey, setProjectKey] = useState<string | undefined>(undefined)
  const selectedProjectObj = projects.find((p) => p.project_key === projectKey)
  const selectedBlocked = selectedProjectObj?.readiness_status === 'blocked'

  // P-C: durable request history for the selected project.
  const { data: requestsResp, refetch: refetchRequests } = useQuery({
    queryKey: ['forecast', 'generation', 'requests', projectKey],
    queryFn: () => api.getForecastGenerationRequests(projectKey),
    enabled: Boolean(projectKey),
  })
  const recentRequests = requestsResp?.requests ?? []

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
  // Live month-window validation (YYYY-MM strings compare correctly). Drives the disabled state +
  // operator-facing messages without any implementation terminology.
  const monthWindowError = projectKey
    ? monthWindowValidation(actualsStartMonth, actualsThroughMonth, forecastStartMonth, forecastEndMonth)
    : null

  function onCutoffChange(value: string) {
    setCutoffOverride(value)
  }
  function onStartChange(value: string) {
    setStartOverride(value)
  }
  function onProjectChange(value: string) {
    setProjectKey(value || undefined)
    setStartOverride(null) // new project → fall back to its advisory defaults
    setCutoffOverride(null)
    setActualsStartOverride(null)
    setActualsThroughOverride(null)
    setForecastStartMonthOverride(null)
    setForecastEndMonthOverride(null)
    setDateError(null)
    setLastRequestId(null)
    setGenCompleted(false)
    setActiveOutputId(undefined) // new project → fall back to its own latest persisted output
  }

  const { data: detailResp } = useQuery({
    queryKey: ['forecast', 'run-detail', selected?.source, selected?.id],
    queryFn: () =>
      selected?.source === 'live_config'
        ? api.getForecastDbConfigRun(selected.id)
        : api.getForecastRun(selected!.id),
    enabled: Boolean(selected),
  })

  async function onGenerate() {
    if (!projectKey) return
    const orderErr = dateOrderError(forecastStartDate, forecastCutoffDate)
    if (orderErr) {
      setDateError(orderErr)
      return
    }
    setDateError(null)
    setGenerating(true)
    setGenError(null)
    setGenUnconfigured(false)
    setLastRequestId(null)
    try {
      const resp = await api.startForecastRun({
        project_key: projectKey,
        forecast_start_date: forecastStartDate || null,
        forecast_cutoff_date: forecastCutoffDate || null,
        forecast_cutoff_date_basis: forecastCutoffDate ? cutoffBasis : null,
      })
      setLastRequestId((resp as { request_id?: string })?.request_id ?? null)
      setRefreshNonce((n) => n + 1)
      await refetch()
      await refetchRequests()
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status
      setGenUnconfigured(status === 503)
      setGenError(
        status === 503
          ? 'Generation is not ready yet. Check storage settings first.'
          : 'Forecast generation could not be started.',
      )
    } finally {
      setGenerating(false)
    }
  }

  // Primary operator path: true DB-native generation (persists v63 outputs when the write gate is on).
  // Restricted to the comprehensive kind. A request fails closed with HTTP 200 + request_status=
  // "failed"/"rejected" and a curated failure_code (e.g. run_output_db_write_disabled,
  // db_native_insufficient_basis); that is NOT a success. Success is request_status="completed" AND
  // db_persisted=true.
  async function onGenerateDbNative() {
    if (!projectKey) return
    // Operator month windows are the source of truth for the matrix; validate them first.
    const windowErr = monthWindowValidation(
      actualsStartMonth,
      actualsThroughMonth,
      forecastStartMonth,
      forecastEndMonth,
    )
    if (windowErr) {
      setDateError(windowErr)
      return
    }
    setDateError(null)
    setGenDb(true)
    setDbError(null)
    setDbDisabled(false)
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
        setLastRequestId(null)
      } else if (resp.request_status === 'completed' && resp.db_persisted) {
        setLastRequestId(resp.request_id ?? null)
        setGenCompleted(true)
      } else {
        // Defensive: a non-failed status that did not persist is not a success we can claim.
        setDbError(failureCodeCopy(resp.failure_code) || 'The forecast request did not complete.')
        setLastRequestId(null)
      }
      setRefreshNonce((n) => n + 1)
      await refetchDb()
      await refetchRequests()
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status
      setDbDisabled(status === 503)
      setDbError(
        status === 503
          ? 'DB-native generation is not enabled in this environment.'
          : 'The forecast could not be started.',
      )
    } finally {
      setGenDb(false)
    }
  }

  // Legacy package-backed DB-config (live-config snapshot) path — advanced disclosure only.
  async function onGenerateDbConfig() {
    if (!projectKey) return
    const orderErr = dateOrderError(forecastStartDate, forecastCutoffDate)
    if (orderErr) {
      setDateError(orderErr)
      return
    }
    setDateError(null)
    setGenDbCfg(true)
    setDbCfgError(null)
    setDbCfgDisabled(false)
    setLastRequestId(null)
    setGenCompleted(false)
    try {
      const resp = await api.startForecastDbConfigRun({
        project_key: projectKey,
        generator_kind: genKind,
        forecast_start_date: forecastStartDate || null,
        forecast_cutoff_date: forecastCutoffDate || null,
        forecast_cutoff_date_basis: forecastCutoffDate ? cutoffBasis : null,
      })
      const requestStatus = (resp as { request_status?: string })?.request_status
      const failureCode = (resp as { failure_code?: string | null })?.failure_code ?? null
      const failureMessage = (resp as { failure_message?: string | null })?.failure_message ?? null
      const requestId = (resp as { request_id?: string })?.request_id ?? null

      if (requestStatus === 'failed' || requestStatus === 'rejected') {
        setDbCfgError(
          failureMessage ||
            failureCodeCopy(failureCode) ||
            'Config-backed generation did not complete.',
        )
        setLastRequestId(null)
      } else {
        setLastRequestId(requestId)
      }
      setRefreshNonce((n) => n + 1)
      await refetchDb()
      await refetchRequests()
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status
      setDbCfgDisabled(status === 503)
      setDbCfgError(
        status === 503
          ? 'Config-backed generation is not enabled in this environment.'
          : 'Config-backed generation could not be started.',
      )
    } finally {
      setGenDbCfg(false)
    }
  }

  const fileRuns = Array.isArray(runsResp?.runs) ? runsResp.runs : []
  const dbRuns = Array.isArray(dbRunsResp?.runs) ? dbRunsResp.runs : []
  const allRuns = [
    ...fileRuns.map((r: Record<string, unknown>) => ({ ...r, _source: 'file' as const })),
    ...dbRuns.map((r: Record<string, unknown>) => ({ ...r, _source: 'live_config' as const })),
  ].sort((a, b) =>
    String(b.generated_display || '').localeCompare(String(a.generated_display || '')),
  )
  const detail = detailResp || null

  // Disable the DB-config control only when readiness is KNOWN not-ready (fail-open during the brief
  // load; the backend POST is still fail-closed). Reasons drive the actionable before-click message.
  const dbNotReady = readiness?.ready === false
  const disabledReasons = readiness?.disabled_reasons ?? []
  const readinessActions = readiness?.actions ?? []
  const readinessWarnings = readiness?.warnings ?? []

  // UI-A: display-ready context-header props. The header is presentational, so the page resolves
  // reason codes here (via PROJECT_READINESS_REASON_TEXT, the single source of that copy).
  const headerReadinessReasons =
    selectedProjectObj && selectedProjectObj.readiness_status !== 'ready'
      ? selectedProjectObj.readiness_reasons.map(
          (code) =>
            PROJECT_READINESS_REASON_TEXT[code] ?? 'This project is not ready for generation.',
        )
      : []
  const headerSelectedRun = detail
    ? {
        label: (detail.display_label as string) || 'Run detail',
        status: (detail.status as string) || 'unknown',
      }
    : null
  const nextAction = deriveNextAction({ projectKey, selectedProjectObj, detail })

  // UI-B: map readiness codes → path-free copy for the generation panel (maps stay the single source).
  const dbBlockerReasons = disabledReasons.map(
    (reason) => READINESS_REASON_TEXT[reason] ?? 'Generation from live configuration is not available yet.',
  )
  const dbBlockerActions = readinessActions.map((action) => ({
    label: action.label,
    to: READINESS_ACTION_ROUTE[action.code] ?? null,
  }))
  const dbWarningLines = readinessWarnings.map(
    (w) => READINESS_WARNING_TEXT[w] ?? 'Generation may not produce output in the current configuration.',
  )
  const runFailed = detail
    ? detail.status === 'failed' || detail.status === 'rejected'
    : false

  return (
    <ForecastShell>
      <ForecastBackLink />
      <ForecastSubnav />

      <ForecastContextHeader
        projectName={selectedProjectObj?.display_name ?? null}
        projectKey={projectKey ?? null}
        readinessStatus={
          selectedProjectObj ? projectReadinessPill(selectedProjectObj.readiness_status) : null
        }
        readinessReasons={headerReadinessReasons}
        latestForecastDisplay={selectedProjectObj?.latest_forecast_display ?? null}
        selectedRun={headerSelectedRun}
        outputContext="No output selected"
        nextAction={nextAction}
      />

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Project"
          subtitle="Select a project to generate a forecast. Availability reflects the latest local database evidence."
          actions={
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
          }
        />
        {projects.length === 0 && (
          <p className="text-sm text-[var(--hb-muted)] mt-2">No projects are available yet.</p>
        )}
        <div className="flex flex-wrap items-center gap-4 mt-3">
          <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
            Forecast start date
            <input
              type="date"
              aria-label="Forecast start date"
              value={forecastStartDate}
              onChange={(e) => onStartChange(e.target.value)}
              className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
            />
          </label>
          <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
            Forecast cut-off date
            <input
              type="date"
              aria-label="Forecast cut-off date"
              value={forecastCutoffDate}
              onChange={(e) => onCutoffChange(e.target.value)}
              className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
            />
          </label>
        </div>
        <div className="mt-3">
          <p className="text-sm font-medium">Forecast month windows</p>
          <p className="text-xs text-[var(--hb-muted)] mt-0.5">
            Defaults populate from the project's actuals and schedule after selection — review and
            adjust, then generate.
          </p>
          <div className="flex flex-wrap items-center gap-4 mt-2">
            <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
              Actuals start month
              <input
                type="month"
                aria-label="Actuals start month"
                value={actualsStartMonth}
                onChange={(e) => setActualsStartOverride(e.target.value)}
                className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
              />
            </label>
            <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
              Actuals through month
              <input
                type="month"
                aria-label="Actuals through month"
                value={actualsThroughMonth}
                onChange={(e) => setActualsThroughOverride(e.target.value)}
                className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
              />
            </label>
            <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
              Forecast start month
              <input
                type="month"
                aria-label="Forecast start month"
                value={forecastStartMonth}
                onChange={(e) => setForecastStartMonthOverride(e.target.value)}
                className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
              />
            </label>
            <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
              Forecast end month
              <input
                type="month"
                aria-label="Forecast end month"
                value={forecastEndMonth}
                onChange={(e) => setForecastEndMonthOverride(e.target.value)}
                className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
              />
            </label>
          </div>
          {projectKey && monthWindowError && (
            <p className="text-xs text-amber-300 mt-1" role="status">
              {monthWindowError}
            </p>
          )}
        </div>
        {projectKey && (
          <p className="text-xs text-[var(--hb-muted)] mt-1">
            Cut-off basis:{' '}
            {cutoffBasis
              ? (CUTOFF_BASIS_LABEL[cutoffBasis] ?? cutoffBasis)
              : 'No schedule-derived default available'}
          </p>
        )}
        {projectKey && (dateDefaults?.warnings.length ?? 0) > 0 && (
          <div className="text-xs text-amber-300 mt-1" role="status">
            {dateDefaults!.warnings.map((w) => (
              <p key={w}>{DATE_DEFAULT_WARNING_TEXT[w] ?? 'Schedule date information is incomplete.'}</p>
            ))}
          </div>
        )}
        {dateError && (
          <p className="text-sm text-rose-300 mt-2" role="status">
            {dateError}
          </p>
        )}
        {lastRequestId && (
          <p className="text-sm text-emerald-300 mt-2" role="status">
            {genCompleted
              ? `Forecast generated and saved (tracking id ${lastRequestId}).`
              : `Generation request submitted (tracking id ${lastRequestId}).`}
          </p>
        )}
      </section>

      <ForecastGeneratePanel
        projectKey={projectKey ?? null}
        selectedBlocked={selectedBlocked}
        dateError={dateError}
        generatorKinds={GENERATOR_KINDS}
        primary={{
          onGenerate: onGenerateDbNative,
          generating: genDb,
          error: dbError,
          errorActionTo: dbDisabled ? '/forecasting/runtime' : null,
          disabled: Boolean(monthWindowError),
        }}
        legacyDbConfig={{
          genKind,
          onKindChange: setGenKind,
          onGenerate: onGenerateDbConfig,
          generating: genDbCfg,
          notReady: dbNotReady,
          blockerReasons: dbBlockerReasons,
          blockerActions: dbBlockerActions,
          warnings: dbWarningLines,
          error: dbCfgError,
          errorActionTo: dbCfgDisabled ? '/forecasting/runtime' : null,
        }}
        legacyFile={{
          onGenerate,
          generating,
          error: genError,
          errorActionTo: genUnconfigured ? '/forecasting/runtime' : null,
        }}
      />

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Generation history</h2>
        {isLoading ? (
          <div className="text-sm text-[var(--hb-muted)]">Loading history…</div>
        ) : error ? (
          <EmptyState title="History unavailable" hint="We could not load generation history right now." />
        ) : allRuns.length === 0 ? (
          <EmptyState
            title="No forecast runs yet"
            hint="Use the Generate panel above to create your first forecast."
          />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Run</ForecastTh>
                <ForecastTh>Source</ForecastTh>
                <ForecastTh>Status</ForecastTh>
                <ForecastTh>Generated</ForecastTh>
                <ForecastTh />
              </>
            }
          >
            {allRuns.map((r) => (
              <tr key={`${r._source}:${r.run_id as string}`}>
                <ForecastTd>{r.display_label as string}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {r._source === 'live_config' ? 'Live configuration' : 'File configuration'}
                </ForecastTd>
                <ForecastTd>
                  <ForecastStatusPill status={runStatusPill(r.status as string)} />
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {(r.generated_display as string) || '—'}
                </ForecastTd>
                <ForecastTd>
                  <ForecastActionButton
                    variant="ghost"
                    onClick={() => setSelected({ id: r.run_id as string, source: r._source })}
                  >
                    Open
                  </ForecastActionButton>
                </ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </section>

      {detail && runFailed && (
        // Failed runs are kept visually separate from persisted/latest output: no packages, no
        // "review output" affordance — only the failure and the explicit no-output statement.
        <section className="forecast-panel">
          <h2 className="forecast-section-label">Run did not complete</h2>
          <p className="text-sm">
            {(detail.display_label as string) || 'Selected run'} · Status:{' '}
            <span className="font-medium">{detail.status as string}</span>
          </p>
          <ForecastErrorCallout
            tone="error"
            lines={[
              ...(detail.message ? [detail.message as string] : []),
              ...(() => {
                // Curated, path-free reason from the coded failure (deduped against message).
                const coded = failureCodeCopy(detail.failure_code as string | null | undefined)
                return coded && coded !== detail.message ? [coded] : []
              })(),
              'No forecast output was produced for this run.',
            ]}
          />
          {detail.no_live_writes && (
            <p className="text-xs text-emerald-300 mt-2">
              No changes were made to live project data or external systems.
            </p>
          )}
        </section>
      )}

      {detail && !runFailed && (
        <section className="forecast-panel">
          <h2 className="forecast-section-label">{(detail.display_label as string) || 'Run detail'}</h2>
          <p className="text-sm">
            Status: <span className="font-medium">{detail.status as string}</span>
            {typeof detail.checks_total === 'number' && detail.checks_total > 0
              ? ` · ${detail.checks_passed}/${detail.checks_total} checks passed`
              : ''}
          </p>
          {detail.config_snapshot_consumed && (
            <p className="text-sm text-[var(--hb-muted)]">
              Configuration:{' '}
              <span className="font-medium">
                {(detail.snapshot_display as string) || 'live configuration'}
              </span>
              {typeof detail.snapshot_item_count === 'number' && detail.snapshot_item_count > 0
                ? ` (${detail.snapshot_item_count} settings)`
                : ''}
              {detail.fidelity_gate_passed ? ' · Verified' : ''}
            </p>
          )}
          {Array.isArray(detail.packages) && detail.packages.length > 0 && (
            <p className="text-sm text-[var(--hb-muted)]">
              Packages: {(detail.packages as string[]).join(' · ')}
            </p>
          )}
          {detail.no_live_writes && (
            <p className="text-xs text-emerald-300 mt-1">
              No changes were made to live project data or external systems.
            </p>
          )}
          {detail.message && (
            <p className="text-sm text-rose-300 mt-1">{detail.message as string}</p>
          )}
          <div className="mt-2">
            <ForecastQuickLink to="/forecasting">Review packages on overview</ForecastQuickLink>
          </div>
        </section>
      )}

      {projectKey && recentRequests.length > 0 && (
        <section className="forecast-panel">
          <h2 className="forecast-section-label">Recent generation requests</h2>
          <ForecastTable
            headers={
              <>
                <ForecastTh>Mode</ForecastTh>
                <ForecastTh>Type</ForecastTh>
                <ForecastTh>Window</ForecastTh>
                <ForecastTh>Status</ForecastTh>
                <ForecastTh>Requested</ForecastTh>
              </>
            }
          >
            {recentRequests.map((r) => (
              <tr key={r.request_id}>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {r.generation_mode === 'db_config' ? 'Live configuration' : 'File configuration'}
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{r.generator_kind || '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {r.forecast_start_date || '—'} → {r.forecast_cutoff_date || '—'}
                </ForecastTd>
                <ForecastTd>
                  <ForecastStatusPill status={runStatusPill(r.request_status)} />
                  {(r.request_status === 'failed' || r.request_status === 'rejected') &&
                    (r.failure_message || failureCodeCopy(r.failure_code)) && (
                      <p className="mt-1 text-xs text-[var(--hb-muted)]">
                        {r.failure_message || failureCodeCopy(r.failure_code)}
                      </p>
                    )}
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{r.created_utc || '—'}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        </section>
      )}

      {projectKey ? (
        <>
          <ForecastHealthSummary
            key={`fh-${projectKey}-${refreshNonce}`}
            project={projectKey}
            readinessStatus={selectedProjectObj?.readiness_status ?? null}
            runFailed={runFailed}
            activeOutputId={activeOutputId}
          />
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
          <ForecastDecisionSupportPanel
            key={`ds-${projectKey}-${refreshNonce}`}
            project={projectKey}
            activeOutputId={activeOutputId}
          />
          <ForecastNarrativesPanel
            key={`nr-${projectKey}-${refreshNonce}`}
            project={projectKey}
            activeOutputId={activeOutputId}
          />
          <ForecastOperatorAssumptionsPanel key={`oa-${projectKey}-${refreshNonce}`} project={projectKey} />
        </>
      ) : (
        <section className="forecast-panel">
          <h2 className="forecast-section-label">Forecast results</h2>
          <p className="text-sm text-[var(--hb-muted)]">
            Select a project to view its forecast results.
          </p>
        </section>
      )}
    </ForecastShell>
  )
}