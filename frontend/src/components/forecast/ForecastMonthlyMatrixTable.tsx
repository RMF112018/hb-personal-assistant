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
  type VisibilityState,
} from '@tanstack/react-table'
import { Fragment, useMemo, useState, type CSSProperties, type MutableRefObject } from 'react'

import type { ForecastDbMonthlyTable, ForecastDbMonthlyTableRow } from '../../lib/api'
import { formatCurrency, formatSignedCurrency } from '../../lib/format'
import {
  buildMonthlyExportPayload,
  computeSubtotal,
  type MonthlyExportPayload,
  type SubtotalValues,
} from './forecastMonthlyExport'

const GROUP_OPTIONS = [
  { value: 'none', label: 'No grouping' },
  { value: 'cost_type', label: 'Cost Type' },
  { value: 'cost_category', label: 'Cost Category' },
] as const
const GROUP_DIMENSION_LABEL: Record<string, string> = {
  cost_type: 'Cost Type',
  cost_category: 'Cost Category',
}

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

// Module-scope so cells don't allocate a fresh closure/object factory each render. The sticky-left
// identity cells must layer above the (CSS) sticky thead/tfoot in full-screen mode, so header/footer
// intersections sit at z 5, sticky-left body cells at z 3 (above normal body cells), while the plain
// sticky thead th / tfoot td get z 4 from CSS.
function stickyStyle(id: string, section: 'header' | 'body' | 'footer'): CSSProperties | undefined {
  if (!STICKY_IDS.has(id)) return undefined
  return {
    position: 'sticky',
    left: STICKY_LEFT[id as keyof typeof STICKY_LEFT],
    zIndex: section === 'body' ? 3 : 5,
    minWidth: id === 'cost_code' ? COST_CODE_W : id === 'cost_type' ? COST_TYPE_W : PROJECTED_W,
    background: 'var(--hb-surface, #fff)',
  }
}

export function ForecastMonthlyMatrixTable({
  table,
  loading,
  error,
  fullScreen,
  exportPayloadFactoryRef,
}: {
  table: ForecastDbMonthlyTable | undefined
  loading?: boolean
  error?: string | null
  fullScreen?: boolean
  // Stable bridge so the panel header's Export control can read the current visible view on demand
  // WITHOUT lifting any TanStack state (which would thrash the controlled-state setup). Assigning a ref
  // never triggers a re-render, so the no-refetch / no-update-loop guarantees are preserved.
  exportPayloadFactoryRef?: MutableRefObject<(() => MonthlyExportPayload) | null>
}) {
  // Fully-controlled, stable table state (each slice only changes when its setter runs).
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [grouping, setGrouping] = useState<GroupingState>([])
  const [expanded, setExpanded] = useState<ExpandedState>({})
  const [globalFilter, setGlobalFilter] = useState('')
  // cost_category is a hidden grouping-only column (no visible column added to the matrix layout).
  const [columnVisibility] = useState<VisibilityState>({ cost_category: false })

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
      // Hidden grouping-only column (Cost Category derived backend-side from the cost_code prefix).
      {
        id: 'cost_category',
        header: 'Cost Category',
        accessorFn: (r) => r.cost_category ?? 'Other',
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
    state: { sorting, columnFilters, grouping, expanded, globalFilter, columnVisibility },
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

  // Publish a current-view export factory to the panel via a ref (no state write → no re-render). It is
  // invoked only when the operator chooses an export; the timestamp is stamped at that moment.
  if (exportPayloadFactoryRef) {
    exportPayloadFactoryRef.current = table
      ? () => buildMonthlyExportPayload({ table, reactTable, generatedAtIso: new Date().toISOString() })
      : null
  }

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
  const groupBy = grouping[0] ?? 'none'
  const groupingActive = groupBy !== 'none'
  const visibleColCount = reactTable.getVisibleLeafColumns().length

  // Subtotal data cells (everything after Cost Code + Cost Type): Projected Budget (sticky), each
  // displayed month, then CtD / FtC / EAC / Variance. Reused for the collapsed group header and the
  // trailing subtotal row of an expanded group.
  const subtotalDataCells = (vals: SubtotalValues) => (
    <>
      <td style={stickyStyle('projected_budget', 'body')}>
        <span className="tabular-nums font-semibold">{formatCurrency(vals.projected_budget)}</span>
      </td>
      {months.map((m) => (
        <td key={m.month}>
          <span className="tabular-nums">{formatCurrency(vals.month_values[m.month])}</span>
        </td>
      ))}
      <td>
        <span className="tabular-nums font-semibold">{formatCurrency(vals.completed_to_date)}</span>
      </td>
      <td>
        <span className="tabular-nums font-semibold">{formatCurrency(vals.forecast_to_complete)}</span>
      </td>
      <td>
        <span className="tabular-nums font-semibold">{formatCurrency(vals.estimated_at_completion)}</span>
      </td>
      <td>
        <span
          className={`tabular-nums font-semibold ${Number(vals.variance_to_budget) < 0 ? 'text-[var(--hb-danger,#b91c1c)]' : ''}`}
        >
          {formatSignedCurrency(vals.variance_to_budget)}
        </span>
      </td>
    </>
  )

  return (
    <div className={`forecast-monthly-matrix ${fullScreen ? 'is-fullscreen' : ''}`}>
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
          Group by
          <select
            aria-label="Group rows"
            value={groupBy}
            onChange={(e) => {
              const v = e.target.value
              setGrouping(v === 'none' ? [] : [v])
              setExpanded(v === 'none' ? {} : true)
            }}
            className="forecast-input"
          >
            {GROUP_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <p className="text-xs text-[var(--hb-muted)] mb-2">
        Variance to Budget: a positive value is under budget (favorable); a negative value is over
        budget (unfavorable).
      </p>
      {groupingActive && (
        <p className="text-xs text-[var(--hb-muted)] mb-2">
          Group subtotals reflect the currently visible rows. Project total remains the certified
          output total.
        </p>
      )}

      <div className="forecast-table-wrap" style={{ overflowX: 'auto' }}>
        <table className="forecast-table forecast-matrix-table">
          <thead>
            <tr>
              {reactTable
                .getFlatHeaders()
                .filter((h) => h.column.getIsVisible())
                .map((h) => {
                const valueType = (h.column.columnDef.meta as { valueType?: string } | undefined)
                  ?.valueType
                return (
                  <th
                    key={h.id}
                    style={stickyStyle(h.column.id, 'header')}
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
              // When grouping is active, skip the flattened leaves (depth > 0); each group's leaves
              // are rendered under their own header so a trailing subtotal row can be appended.
              if (groupingActive && row.depth > 0) return null

              if (row.getIsGrouped()) {
                const leaves = row.subRows
                const sub = computeSubtotal(
                  leaves.map((lr) => lr.original),
                  months,
                )
                const isExpandedGroup = row.getIsExpanded()
                const dim = GROUP_DIMENSION_LABEL[groupBy] ?? 'Group'
                const label = String(row.getGroupingValue(groupBy) ?? '—')
                return (
                  <Fragment key={row.id}>
                    <tr className="forecast-matrix-group-row">
                      <td style={stickyStyle('cost_code', 'body')}>
                        <button
                          type="button"
                          className="forecast-matrix-th-btn"
                          aria-expanded={isExpandedGroup}
                          onClick={row.getToggleExpandedHandler()}
                        >
                          <span aria-hidden>{isExpandedGroup ? '▾' : '▸'}</span>{' '}
                          <span className="font-medium">
                            {dim}: {label}
                          </span>{' '}
                          <span className="text-[var(--hb-muted)]">({leaves.length})</span>
                        </button>
                      </td>
                      {isExpandedGroup ? (
                        <td colSpan={visibleColCount - 1} />
                      ) : (
                        // Collapsed: the group header shows the subtotal values inline.
                        <>
                          <td style={stickyStyle('cost_type', 'body')} />
                          {subtotalDataCells(sub)}
                        </>
                      )}
                    </tr>
                    {isExpandedGroup &&
                      leaves.map((leaf) => (
                        <tr key={leaf.id}>
                          {leaf.getVisibleCells().map((cell) => (
                            <td key={cell.id} style={stickyStyle(cell.column.id, 'body')}>
                              {flexRender(cell.column.columnDef.cell, cell.getContext())}
                            </td>
                          ))}
                        </tr>
                      ))}
                    {isExpandedGroup && (
                      <tr className="forecast-matrix-subtotal-row">
                        <td style={stickyStyle('cost_code', 'body')}>
                          <span className="font-semibold">Subtotal</span>
                        </td>
                        <td style={stickyStyle('cost_type', 'body')} />
                        {subtotalDataCells(sub)}
                      </tr>
                    )}
                  </Fragment>
                )
              }

              return (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} style={stickyStyle(cell.column.id, 'body')}>
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
                <td style={stickyStyle('cost_code', 'footer')}>
                  <span className="font-semibold">Project total</span>
                </td>
                <td style={stickyStyle('cost_type', 'footer')} />
                <td style={stickyStyle('projected_budget', 'footer')}>
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
