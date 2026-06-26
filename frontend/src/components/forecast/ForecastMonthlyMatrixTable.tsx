import {
  flexRender,
  getCoreRowModel,
  getExpandedRowModel,
  getFilteredRowModel,
  getGroupedRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
  type ExpandedState,
  type GroupingState,
  type SortingState,
} from '@tanstack/react-table'
import { useMemo, useState, type CSSProperties } from 'react'

import type { ForecastDbMonthlyTable, ForecastDbMonthlyTableRow } from '../../lib/api'
import { formatCurrency, formatSignedCurrency } from '../../lib/format'

/**
 * Table-ready operator month-window matrix. The backend supplies every authoritative value (row
 * totals, the per-month dense map, and the total row); this component only formats, sorts, filters,
 * groups, and renders. It never recomputes financial values. Identity columns (Cost Code, Cost Type,
 * Projected Budget) are sticky for horizontal scrolling; month columns are dynamic and chronological.
 *
 * Sort/filter/group/search state is held LOCAL and FULLY CONTROLLED via stable useState slices with
 * matching onChange handlers (never rebuilt as fresh arrays in the `state` object) so TanStack's
 * row-model memoization holds and its auto-reset machinery never thrashes into a render loop. Row
 * identity is pinned to budget_code_key.
 */

// Sticky identity column geometry (fixed widths so cumulative left offsets are exact).
const COST_CODE_W = 180
const COST_TYPE_W = 96
const PROJECTED_W = 140
const STICKY_LEFT = {
  cost_code: 0,
  cost_type: COST_CODE_W,
  projected_budget: COST_CODE_W + COST_TYPE_W,
}
const STICKY_IDS = new Set(['cost_code', 'cost_type', 'projected_budget'])

function num(v: string | null | undefined): number {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

// Module-scope so cells don't allocate a fresh closure/object factory each render.
function stickyStyle(id: string, header: boolean): CSSProperties | undefined {
  if (!STICKY_IDS.has(id)) return undefined
  return {
    position: 'sticky',
    left: STICKY_LEFT[id as keyof typeof STICKY_LEFT],
    zIndex: header ? 3 : 1,
    minWidth: id === 'cost_code' ? COST_CODE_W : id === 'cost_type' ? COST_TYPE_W : PROJECTED_W,
    background: 'var(--hb-surface, #fff)',
  }
}

export function ForecastMonthlyMatrixTable({
  table,
  loading,
  error,
}: {
  table: ForecastDbMonthlyTable | undefined
  loading?: boolean
  error?: string | null
}) {
  // Fully-controlled, stable table state (each slice only changes when its setter runs).
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [grouping, setGrouping] = useState<GroupingState>([])
  const [expanded, setExpanded] = useState<ExpandedState>({})
  const [globalFilter, setGlobalFilter] = useState('')

  const months = useMemo(() => table?.months ?? [], [table])
  const rows = useMemo(() => table?.rows ?? [], [table])

  const columns = useMemo<ColumnDef<ForecastDbMonthlyTableRow>[]>(() => {
    const identity: ColumnDef<ForecastDbMonthlyTableRow>[] = [
      {
        id: 'cost_code',
        header: 'Cost Code',
        accessorFn: (r) => r.cost_code ?? r.budget_code_key,
        cell: (c) => <span className="font-medium">{String(c.getValue() ?? '—')}</span>,
      },
      {
        id: 'cost_type',
        header: 'Cost Type',
        accessorFn: (r) => r.cost_type ?? '—',
      },
      {
        id: 'projected_budget',
        header: 'Projected Budget',
        accessorFn: (r) => num(r.projected_budget),
        cell: (c) => <span className="tabular-nums">{formatCurrency(c.getValue() as number)}</span>,
      },
    ]
    const monthCols: ColumnDef<ForecastDbMonthlyTableRow>[] = months.map((m) => ({
      id: `m_${m.month}`,
      header: m.label,
      accessorFn: (r) => num(r.month_values[m.month]),
      cell: (c) => <span className="tabular-nums">{formatCurrency(c.getValue() as number)}</span>,
      meta: { valueType: m.value_type },
    }))
    const trailing: ColumnDef<ForecastDbMonthlyTableRow>[] = [
      {
        id: 'completed_to_date',
        header: 'Completed to Date',
        accessorFn: (r) => num(r.completed_to_date),
        cell: (c) => <span className="tabular-nums">{formatCurrency(c.getValue() as number)}</span>,
      },
      {
        id: 'forecast_to_complete',
        header: 'Forecast to Complete',
        accessorFn: (r) => num(r.forecast_to_complete),
        cell: (c) => <span className="tabular-nums">{formatCurrency(c.getValue() as number)}</span>,
      },
      {
        id: 'estimated_at_completion',
        header: 'EAC',
        accessorFn: (r) => num(r.estimated_at_completion),
        cell: (c) => <span className="tabular-nums">{formatCurrency(c.getValue() as number)}</span>,
      },
      {
        id: 'variance_to_budget',
        header: 'Variance to Budget',
        accessorFn: (r) => num(r.variance_to_budget),
        cell: (c) => {
          const v = c.getValue() as number
          return (
            <span className={`tabular-nums ${v < 0 ? 'text-[var(--hb-danger,#b91c1c)]' : ''}`}>
              {formatSignedCurrency(v)}
            </span>
          )
        },
      },
    ]
    return [...identity, ...monthCols, ...trailing]
  }, [months])

  const reactTable = useReactTable({
    data: rows,
    columns,
    state: { sorting, columnFilters, grouping, expanded, globalFilter },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGroupingChange: setGrouping,
    onExpandedChange: setExpanded,
    onGlobalFilterChange: setGlobalFilter,
    getRowId: (row) => row.budget_code_key,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getGroupedRowModel: getGroupedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    autoResetExpanded: false,
    autoResetPageIndex: false,
    enableGlobalFilter: true,
  })

  if (error) {
    return (
      <div className="forecast-panel" role="alert">
        <p className="text-sm text-[var(--hb-muted)]">
          The monthly forecast table could not be loaded. {error}
        </p>
      </div>
    )
  }
  if (loading) {
    return (
      <div className="forecast-panel">
        <p className="text-sm text-[var(--hb-muted)]">Loading the monthly forecast table…</p>
      </div>
    )
  }
  if (!table) return null
  if (table.status === 'legacy_output_no_operator_window') {
    return (
      <div className="forecast-panel">
        <p className="text-sm text-[var(--hb-muted)]">
          This forecast predates operator-selected month windows, so a monthly table is not available
          for it. Generate a new forecast with month windows to view the matrix.
        </p>
      </div>
    )
  }
  if (rows.length === 0) {
    return (
      <div className="forecast-panel">
        <p className="text-sm text-[var(--hb-muted)]">
          This forecast has no budget-code rows to display.
        </p>
      </div>
    )
  }

  const total = table.total_row
  const costCodeFilter = (reactTable.getColumn('cost_code')?.getFilterValue() as string) ?? ''
  const costTypeFilter = (reactTable.getColumn('cost_type')?.getFilterValue() as string) ?? ''
  const isGrouped = grouping.includes('cost_type')

  return (
    <div className="forecast-monthly-matrix">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <input
          type="search"
          aria-label="Search the monthly forecast table"
          placeholder="Search…"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="forecast-input"
        />
        <input
          type="search"
          aria-label="Filter by Cost Code"
          placeholder="Filter Cost Code"
          value={costCodeFilter}
          onChange={(e) => reactTable.getColumn('cost_code')?.setFilterValue(e.target.value)}
          className="forecast-input"
        />
        <input
          type="search"
          aria-label="Filter by Cost Type"
          placeholder="Filter Cost Type"
          value={costTypeFilter}
          onChange={(e) => reactTable.getColumn('cost_type')?.setFilterValue(e.target.value)}
          className="forecast-input"
        />
        <label className="flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={isGrouped}
            onChange={(e) => {
              setGrouping(e.target.checked ? ['cost_type'] : [])
              setExpanded(e.target.checked ? true : {})
            }}
          />
          Group by Cost Type
        </label>
      </div>

      <p className="text-xs text-[var(--hb-muted)] mb-2">
        Variance to Budget: a positive value is under budget (favorable); a negative value is over
        budget (unfavorable).
      </p>

      <div className="forecast-table-wrap" style={{ overflowX: 'auto' }}>
        <table className="forecast-table forecast-matrix-table">
          <thead>
            <tr>
              {reactTable.getFlatHeaders().map((h) => {
                const valueType = (h.column.columnDef.meta as { valueType?: string } | undefined)
                  ?.valueType
                return (
                  <th
                    key={h.id}
                    style={stickyStyle(h.column.id, true)}
                    aria-sort={
                      h.column.getIsSorted() === 'asc'
                        ? 'ascending'
                        : h.column.getIsSorted() === 'desc'
                          ? 'descending'
                          : undefined
                    }
                  >
                    <button
                      type="button"
                      className="forecast-matrix-th-btn"
                      onClick={h.column.getToggleSortingHandler()}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getIsSorted() === 'asc' && ' ▲'}
                      {h.column.getIsSorted() === 'desc' && ' ▼'}
                    </button>
                    {valueType && (
                      <span className="forecast-matrix-month-tag" data-kind={valueType}>
                        {valueType === 'actual' ? 'Actual' : 'Forecast'}
                      </span>
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {reactTable.getRowModel().rows.map((row) => {
              if (row.getIsGrouped()) {
                return (
                  <tr key={row.id} className="forecast-matrix-group-row">
                    <td colSpan={columns.length} style={{ position: 'sticky', left: 0 }}>
                      <span className="font-medium">Cost Type: {String(row.getGroupingValue('cost_type') ?? '—')}</span>{' '}
                      <span className="text-[var(--hb-muted)]">({row.subRows.length})</span>
                    </td>
                  </tr>
                )
              }
              return (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} style={stickyStyle(cell.column.id, false)}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
          {total && (
            <tfoot>
              <tr className="forecast-matrix-total-row">
                <td style={stickyStyle('cost_code', false)}>
                  <span className="font-semibold">Total</span>
                </td>
                <td style={stickyStyle('cost_type', false)} />
                <td style={stickyStyle('projected_budget', false)}>
                  <span className="tabular-nums font-semibold">{formatCurrency(total.projected_budget)}</span>
                </td>
                {months.map((m) => (
                  <td key={m.month}>
                    <span className="tabular-nums">{formatCurrency(total.month_values[m.month])}</span>
                  </td>
                ))}
                <td>
                  <span className="tabular-nums font-semibold">{formatCurrency(total.completed_to_date)}</span>
                </td>
                <td>
                  <span className="tabular-nums font-semibold">{formatCurrency(total.forecast_to_complete)}</span>
                </td>
                <td>
                  <span className="tabular-nums font-semibold">{formatCurrency(total.estimated_at_completion)}</span>
                </td>
                <td>
                  <span className="tabular-nums font-semibold">{formatSignedCurrency(total.variance_to_budget)}</span>
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}
