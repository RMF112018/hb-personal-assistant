import { useDataQualitySummary } from '../../hooks/useDataQualitySummary';

/**
 * Prompt G — Non-admin sidebar footer Data Quality indicator.
 * Renders a compact "● Data Quality" label with status-driven color.
 * Hover (title) shows latest update + mapped message per 05_FRONTEND_UX_SPEC.
 * Intentionally simple (risk note): no diagnostics, no raw, no heavy UI.
 * Colors:
 *  - green: good
 *  - yellow: degraded / unknown (with prior setup)
 *  - red: poor / no trusted data
 * Loading and error degrade conservatively to neutral/unknown.
 * Admin note is advisory text only (no navigation).
 */
export function DataQualityIndicator() {
  const { data, isLoading, error } = useDataQualitySummary();

  const status = (data?.status || (isLoading ? 'unknown' : (error ? 'unknown' : 'unknown'))).toLowerCase();
  const last = data?.last_updated_at || null;
  const msg = data?.message || null;

  // Map status to visual + hover text (exact phrasing from spec examples, with graceful last-updated).
  // All values are const; computed once from status.
  const label = 'Data Quality';
  let colorClass: string;
  let titleLines: string[];
  if (status === 'good') {
    colorClass = 'bg-green-500';
    const when = formatWhen(last);
    titleLines = [
      'Data Quality: Good',
      `Last updated: ${when}`,
      msg || 'Sources are current.',
    ];
  } else if (status === 'degraded' || status === 'unknown') {
    colorClass = 'bg-yellow-500';
    const when = formatWhen(last);
    titleLines = [
      'Data Quality: Needs attention',
      `Last updated: ${when}`,
      msg || 'Some approved sources are stale or pending sync.',
    ];
  } else if (status === 'poor') {
    colorClass = 'bg-red-500';
    titleLines = [
      'Data Quality: Poor',
      'Last updated: Not available',
      msg || 'No approved source data has been collected yet.',
    ];
  } else {
    colorClass = 'bg-[var(--hb-muted)]';
    titleLines = ['Data Quality: Unknown', 'Last updated: Not available', 'Status unavailable.'];
  }

  // Append non-admin note for admin users (text only)
  titleLines.push('Admin users may click through to detailed diagnostics in Settings.');

  const title = titleLines.join('\n');

  return (
    <div
      className="px-2 py-1 text-[10px] text-[var(--hb-muted)] flex items-center gap-1.5 cursor-default select-none"
      title={title}
      aria-label={label}
    >
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${colorClass}`} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return 'Not available';
  try {
    const d = new Date(iso);
    // Match example style: "Jun 7, 2026 at 8:00 PM" (locale may vary; keep readable)
    const datePart = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    const timePart = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    return `${datePart} at ${timePart}`;
  } catch {
    return iso;
  }
}
