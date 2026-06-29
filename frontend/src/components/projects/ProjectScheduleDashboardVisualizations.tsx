/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  Bar,
  BarChart,
  CartesianGrid,
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
}

export function ProjectScheduleDashboardVisualizations({
  schedule,
}: ProjectScheduleDashboardVisualizationsProps) {
  if (!hasScheduleVisualizations(schedule)) return null

  const trend = buildScheduleTrendSeries(schedule.trend_series || {})
  const drivers = buildDriverImpactRows(schedule.change_driver_analysis || {})
  const milestones = buildMilestoneSlipRows(schedule.milestones || {})
  const floatBuckets = buildFloatPressureBuckets(schedule.remaining_health || {})

  return (
    <section className="space-y-4">
      <h4 className="text-sm font-semibold">Trends &amp; Pressure</h4>
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