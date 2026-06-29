/* eslint-disable @typescript-eslint/no-explicit-any */

export type ScheduleTrendPoint = {
  label: string
  forecastFinish: string | null
  remainingCount: number
  negativeFloatCount: number
  criticalCount: number
  milestoneMovedLater: number
}

export type ScheduleDriverImpactRow = {
  label: string
  driverScore: number
  downstreamLater: number
}

export function buildScheduleTrendSeries(trendSeries: Record<string, any>): ScheduleTrendPoint[] {
  const metrics = Array.isArray(trendSeries.metrics) ? trendSeries.metrics : []
  return metrics.map((point: any) => ({
    label: String(point.friendly_label || point.data_date || 'Update'),
    forecastFinish: point.forecast_finish ? String(point.forecast_finish) : null,
    remainingCount: Number(point.remaining_activity_count || 0),
    negativeFloatCount: Number(point.negative_float_remaining_count || 0),
    criticalCount: Number(point.critical_remaining_count || 0),
    milestoneMovedLater: Number(point.milestone_moved_later_count || 0),
  }))
}

export function buildDriverImpactRows(driverHub: Record<string, any>): ScheduleDriverImpactRow[] {
  const prior = driverHub.prior_update || driverHub
  const drivers = Array.isArray(prior.top_drivers) ? prior.top_drivers : []
  return drivers.slice(0, 8).map((driver: any) => ({
    label: String(driver.activity_name || driver.activity_id || 'Driver'),
    driverScore: Number(driver.driver_score || 0),
    downstreamLater: Number(driver.downstream_moved_later_count || 0),
  }))
}

export function buildMilestoneSlipRows(milestones: Record<string, any>) {
  const items = Array.isArray(milestones.items) ? milestones.items : []
  return items
    .filter((item: any) => Number(item.movement_days || 0) > 0)
    .slice(0, 12)
    .map((item: any) => ({
      label: String(item.activity_name || item.activity_id || 'Milestone'),
      movementDays: Number(item.movement_days || 0),
      forecastDate: item.forecast_date ? String(item.forecast_date) : null,
    }))
}

export function buildFloatPressureBuckets(remainingHealth: Record<string, any>) {
  const floatPressure = remainingHealth.float_pressure || {}
  const preview = Array.isArray(floatPressure.preview) ? floatPressure.preview : []
  const buckets = { negative: 0, zero: 0, positive: 0 }
  for (const row of preview) {
    const raw = row.total_float ?? row.derived_total_float_days
    const value = raw == null || raw === '' ? null : Number(raw)
    if (value == null || Number.isNaN(value)) continue
    if (value < 0) buckets.negative += 1
    else if (value === 0) buckets.zero += 1
    else buckets.positive += 1
  }
  if (!preview.length) {
    return [
      { label: 'Negative', count: Number(floatPressure.negative_float_count || 0) },
      { label: 'Zero', count: Number(floatPressure.zero_float_count || 0) },
      { label: 'Near-critical', count: Number(floatPressure.near_critical_count || 0) },
    ]
  }
  return [
    { label: 'Negative', count: buckets.negative },
    { label: 'Zero', count: buckets.zero },
    { label: 'Positive', count: buckets.positive },
  ]
}

export function hasScheduleVisualizations(schedule: Record<string, any>) {
  const trend = buildScheduleTrendSeries(schedule.trend_series || {})
  const drivers = buildDriverImpactRows(schedule.change_driver_analysis || {})
  const milestones = buildMilestoneSlipRows(schedule.milestones || {})
  return trend.length > 1 || drivers.length > 0 || milestones.length > 0
}