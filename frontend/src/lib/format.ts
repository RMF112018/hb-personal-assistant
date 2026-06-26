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

/**
 * Exact money aggregation for presentation subtotals. Backend money values are 2-dp decimal STRINGS;
 * these parse to integer cents via BigInt (never binary floating point), so group subtotals carry no
 * float drift. Display still goes through formatCurrency/formatSignedCurrency. These are presentation
 * aggregates only — they never replace backend-certified row values or the project total.
 */
export function moneyStringToCents(value: string | null | undefined): bigint {
  const raw = String(value ?? '0').trim()
  if (raw === '') return 0n
  const negative = raw.startsWith('-')
  const normalized = raw.replace(/^-/, '')
  const [wholeRaw, decimalRaw = ''] = normalized.split('.')
  const whole = BigInt(wholeRaw.replace(/[^0-9]/g, '') || '0')
  const cents = BigInt((decimalRaw.replace(/[^0-9]/g, '') + '00').slice(0, 2))
  const total = whole * 100n + cents
  return negative ? -total : total
}

export function centsToMoneyString(cents: bigint): string {
  const negative = cents < 0n
  const abs = negative ? -cents : cents
  const whole = abs / 100n
  const fraction = abs % 100n
  return `${negative ? '-' : ''}${whole}.${fraction.toString().padStart(2, '0')}`
}

/** Exact sum of money strings → a 2-dp money string (BigInt integer-cents, no float drift). */
export function sumMoney(values: Array<string | null | undefined>): string {
  return centsToMoneyString(values.reduce((acc, v) => acc + moneyStringToCents(v), 0n))
}
