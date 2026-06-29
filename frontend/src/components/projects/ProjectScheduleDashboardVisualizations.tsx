/* eslint-disable @typescript-eslint/no-explicit-any */
import type { ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { SectionCard } from '../common/SectionCard'
import {
  buildDriverImpactRows,
  buildFloatPressureBuckets,
  buildMilestoneSlipRows,
  buildScheduleTrendSeries,
  hasScheduleVisualizations,
} from './projectScheduleDashboardData'

const CHART_HEIGHT = 200

type ProjectScheduleDashboardVisualizationsProps = {
  schedule: Record<string, any>
  trendPayload?: Record<string, any>
  trendLoading?: boolean
  trendError?: unknown
}

export function ProjectScheduleDashboardVisualizations({
  schedule,
  trendPayload,
  trendLoading = false,
  trendError,
}: ProjectScheduleDashboardVisualizationsProps) {
  const trend = buildScheduleTrendSeries(schedule.trend_series || {})
  const drivers = buildDriverImpactRows(schedule.change_driver_analysis || {})
  const milestones = buildMilestoneSlipRows(schedule.milestones || {})
  const floatBuckets = buildFloatPressureBuckets(schedule.remaining_health || {})
  const trendsByKey = trendPayloadByKey(trendPayload)
  const trendErrors = Array.isArray(trendPayload?.errors) ? trendPayload.errors : []
  const hasLegacyVisuals = hasScheduleVisualizations(schedule)

  return (
    <section className="space-y-4">
      <h4 className="text-sm font-semibold">Schedule Controls</h4>
      <ControlsOverview schedule={schedule} />

      <div className="space-y-4">
        <h5 className="text-sm font-semibold">Trend Analytics</h5>
        {trendLoading && (
          <div role="status" className="rounded border border-[var(--hb-border)] p-3 text-sm text-[var(--hb-muted)]">
            Loading schedule controls trends...
          </div>
        )}
        {Boolean(trendError) && (
          <div role="alert" className="rounded border border-amber-800/70 p-3 text-sm">
            Schedule controls trends are unavailable right now.
          </div>
        )}
        <div className="grid gap-4 xl:grid-cols-2">
          <MetricPanel metric={trendsByKey.monthly_activity_start_finish_distribution} title="Monthly Activity Start/Finish Distribution">
            {(metric) => <MonthlyDistributionChart metric={metric} />}
          </MetricPanel>
          <MetricPanel metric={trendsByKey.planned_vs_actual_percent_complete} title="Planned vs Actual Percent Complete">
            {(metric) => <ProgressChart metric={metric} />}
          </MetricPanel>
          <MetricPanel metric={trendsByKey.schedule_performance_ratio} title="Schedule Performance Ratio">
            {(metric) => <PerformanceRatioChart metric={metric} />}
          </MetricPanel>
          <MetricPanel metric={trendsByKey.schedule_delay_over_time} title="Schedule Delay Over Time">
            {(metric) => <DelayChart metric={metric} />}
          </MetricPanel>
          <MetricPanel metric={trendsByKey.schedule_changes_over_time} title="Schedule Changes Over Time">
            {(metric) => <ChangesChart metric={metric} />}
          </MetricPanel>
        </div>
      </div>

      <div className="space-y-4">
        <h5 className="text-sm font-semibold">Schedule Health / Feasibility</h5>
        <div className="grid gap-4 xl:grid-cols-2">
          <MetricPanel metric={trendsByKey.project_schedule_health_index} title="Project Schedule Health Index">
            {(metric) => <HealthIndexChart metric={metric} />}
          </MetricPanel>
          <MetricPanel metric={trendsByKey.schedule_feasibility_score} title="Schedule Feasibility Score">
            {(metric) => <MetricPointList metric={metric} valueKey="feasibility_score" />}
          </MetricPanel>
          <MetricPanel metric={trendsByKey.required_recovery_days} title="Required Recovery Days">
            {(metric) => <MetricPointList metric={metric} valueKey="required_recovery_days" />}
          </MetricPanel>
          <MetricPanel metric={trendsByKey.critical_path_length_index} title="Critical Path Length Index">
            {(metric) => <MetricPointList metric={metric} valueKey="critical_path_length_index" />}
          </MetricPanel>
          <MetricPanel metric={trendsByKey.total_float_consumption_index} title="Total Float Consumption Index">
            {(metric) => <FloatConsumptionChart metric={metric} />}
          </MetricPanel>
          {trendsByKey.schedule_compression_ratio && (
            <MetricPanel metric={trendsByKey.schedule_compression_ratio} title="Schedule Compression Ratio">
              {(metric) => <MetricPointList metric={metric} valueKey="compression_ratio" />}
            </MetricPanel>
          )}
        </div>
      </div>

      <div className="space-y-4">
        <h5 className="text-sm font-semibold">Execution Reliability / Review Cues</h5>
        <div className="grid gap-4 xl:grid-cols-2">
          {trendsByKey.window_start_accuracy && (
            <MetricPanel metric={trendsByKey.window_start_accuracy} title="Window Start Accuracy">
              {(metric) => <WindowAccuracySummary metric={metric} startField />}
            </MetricPanel>
          )}
          {trendsByKey.window_finish_accuracy && (
            <MetricPanel metric={trendsByKey.window_finish_accuracy} title="Window Finish Accuracy">
              {(metric) => <WindowAccuracySummary metric={metric} />}
            </MetricPanel>
          )}
          {trendsByKey.should_have_finished_status && (
            <MetricPanel metric={trendsByKey.should_have_finished_status} title="Should Have Finished Status">
              {(metric) => <StatusBreakdownChart metric={metric} />}
            </MetricPanel>
          )}
          {trendsByKey.delay_analysis && (
            <MetricPanel metric={trendsByKey.delay_analysis} title="Delay Analysis">
              {(metric) => <MetricPointList metric={metric} valueKey="net_movement" />}
            </MetricPanel>
          )}
          {trendsByKey.critical_issues_category_model && (
            <MetricPanel metric={trendsByKey.critical_issues_category_model} title="Critical Issues Category Model">
              {(metric) => <CategoryBreakdownChart metric={metric} />}
            </MetricPanel>
          )}
        </div>
      </div>

      <BlockedMetricCards errors={trendErrors} hiddenKeys={Object.keys(trendsByKey)} />

      {hasLegacyVisuals && (
        <h5 className="text-sm font-semibold">Review Cues</h5>
      )}
      {trend.length > 1 && (
        <SectionCard title="Schedule trend metrics">
          <figure>
            <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="remainingCount" name="Remaining" stroke="#7dd3fc" strokeWidth={2} />
                <Line type="monotone" dataKey="negativeFloatCount" name="Negative float" stroke="#f87171" strokeWidth={2} />
                <Line type="monotone" dataKey="criticalCount" name="Critical" stroke="#fbbf24" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <figcaption className="mt-2 text-xs text-[var(--hb-muted)]">
              Remaining work, negative float, and critical counts across recent comparable updates.
            </figcaption>
          </figure>
        </SectionCard>
      )}

      {drivers.length > 0 && (
        <SectionCard title="Driver impact (sequence cues)">
          <figure>
            <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
              <BarChart data={drivers} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="downstreamLater" name="Downstream moved later" fill="#60a5fa" />
              </BarChart>
            </ResponsiveContainer>
            <figcaption className="mt-2 text-xs text-[var(--hb-muted)]">
              Candidate drivers ranked by downstream movement — sequence cues only, not causation.
            </figcaption>
          </figure>
        </SectionCard>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {milestones.length > 0 && (
          <SectionCard title="Milestone slip timeline">
            <figure>
              <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                <BarChart data={milestones}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="movementDays" name="Movement (days)" fill="#fb923c" />
                </BarChart>
              </ResponsiveContainer>
              <figcaption className="mt-2 text-xs text-[var(--hb-muted)]">
                Remaining milestones that moved later versus the prior update.
              </figcaption>
            </figure>
          </SectionCard>
        )}

        {floatBuckets.some((bucket) => bucket.count > 0) && (
          <SectionCard title="Float-pressure distribution">
            <figure>
              <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                <BarChart data={floatBuckets}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" name="Activities" fill="#a78bfa" />
                </BarChart>
              </ResponsiveContainer>
              <figcaption className="mt-2 text-xs text-[var(--hb-muted)]">
                Float-pressure buckets from remaining-work preview activities.
              </figcaption>
            </figure>
          </SectionCard>
        )}
      </div>
    </section>
  )
}

function ControlsOverview({ schedule }: { schedule: Record<string, any> }) {
  const command = schedule.command_summary || {}
  const direct = schedule.change_impact?.direct_remaining_changes?.summary || {}
  return (
    <SectionCard title="Controls Overview">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SmallMetric label="Forecast completion" value={command.forecast_finish} />
        <SmallMetric label="Critical remaining" value={command.critical_remaining_count} />
        <SmallMetric label="Source/export negative float" value={command.negative_float_remaining_count} />
        <SmallMetric label="Remaining work" value={command.remaining_activity_count} />
        <SmallMetric label="Remaining later / earlier" value={`${numberText(direct.finish_moved_later_count)} / ${numberText(direct.finish_moved_earlier_count)}`} />
        <SmallMetric label="Finish changed" value={direct.finish_changed_count ?? direct.changed_count} />
        <SmallMetric label="Worsened / improved float" value={`${numberText(direct.worsened_float_count)} / ${numberText(direct.improved_float_count)}`} />
        <SmallMetric label="Moved milestones" value={direct.moved_remaining_milestones_count} />
      </div>
    </SectionCard>
  )
}

function SmallMetric({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded border border-[var(--hb-border)] bg-black/10 p-3">
      <div className="text-xs text-[var(--hb-muted)]">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value == null || value === '' ? '—' : String(value)}</div>
    </div>
  )
}

function MetricPanel({
  metric,
  title,
  children,
}: {
  metric?: Record<string, any>
  title: string
  children: (metric: Record<string, any>) => ReactNode
}) {
  const points = Array.isArray(metric?.points) ? metric.points : []
  const notes = Array.isArray(metric?.data_quality_notes) ? metric.data_quality_notes : []
  const partialDimension = metric?.partial_dimension_support === true
  const caveats = Array.isArray(metric?.caveats) ? metric.caveats : []
  const basis = Array.isArray(metric?.basis_labels) ? metric.basis_labels : []
  const comparison = Array.isArray(metric?.comparison_basis) ? metric.comparison_basis : []
  const selectedBaseline = metric?.selected_baseline || {}
  const unavailable = metric && metric.available === false
  return (
    <SectionCard title={title}>
      {!metric ? (
        <div className="rounded border border-[var(--hb-border)] p-3 text-sm text-[var(--hb-muted)]">
          Not yet available from schedule controls trend API.
        </div>
      ) : unavailable ? (
        <div className="rounded border border-amber-800/70 p-3 text-sm">
          <div className="font-medium">Not yet available</div>
          <div className="mt-1 text-[var(--hb-muted)]">{readable(metric.reason || metric.readiness_status || 'blocked')}</div>
        </div>
      ) : points.length === 0 ? (
        <div className="rounded border border-[var(--hb-border)] p-3 text-sm text-[var(--hb-muted)]">
          {notes[0] || 'No trend points are available for the selected update window.'}
        </div>
      ) : (
        children(metric)
      )}
      <MetricProvenance
        basis={basis}
        comparison={comparison}
        weighting={metric?.weighting_basis}
        caveats={caveats}
        notes={partialDimension ? ['Partial UDF dimension coverage reported by backend.', ...notes] : notes}
      />
      {selectedBaseline?.selected_baseline_label && (
        <div className="mt-2 text-xs text-[var(--hb-muted)]">
          Selected baseline: {selectedBaseline.selected_baseline_label}
          {selectedBaseline.selected_baseline_data_date ? ` (${selectedBaseline.selected_baseline_data_date})` : ''}
          {selectedBaseline.recompute_required ? ' · Recompute/readiness required' : ''}
        </div>
      )}
    </SectionCard>
  )
}

function MetricProvenance({
  basis,
  comparison,
  weighting,
  caveats,
  notes,
}: {
  basis: string[]
  comparison: string[]
  weighting?: string
  caveats: string[]
  notes: string[]
}) {
  return (
    <div className="mt-3 space-y-2 text-xs text-[var(--hb-muted)]">
      <div className="flex flex-wrap gap-2">
        {basis.map((item) => <span key={item} className="badge">{readable(item)}</span>)}
        {comparison.map((item) => <span key={item} className="badge">{readable(item)}</span>)}
        {weighting && <span className="badge">{readable(weighting)}</span>}
      </div>
      {caveats.slice(0, 2).map((item) => <p key={item}>{item}</p>)}
      {notes.slice(0, 2).map((item) => <p key={item}>{item}</p>)}
    </div>
  )
}

function MonthlyDistributionChart({ metric }: { metric: Record<string, any> }) {
  const data = (Array.isArray(metric.points) ? metric.points : []).slice(-18).map((point: any) => ({
    label: `${point.month} ${readable(point.date_family || '')}`,
    count: Number(point.activity_count || 0),
  }))
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={70} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="count" name="Activities" fill="#60a5fa" />
      </BarChart>
    </ResponsiveContainer>
  )
}

function ProgressChart({ metric }: { metric: Record<string, any> }) {
  const data = trendPoints(metric).map((point) => ({
    label: point.data_date,
    planned: percent(point.planned_percent_complete),
    actual: percent(point.actual_percent_complete),
  }))
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="planned" name="Planned %" stroke="#93c5fd" strokeWidth={2} />
        <Line type="monotone" dataKey="actual" name="Actual %" stroke="#34d399" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}

function PerformanceRatioChart({ metric }: { metric: Record<string, any> }) {
  const data = trendPoints(metric).map((point) => ({
    label: point.data_date,
    ratio: point.schedule_performance_ratio == null ? null : Number(point.schedule_performance_ratio).toFixed(2),
  }))
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Line type="monotone" dataKey="ratio" name="Schedule performance ratio" stroke="#fbbf24" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}

function DelayChart({ metric }: { metric: Record<string, any> }) {
  const data = trendPoints(metric).map((point) => ({
    label: point.period || point.data_date,
    delay: Number(point.delay_days || 0),
    gain: Number(point.gain_days || 0),
    net: Number(point.net_movement_days || 0),
  }))
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="delay" name="Delay days" fill="#f87171" />
        <Bar dataKey="gain" name="Gain days" fill="#34d399" />
        <Bar dataKey="net" name="Net movement" fill="#60a5fa" />
      </BarChart>
    </ResponsiveContainer>
  )
}

function ChangesChart({ metric }: { metric: Record<string, any> }) {
  const data = trendPoints(metric).map((point) => ({
    label: point.period || point.data_date,
    activity: Number(point.categories?.activity_changes || 0),
    logic: Number(point.categories?.logic_changes || 0),
    duration: Number(point.categories?.duration_changes || 0),
    critical: Number(point.categories?.critical_changes || 0),
    added: Number(point.categories?.added_activity_changes || 0),
    deleted: Number(point.categories?.deleted_activity_changes || 0),
  }))
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip />
        <Legend />
        <Bar dataKey="activity" name="Activity" fill="#60a5fa" />
        <Bar dataKey="logic" name="Logic" fill="#a78bfa" />
        <Bar dataKey="duration" name="Duration" fill="#fb923c" />
        <Bar dataKey="critical" name="Critical" fill="#f87171" />
        <Bar dataKey="added" name="Added" fill="#34d399" />
        <Bar dataKey="deleted" name="Deleted" fill="#94a3b8" />
      </BarChart>
    </ResponsiveContainer>
  )
}

function HealthIndexChart({ metric }: { metric: Record<string, any> }) {
  const data = trendPoints(metric).map((point) => ({
    label: point.data_date,
    score: Number(point.health_index || 0),
  }))
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
        <Tooltip />
        <Line type="monotone" dataKey="score" name="Health index" stroke="#34d399" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}

function MetricPointList({ metric, valueKey }: { metric: Record<string, any>; valueKey: string }) {
  return (
    <div className="space-y-2 text-sm">
      {trendPoints(metric).slice(-4).map((point) => (
        <div key={`${point.data_date || point.period}-${valueKey}`} className="flex justify-between gap-3 rounded border border-[var(--hb-border)] p-2">
          <span>{point.data_date || point.period || 'Update'}</span>
          <span className="font-medium">{point[valueKey] == null ? '—' : String(point[valueKey])}</span>
        </div>
      ))}
    </div>
  )
}

function WindowAccuracySummary({
  metric,
  startField = false,
}: {
  metric: Record<string, any>
  startField?: boolean
}) {
  const point = trendPoints(metric)[0] || {}
  const rows = startField
    ? [
        ['On time', point.on_time_count],
        ['Late', point.late_count],
        ['Did not start', point.did_not_start_count],
      ]
    : [
        ['Finished on time', point.finished_on_time_count],
        ['Finished late', point.finished_late_count],
        ['Did not finish', point.did_not_finish_count],
      ]
  return (
    <div className="space-y-2 text-sm">
      {rows.map(([label, value]) => (
        <div key={String(label)} className="flex justify-between gap-3 rounded border border-[var(--hb-border)] p-2">
          <span>{label}</span>
          <span className="font-medium">{numberText(value)}</span>
        </div>
      ))}
      <div className="text-xs text-[var(--hb-muted)]">
        Accuracy ratio: {point.accuracy_ratio == null ? '—' : String(point.accuracy_ratio)}
      </div>
    </div>
  )
}

function StatusBreakdownChart({ metric }: { metric: Record<string, any> }) {
  const data = trendPoints(metric).map((point: any) => ({
    label: readable(String(point.status || 'status')),
    count: Number(point.activity_count || 0),
  }))
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="count" name="Activities" fill="#34d399" />
      </BarChart>
    </ResponsiveContainer>
  )
}

function CategoryBreakdownChart({ metric }: { metric: Record<string, any> }) {
  const data = trendPoints(metric).map((point: any) => ({
    label: readable(String(point.category || point.category_label || 'category')),
    count: Number(point.candidate_count || 0),
  }))
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-15} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="count" name="Candidates" fill="#fbbf24" />
      </BarChart>
    </ResponsiveContainer>
  )
}

function FloatConsumptionChart({ metric }: { metric: Record<string, any> }) {
  const data = trendPoints(metric).flatMap((point) =>
    (Array.isArray(point.series) ? point.series : []).map((row: any) => ({
      label: `${point.data_date} ${readable(row.float_basis || '')}`,
      total: Number(row.total_float_days || 0),
    })),
  )
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={70} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey="total" name="Total float days" fill="#38bdf8" />
      </BarChart>
    </ResponsiveContainer>
  )
}

const BLOCKED_METRICS = [
  ['delay_analysis', 'Delay Analysis', 'Requires UDF normalization'],
  ['window_start_accuracy', 'Window Start Accuracy', 'Requires UDF normalization'],
  ['window_finish_accuracy', 'Window Finish Accuracy', 'Requires UDF normalization'],
  ['should_have_finished_status', 'Should Have Finished', 'Requires UDF normalization'],
  ['critical_issues_category_model', 'Critical Issues Category Model', 'Requires UDF normalization'],
  ['schedule_compression_ratio', 'Schedule Compression Ratio', 'Requires selected baseline'],
] as const

function BlockedMetricCards({ errors, hiddenKeys = [] }: { errors: any[]; hiddenKeys?: string[] }) {
  const errorByKey = new Map(errors.map((err) => [err.metric_key, err.detail]))
  const hidden = new Set(hiddenKeys)
  return (
    <div className="space-y-4">
      <h5 className="text-sm font-semibold">Blocked / Not Yet Available Metrics</h5>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {BLOCKED_METRICS.filter(([key]) => !hidden.has(key)).map(([key, label, reason]) => (
          <div key={key} className="rounded border border-[var(--hb-border)] p-3">
            <div className="text-sm font-medium">{label}</div>
            <div className="mt-1 text-xs text-[var(--hb-muted)]">
              Not yet available: {readable(String(errorByKey.get(key) || reason))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function trendPayloadByKey(payload?: Record<string, any>) {
  const out: Record<string, any> = {}
  for (const metric of Array.isArray(payload?.metrics) ? payload.metrics : []) {
    if (metric?.metric_key) out[metric.metric_key] = metric
  }
  return out
}

function trendPoints(metric: Record<string, any>) {
  return Array.isArray(metric.points) ? metric.points : []
}

function readable(value: string) {
  if (value === 'source_export') return 'source/export'
  if (value === 'computed_cpm') return 'computed CPM'
  return value.replaceAll('_', ' ')
}

function percent(value: any) {
  const num = Number(value)
  return Number.isFinite(num) ? Math.round(num * 1000) / 10 : null
}

function numberText(value: any) {
  return value == null || value === '' ? '0' : String(value)
}
