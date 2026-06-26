import type { ForecastDbForecastSummary, ForecastDbMonthlyTable } from '../../lib/api'

/**
 * Read-only dashboard data shaping for the selected forecast output. These helpers ONLY reshape
 * values already returned by the forecast detail/monthly read APIs into chart points — no new
 * forecast or accounting semantics. All money arrives as decimal strings (or null); parsing is
 * finite-guarded so an invalid/`"NaN"`/null value is dropped, never rendered as `NaN` or coerced
 * into a misleading 0.
 */

/** Finite-guarded decimal-string → number. Returns null for null/undefined/''/'NaN'/garbage. */
export function parseMoney(value: string | null | undefined): number | null {
  if (value == null || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export type ChartPoint = { name: string; value: number }

export type MonthlyPoint = {
  month: string
  label: string
  valueType: 'actual' | 'forecast'
  amount: number
}

export type BudgetVsEac = { points: ChartPoint[]; hasData: boolean }
export type CostPosition = { points: ChartPoint[]; hasData: boolean }
export type MonthlySeries = { series: MonthlyPoint[]; hasData: boolean }

/** Current Budget vs Estimated at Completion — a comparison needs both values present. */
export function buildBudgetVsEac(summary: ForecastDbForecastSummary | null | undefined): BudgetVsEac {
  const currentBudget = parseMoney(summary?.current_budget)
  const eac = parseMoney(summary?.estimated_at_completion)
  if (currentBudget == null || eac == null) {
    return { points: [], hasData: false }
  }
  return {
    points: [
      { name: 'Current Budget', value: currentBudget },
      { name: 'EAC', value: eac },
    ],
    hasData: true,
  }
}

/** Cost to Date vs Cost to Complete — a composition needs both values present. */
export function buildCostPosition(summary: ForecastDbForecastSummary | null | undefined): CostPosition {
  const toDate = parseMoney(summary?.total_cost_to_date)
  const toComplete = parseMoney(summary?.cost_to_complete)
  if (toDate == null || toComplete == null) {
    return { points: [], hasData: false }
  }
  return {
    points: [
      { name: 'Cost to Date', value: toDate },
      { name: 'To Complete', value: toComplete },
    ],
    hasData: true,
  }
}

/**
 * Per-month series from the total row. Prefers `total_row.month_values` (no synthetic total is
 * built when the total row is missing). Months whose value is non-finite are OMITTED — never
 * coerced to 0 — while a legitimate certified `"0.00"` (finite) is kept.
 */
export function buildMonthlySeries(table: ForecastDbMonthlyTable | null | undefined): MonthlySeries {
  if (!table || table.status !== 'ready' || !table.total_row) {
    return { series: [], hasData: false }
  }
  const monthValues = table.total_row.month_values ?? {}
  const series: MonthlyPoint[] = []
  for (const month of table.months ?? []) {
    const amount = parseMoney(monthValues[month.month])
    if (amount == null) continue
    series.push({
      month: month.month,
      label: month.label,
      valueType: month.value_type,
      amount,
    })
  }
  return { series, hasData: series.length > 0 }
}

export function hasAnyVisualization(
  budget: BudgetVsEac,
  cost: CostPosition,
  monthly: MonthlySeries,
): boolean {
  return budget.hasData || cost.hasData || monthly.hasData
}
