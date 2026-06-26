import type { Table } from '@tanstack/react-table'
import { describe, expect, it } from 'vitest'

import type { ForecastDbMonthlyTable, ForecastDbMonthlyTableRow } from '../../lib/api'
import {
  buildExportFilename,
  buildMonthlyExportColumns,
  buildMonthlyExportMetadata,
  buildMonthlyExportPayload,
  formatExportTimestamp,
  serializeCsv,
  type MonthlyExportPayload,
} from './forecastMonthlyExport'

const ISO = '2026-06-26T14:30:00.000Z'

const ROW_LAB: ForecastDbMonthlyTableRow = {
  budget_code_key: 'k-lab',
  budget_code: '1000.03-01-1000.LAB',
  cost_code: '03-01-1000',
  cost_type: 'LAB',
  cost_category: 'Preconstruction',
  projected_budget: '100000.00',
  projected_budget_source: 'procore_ep_budget_detail_rows',
  projected_budget_source_warning: null,
  month_values: { '2026-01': '1000.00', '2026-02': '0.00', '2026-03': '2500.00' },
  completed_to_date: '1000.00',
  forecast_to_complete: '2500.00',
  estimated_at_completion: '3500.00',
  variance_to_budget: '96500.00',
  confidence: 'medium',
  method_code: 'even_spread',
  reason_codes: [],
}

const ROW_MAT: ForecastDbMonthlyTableRow = {
  budget_code_key: 'k-mat',
  budget_code: '2000.03-01-2000.MAT',
  cost_code: '03-01-2000',
  cost_type: 'MAT',
  cost_category: 'Cost of Work',
  projected_budget: '50000.00',
  projected_budget_source: 'procore_ep_budget_detail_rows',
  projected_budget_source_warning: null,
  month_values: { '2026-01': '0.00', '2026-02': '500.00', '2026-03': '1000.00' },
  completed_to_date: '500.00',
  forecast_to_complete: '1000.00',
  estimated_at_completion: '1500.00',
  variance_to_budget: '48500.00',
  confidence: 'medium',
  method_code: 'even_spread',
  reason_codes: [],
}

const TABLE: ForecastDbMonthlyTable = {
  surface: 'analytics.forecast_run_readmodel.monthly_table',
  output_id: 'fout-1',
  project_key: 'tropical',
  status: 'ready',
  actuals_start_month: '2026-01',
  actuals_through_month: '2026-02',
  forecast_start_month: '2026-03',
  forecast_end_month: '2026-03',
  months: [
    { month: '2026-01', label: 'Jan 2026', value_type: 'actual' },
    { month: '2026-02', label: 'Feb 2026', value_type: 'actual' },
    { month: '2026-03', label: 'Mar 2026', value_type: 'forecast' },
  ],
  rows: [ROW_LAB, ROW_MAT],
  total_row: {
    projected_budget: '150000.00',
    month_values: { '2026-01': '1000.00', '2026-02': '500.00', '2026-03': '3500.00' },
    completed_to_date: '1500.00',
    forecast_to_complete: '3500.00',
    estimated_at_completion: '5000.00',
    variance_to_budget: '145000.00',
  },
  month_window_warnings: [],
}

// --- Minimal Table stubs that exercise buildMonthlyExportRows' use of the TanStack row API. The real
// grouping/filtering/sorting fidelity is covered against the actual instance in the table component test;
// here we drive the ungrouped / expanded / collapsed shapes deterministically.
type StubRow = {
  id: string
  depth: number
  original: ForecastDbMonthlyTableRow
  subRows: StubRow[]
  getIsGrouped: () => boolean
  getIsExpanded: () => boolean
  getGroupingValue: (id: string) => unknown
}

function leafRow(original: ForecastDbMonthlyTableRow, depth = 0): StubRow {
  return {
    id: original.budget_code_key,
    depth,
    original,
    subRows: [],
    getIsGrouped: () => false,
    getIsExpanded: () => false,
    getGroupingValue: () => undefined,
  }
}

function groupRow(value: string, leaves: ForecastDbMonthlyTableRow[], expanded: boolean): StubRow {
  return {
    id: `group-${value}`,
    depth: 0,
    original: leaves[0],
    subRows: leaves.map((l) => leafRow(l, 1)),
    getIsGrouped: () => true,
    getIsExpanded: () => expanded,
    getGroupingValue: () => value,
  }
}

function stubTable(grouping: string[], rows: StubRow[]): Table<ForecastDbMonthlyTableRow> {
  return {
    getState: () => ({ grouping }),
    getRowModel: () => ({ rows }),
  } as unknown as Table<ForecastDbMonthlyTableRow>
}

describe('forecastMonthlyExport', () => {
  it('builds deterministic columns with dynamic months in order and no cost_category column', () => {
    const cols = buildMonthlyExportColumns(TABLE)
    expect(cols.map((c) => c.id)).toEqual([
      'cost_code',
      'cost_type',
      'projected_budget',
      'm_2026-01',
      'm_2026-02',
      'm_2026-03',
      'completed_to_date',
      'forecast_to_complete',
      'estimated_at_completion',
      'variance_to_budget',
    ])
    expect(cols.find((c) => c.id === 'cost_category')).toBeUndefined()
    expect(cols.find((c) => c.id === 'estimated_at_completion')?.header).toBe('EAC')
    expect(cols.filter((c) => c.kind === 'month').map((c) => c.header)).toEqual([
      'Jan 2026',
      'Feb 2026',
      'Mar 2026',
    ])
  })

  it('generates a deterministic filename from a fixed clock', () => {
    expect(formatExportTimestamp(ISO)).toBe('20260626-1430')
    const payload = buildMonthlyExportPayload({ table: TABLE, reactTable: stubTable([], []), generatedAtIso: ISO })
    expect(buildExportFilename(payload, 'csv')).toBe('forecast-monthly-tropical-fout-1-20260626-1430.csv')
    expect(buildExportFilename(payload, 'xlsx')).toBe('forecast-monthly-tropical-fout-1-20260626-1430.xlsx')
  })

  it('exports ungrouped data rows followed by the certified project total', () => {
    const reactTable = stubTable([], [leafRow(ROW_LAB), leafRow(ROW_MAT)])
    const payload = buildMonthlyExportPayload({ table: TABLE, reactTable, generatedAtIso: ISO })
    expect(payload.rows.map((r) => r.rowType)).toEqual(['data', 'data', 'total'])
    expect(payload.rows[0].values.cost_code).toBe('03-01-1000')
    expect(payload.rows[0].values.cost_type).toBe('LAB')
    // Money stays a decimal string in the payload (no premature Number()).
    expect(payload.rows[0].values.projected_budget).toBe('100000.00')
    expect(payload.rows[0].values['m_2026-03']).toBe('2500.00')
    const total = payload.rows[2]
    expect(total.values.cost_code).toBe('Project total')
    expect(total.values.projected_budget).toBe('150000.00')
    expect(total.values.variance_to_budget).toBe('145000.00')
  })

  it('exports an expanded group as header, child rows, then subtotal (BigInt-exact)', () => {
    const grp = groupRow('LAB', [ROW_LAB, ROW_MAT], true)
    const reactTable = stubTable(
      ['cost_type'],
      [grp, leafRow(ROW_LAB, 1), leafRow(ROW_MAT, 1)],
    )
    const payload = buildMonthlyExportPayload({ table: TABLE, reactTable, generatedAtIso: ISO })
    expect(payload.rows.map((r) => r.rowType)).toEqual(['group', 'data', 'data', 'subtotal', 'total'])
    const header = payload.rows[0]
    expect(header.values.cost_code).toBe('Cost Type: LAB (2)')
    // Expanded group header carries no inline numbers.
    expect(header.values.projected_budget).toBeNull()
    const subtotal = payload.rows[3]
    expect(subtotal.values.cost_code).toBe('Subtotal')
    // 100000.00 + 50000.00 = 150000.00 (exact).
    expect(subtotal.values.projected_budget).toBe('150000.00')
    expect(subtotal.values.estimated_at_completion).toBe('5000.00')
  })

  it('exports a collapsed group as a single header row carrying the subtotal inline', () => {
    const grp = groupRow('LAB', [ROW_LAB, ROW_MAT], false)
    // Collapsed: TanStack does not emit the flattened depth-1 leaves; only the group row is present.
    const reactTable = stubTable(['cost_type'], [grp])
    const payload = buildMonthlyExportPayload({ table: TABLE, reactTable, generatedAtIso: ISO })
    expect(payload.rows.map((r) => r.rowType)).toEqual(['group', 'total'])
    const header = payload.rows[0]
    expect(header.values.cost_code).toBe('Cost Type: LAB (2)')
    // Collapsed header shows the subtotal values inline (matches the UI).
    expect(header.values.projected_budget).toBe('150000.00')
    expect(header.values.estimated_at_completion).toBe('5000.00')
    // No leaf data rows leaked for the collapsed group.
    expect(payload.rows.some((r) => r.rowType === 'data')).toBe(false)
  })

  it('builds a readable metadata block with month labels', () => {
    const meta = buildMonthlyExportMetadata(TABLE, ISO)
    expect(meta).toMatchObject({
      Project: 'tropical',
      'Output ID': 'fout-1',
      'Actuals start month': 'Jan 2026',
      'Actuals through month': 'Feb 2026',
      'Forecast start month': 'Mar 2026',
      'Forecast end month': 'Mar 2026',
      'Exported at': '2026-06-26 14:30 UTC',
    })
  })

  it('serializes CSV with raw decimal-string money and a header row', () => {
    const reactTable = stubTable([], [leafRow(ROW_LAB), leafRow(ROW_MAT)])
    const payload = buildMonthlyExportPayload({ table: TABLE, reactTable, generatedAtIso: ISO })
    const csv = serializeCsv(payload)
    const lines = csv.split('\n')
    expect(lines[0]).toBe(
      'Cost Code,Cost Type,Projected Budget,Jan 2026,Feb 2026,Mar 2026,Completed to Date,Forecast to Complete,EAC,Variance to Budget',
    )
    // Decimal strings, not rounded display strings ($100,000).
    expect(lines[1]).toContain('100000.00')
    expect(csv).not.toContain('$')
  })

  it('escapes CSV cells with commas, quotes, and newlines safely', () => {
    const payload: MonthlyExportPayload = {
      projectKey: 'p',
      outputId: 'o',
      generatedAtIso: ISO,
      title: 'Monthly Forecast',
      columns: [
        { id: 'cost_code', header: 'Cost Code', kind: 'text' },
        { id: 'cost_type', header: 'Cost Type', kind: 'text' },
      ],
      rows: [
        {
          id: 'r1',
          rowType: 'data',
          values: { cost_code: 'a,b', cost_type: 'has "quote"' },
        },
        {
          id: 'r2',
          rowType: 'data',
          values: { cost_code: 'line\nbreak', cost_type: null },
        },
      ],
      metadata: {},
    }
    const lines = serializeCsv(payload).split('\n')
    expect(lines[1]).toBe('"a,b","has ""quote"""')
    // The embedded newline keeps its row quoted (the literal \n lives inside the quoted field).
    expect(serializeCsv(payload)).toContain('"line\nbreak",')
  })

  it('does not leak implementation terms, paths, or internal identifiers', () => {
    const reactTable = stubTable(['cost_type'], [groupRow('LAB', [ROW_LAB], true), leafRow(ROW_LAB, 1)])
    const payload = buildMonthlyExportPayload({ table: TABLE, reactTable, generatedAtIso: ISO })
    const blob = serializeCsv(payload) + JSON.stringify(payload.columns) + JSON.stringify(payload.rows) + JSON.stringify(payload.metadata)
    expect(blob).not.toMatch(/raw_json/)
    expect(blob).not.toMatch(/\/Users\//)
    expect(blob).not.toMatch(/read model/i)
    expect(blob).not.toMatch(/forecast_run_readmodel/)
    expect(blob).not.toMatch(/monthly-table/)
  })
})
