import {
  buildExportFilename,
  serializeCsv,
  type MonthlyExportColumn,
  type MonthlyExportPayload,
} from './forecastMonthlyExport'

/**
 * Side-effectful export writers for the Monthly Forecast panel. All DOM / Blob / dependency-backed work
 * lives here so the shaping core (./forecastMonthlyExport) stays pure and trivially testable. The Excel
 * writer is dynamically imported so it never enters the initial page bundle.
 */

/** Create a temporary object URL and trigger a download, then clean up. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

/** CSV export — decimal-string money emitted verbatim so Excel reads numeric cells as numbers. */
export function exportCsv(payload: MonthlyExportPayload): void {
  const blob = new Blob([serializeCsv(payload)], { type: 'text/csv;charset=utf-8' })
  downloadBlob(blob, buildExportFilename(payload, 'csv'))
}

// Numeric conversion happens ONLY at this writer boundary: currency/month/number cells become real
// numbers (with a currency number format) so Excel stores them numerically; text/blank cells pass through.
function xlsxCellValue(
  column: MonthlyExportColumn,
  value: string | number | null,
): string | number | null {
  if (value == null) return null
  if (column.kind === 'currency' || column.kind === 'month' || column.kind === 'number') {
    const n = typeof value === 'number' ? value : Number(value)
    return Number.isFinite(n) ? n : value
  }
  return value
}

const CURRENCY_NUM_FMT = '"$"#,##0.00'

function columnWidth(column: MonthlyExportColumn): number {
  if (column.id === 'cost_code') return 26
  if (column.id === 'cost_type') return 12
  return 16
}

/**
 * True .xlsx export via exceljs (dynamically imported). One "Monthly Forecast" worksheet with a metadata
 * block above the table, a frozen header row + the three identity columns, readable widths, and currency
 * formatting on the money columns.
 */
export async function exportXlsx(payload: MonthlyExportPayload): Promise<void> {
  const ExcelJS = (await import('exceljs')).default
  const workbook = new ExcelJS.Workbook()
  const sheet = workbook.addWorksheet('Monthly Forecast')

  // Metadata block (label / value rows), then a spacer, then the table.
  for (const [label, value] of Object.entries(payload.metadata)) {
    const metaRow = sheet.addRow([label, value == null ? '' : value])
    metaRow.getCell(1).font = { bold: true }
  }
  sheet.addRow([])

  const headerRowIndex = sheet.rowCount + 1
  const headerRow = sheet.addRow(payload.columns.map((c) => c.header))
  headerRow.font = { bold: true }

  for (const row of payload.rows) {
    const added = sheet.addRow(payload.columns.map((c) => xlsxCellValue(c, row.values[c.id] ?? null)))
    if (row.rowType !== 'data') added.font = { bold: true }
  }

  // Widths + currency number format (applied to data columns; the metadata block uses only cols 1–2).
  payload.columns.forEach((column, index) => {
    const sheetColumn = sheet.getColumn(index + 1)
    sheetColumn.width = columnWidth(column)
    if (column.kind === 'currency' || column.kind === 'month') sheetColumn.numFmt = CURRENCY_NUM_FMT
  })

  // Freeze the header row and the three identity columns (Cost Code / Cost Type / Projected Budget).
  sheet.views = [{ state: 'frozen', xSplit: 3, ySplit: headerRowIndex }]

  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer as BlobPart], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  downloadBlob(blob, buildExportFilename(payload, 'xlsx'))
}
