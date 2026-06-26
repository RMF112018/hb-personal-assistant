import type { Table } from '@tanstack/react-table'

import type {
  ForecastDbMonthlyTable,
  ForecastDbMonthlyTableMonth,
  ForecastDbMonthlyTableRow,
} from '../../lib/api'
import { formatMonthLabel, sumMoney } from '../../lib/format'

/**
 * Pure shaping for a Monthly Forecast export. This module never touches the DOM, Blob, or any writer
 * dependency — it only turns the current visible table view into a serializable payload and a CSV string.
 * Side-effectful download/writers live in ./forecastMonthlyExportWriters.
 *
 * Money values stay as backend decimal strings (e.g. '150000.00') all the way through the payload and
 * CSV; numeric conversion happens only at the XLSX/PDF writer boundary. The only computed values are the
 * visible group subtotals, via the same computeSubtotal + sumMoney (BigInt-cents) the table renders with,
 * so an export matches what is on screen exactly. Backend row values and the project total stay
 * authoritative.
 */

// --- Group subtotal (presentation aggregation only; relocated here as the single source the table and
// the export both use). Exact BigInt-cents sums via sumMoney; never a replacement for certified values.
export type SubtotalValues = {
  projected_budget: string
  month_values: Record<string, string>
  completed_to_date: string
  forecast_to_complete: string
  estimated_at_completion: string
  variance_to_budget: string
}

export function computeSubtotal(
  leaves: ForecastDbMonthlyTableRow[],
  months: ForecastDbMonthlyTableMonth[],
): SubtotalValues {
  const month_values: Record<string, string> = {}
  for (const m of months) {
    month_values[m.month] = sumMoney(leaves.map((r) => r.month_values[m.month]))
  }
  return {
    projected_budget: sumMoney(leaves.map((r) => r.projected_budget)),
    month_values,
    completed_to_date: sumMoney(leaves.map((r) => r.completed_to_date)),
    forecast_to_complete: sumMoney(leaves.map((r) => r.forecast_to_complete)),
    estimated_at_completion: sumMoney(leaves.map((r) => r.estimated_at_completion)),
    variance_to_budget: sumMoney(leaves.map((r) => r.variance_to_budget)),
  }
}

// Mirror the table's grouping dimension labels (kept in lockstep with ForecastMonthlyMatrixTable).
const GROUP_DIMENSION_LABEL: Record<string, string> = {
  cost_type: 'Cost Type',
  cost_category: 'Cost Category',
}

// --- Export payload types ---------------------------------------------------------------------------

export type MonthlyExportColumn = {
  id: string
  header: string
  kind: 'text' | 'currency' | 'number' | 'month'
}

export type MonthlyExportRow = {
  id: string
  rowType: 'data' | 'group' | 'subtotal' | 'total'
  values: Record<string, string | number | null>
}

export type MonthlyExportPayload = {
  projectKey: string
  outputId: string
  generatedAtIso: string
  title: string
  columns: MonthlyExportColumn[]
  rows: MonthlyExportRow[]
  metadata: Record<string, string | number | null>
}

const TRAILING_COLUMNS: { id: keyof ForecastDbMonthlyTableRow; header: string }[] = [
  { id: 'completed_to_date', header: 'Completed to Date' },
  { id: 'forecast_to_complete', header: 'Forecast to Complete' },
  { id: 'estimated_at_completion', header: 'EAC' },
  { id: 'variance_to_budget', header: 'Variance to Budget' },
]

/**
 * Deterministic column order for the export: Cost Code, Cost Type, Projected Budget, dynamic months in
 * display order, then Completed to Date / Forecast to Complete / EAC / Variance to Budget. The hidden
 * cost_category column is never emitted as a normal column (group labels carry the category instead).
 */
export function buildMonthlyExportColumns(table: ForecastDbMonthlyTable): MonthlyExportColumn[] {
  const months = table.months ?? []
  return [
    { id: 'cost_code', header: 'Cost Code', kind: 'text' },
    { id: 'cost_type', header: 'Cost Type', kind: 'text' },
    { id: 'projected_budget', header: 'Projected Budget', kind: 'currency' },
    ...months.map((m): MonthlyExportColumn => ({ id: `m_${m.month}`, header: m.label, kind: 'month' })),
    ...TRAILING_COLUMNS.map((c): MonthlyExportColumn => ({ id: c.id, header: c.header, kind: 'currency' })),
  ]
}

function monthCell(month_values: Record<string, string>, month: string): string {
  // month_values is a dense, backend-certified map; default keeps parity with the on-screen $0 cell.
  return month_values[month] ?? '0.00'
}

function leafRowValues(
  r: ForecastDbMonthlyTableRow,
  months: ForecastDbMonthlyTableMonth[],
): Record<string, string | number | null> {
  const values: Record<string, string | number | null> = {
    cost_code: r.cost_code ?? r.budget_code_key,
    cost_type: r.cost_type ?? '—',
    projected_budget: r.projected_budget,
  }
  for (const m of months) values[`m_${m.month}`] = monthCell(r.month_values, m.month)
  values.completed_to_date = r.completed_to_date
  values.forecast_to_complete = r.forecast_to_complete
  values.estimated_at_completion = r.estimated_at_completion
  values.variance_to_budget = r.variance_to_budget
  return values
}

function aggregateRowValues(
  label: string,
  sub: SubtotalValues,
  months: ForecastDbMonthlyTableMonth[],
): Record<string, string | number | null> {
  const values: Record<string, string | number | null> = {
    cost_code: label,
    cost_type: null,
    projected_budget: sub.projected_budget,
  }
  for (const m of months) values[`m_${m.month}`] = monthCell(sub.month_values, m.month)
  values.completed_to_date = sub.completed_to_date
  values.forecast_to_complete = sub.forecast_to_complete
  values.estimated_at_completion = sub.estimated_at_completion
  values.variance_to_budget = sub.variance_to_budget
  return values
}

function emptyAggregateValues(
  label: string,
  months: ForecastDbMonthlyTableMonth[],
): Record<string, string | number | null> {
  const values: Record<string, string | number | null> = {
    cost_code: label,
    cost_type: null,
    projected_budget: null,
  }
  for (const m of months) values[`m_${m.month}`] = null
  for (const c of TRAILING_COLUMNS) values[c.id] = null
  return values
}

/**
 * Build the export rows from the current visible table view, mirroring ForecastMonthlyMatrixTable's
 * render exactly: flattened group leaves (depth > 0) are skipped; an expanded group emits its header,
 * its visible child rows, then a trailing subtotal row; a collapsed group emits a single header row
 * carrying the subtotal inline; ungrouped rows emit directly; the certified project total is appended.
 */
export function buildMonthlyExportRows({
  table,
  reactTable,
}: {
  table: ForecastDbMonthlyTable
  reactTable: Table<ForecastDbMonthlyTableRow>
}): MonthlyExportRow[] {
  const months = table.months ?? []
  const grouping = reactTable.getState().grouping
  const groupingActive = grouping.length > 0
  const groupBy = grouping[0]
  const out: MonthlyExportRow[] = []

  for (const row of reactTable.getRowModel().rows) {
    // Skip the flattened leaves TanStack also lists under an active grouping; each group's leaves are
    // emitted under their own header below so the collapsed/expanded distinction is honored.
    if (groupingActive && row.depth > 0) continue

    if (row.getIsGrouped()) {
      const leaves = row.subRows
      const sub = computeSubtotal(
        leaves.map((lr) => lr.original),
        months,
      )
      const isExpanded = row.getIsExpanded()
      const dim = GROUP_DIMENSION_LABEL[groupBy] ?? 'Group'
      const label = `${dim}: ${String(row.getGroupingValue(groupBy) ?? '—')} (${leaves.length})`
      out.push({
        id: `group:${row.id}`,
        rowType: 'group',
        // Collapsed groups carry the subtotal inline (as on screen); expanded headers stay blank.
        values: isExpanded ? emptyAggregateValues(label, months) : aggregateRowValues(label, sub, months),
      })
      if (isExpanded) {
        for (const leaf of leaves) {
          out.push({ id: `data:${leaf.id}`, rowType: 'data', values: leafRowValues(leaf.original, months) })
        }
        out.push({
          id: `subtotal:${row.id}`,
          rowType: 'subtotal',
          values: aggregateRowValues('Subtotal', sub, months),
        })
      }
      continue
    }

    out.push({ id: `data:${row.id}`, rowType: 'data', values: leafRowValues(row.original, months) })
  }

  const total = table.total_row
  if (total) {
    out.push({
      id: 'total',
      rowType: 'total',
      values: aggregateRowValues('Project total', total, months),
    })
  }

  return out
}

/** Readable metadata block describing the output and its month windows. */
export function buildMonthlyExportMetadata(
  table: ForecastDbMonthlyTable,
  generatedAtIso: string,
): Record<string, string | number | null> {
  const monthOrDash = (m: string | undefined | null) => (m ? formatMonthLabel(m) : '—')
  return {
    Project: table.project_key,
    'Output ID': table.output_id,
    'Actuals start month': monthOrDash(table.actuals_start_month),
    'Actuals through month': monthOrDash(table.actuals_through_month),
    'Forecast start month': monthOrDash(table.forecast_start_month),
    'Forecast end month': monthOrDash(table.forecast_end_month),
    'Exported at': formatExportedAt(generatedAtIso),
  }
}

export function buildMonthlyExportPayload({
  table,
  reactTable,
  generatedAtIso,
}: {
  table: ForecastDbMonthlyTable
  reactTable: Table<ForecastDbMonthlyTableRow>
  generatedAtIso: string
}): MonthlyExportPayload {
  return {
    projectKey: table.project_key,
    outputId: table.output_id,
    generatedAtIso,
    title: 'Monthly Forecast',
    columns: buildMonthlyExportColumns(table),
    rows: buildMonthlyExportRows({ table, reactTable }),
    metadata: buildMonthlyExportMetadata(table, generatedAtIso),
  }
}

// --- Filenames + timestamps (deterministic, parsed from the ISO string; no Date needed) --------------

const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/

/** ISO instant → 'YYYYMMDD-HHmm' (UTC), used in the export filename. Falls back to a stable stamp. */
export function formatExportTimestamp(iso: string): string {
  const m = ISO_RE.exec(iso)
  if (!m) return '00000000-0000'
  return `${m[1]}${m[2]}${m[3]}-${m[4]}${m[5]}`
}

/** ISO instant → readable 'YYYY-MM-DD HH:mm UTC' for the metadata block. */
export function formatExportedAt(iso: string): string {
  const m = ISO_RE.exec(iso)
  if (!m) return iso
  return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]} UTC`
}

function sanitizeFilenamePart(value: string): string {
  const cleaned = value.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '')
  return cleaned || 'forecast'
}

export function buildExportFilename(payload: MonthlyExportPayload, ext: string): string {
  const stamp = formatExportTimestamp(payload.generatedAtIso)
  const project = sanitizeFilenamePart(payload.projectKey)
  const output = sanitizeFilenamePart(payload.outputId)
  return `forecast-monthly-${project}-${output}-${stamp}.${ext}`
}

// --- CSV serialization (pure) -----------------------------------------------------------------------

function csvCell(value: string | number | null): string {
  if (value == null) return ''
  const text = typeof value === 'number' ? String(value) : value
  // Quote only when needed; double embedded quotes. Preserves commas, quotes, and line breaks.
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/** Serialize the payload to a CSV string. Money decimal strings are emitted verbatim (Excel reads them
 * as numbers); line endings are '\n'. */
export function serializeCsv(payload: MonthlyExportPayload): string {
  const lines: string[] = []
  lines.push(payload.columns.map((c) => csvCell(c.header)).join(','))
  for (const row of payload.rows) {
    lines.push(payload.columns.map((c) => csvCell(row.values[c.id] ?? null)).join(','))
  }
  return lines.join('\n')
}
