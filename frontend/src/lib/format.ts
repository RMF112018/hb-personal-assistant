/**
 * Canonical display formatters for forecasting surfaces. Values from the read-model API arrive as
 * decimal strings (e.g. '1234567.89') or null; these render them for executives without mutating any
 * underlying value. Null/empty/non-numeric inputs render as an em-dash, preserving null-safety.
 */
export function formatCurrency(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—'
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

export function formatNumber(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—'
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US')
}

/**
 * Signed currency for variance-style values: negatives render in parentheses, e.g. '($123,456)',
 * following the app's accounting convention. Null/non-numeric render as an em-dash.
 */
export function formatSignedCurrency(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—'
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return '—'
  if (n < 0) {
    return `(${Math.abs(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })})`
  }
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

/** Human month-column label from a YYYY-MM string, e.g. '2026-01' -> 'Jan 2026' (passthrough if invalid). */
export function formatMonthLabel(yearMonth: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(yearMonth)
  if (!m) return yearMonth
  const monthIndex = Number(m[2]) - 1
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  if (monthIndex < 0 || monthIndex > 11) return yearMonth
  return `${names[monthIndex]} ${m[1]}`
}
