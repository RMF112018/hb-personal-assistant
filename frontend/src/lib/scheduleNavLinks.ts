/** Preserve analytical query params when navigating between schedule sub-pages. */

const AS_OF_RE = /^\d{4}-\d{2}-\d{2}$/

export function scheduleAnalyticalQuery(searchParams: URLSearchParams): string {
  const next = new URLSearchParams()
  const asOf = searchParams.get('as_of') || ''
  const basis = searchParams.get('comparison_basis') || ''
  if (AS_OF_RE.test(asOf)) next.set('as_of', asOf)
  if (basis) next.set('comparison_basis', basis)
  const serialized = next.toString()
  return serialized ? `?${serialized}` : ''
}

export function scheduleNavHref(
  path: string,
  searchParams: URLSearchParams,
  mode: 'analytical' | 'import' = 'analytical',
): string {
  if (mode === 'import') return path
  return `${path}${scheduleAnalyticalQuery(searchParams)}`
}
