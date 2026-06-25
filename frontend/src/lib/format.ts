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
