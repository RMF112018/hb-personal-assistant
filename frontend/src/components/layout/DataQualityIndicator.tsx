import { useDataQualitySummary } from '../../hooks/useDataQualitySummary';
import { getDataQualityCopy } from '../../lib/statusCopy';

/**
 * Non-admin sidebar footer Data Quality indicator (P07).
 * Renders a compact "Data Quality" label with status-driven color dot (green/yellow/red/gray).
 * Hover and keyboard focus reveal latest update + concise status summary (via visible tooltip + title attr).
 * Keyboard accessible: focusable trigger (tabIndex), role/aria-describedby on tooltip, Escape to dismiss focus.
 * Uses getDataQualityCopy for consistent fallback description when no message.
 * No diagnostics or raw data exposed. Colors: green=good, yellow=degraded/unknown, red=poor, gray=other.
 * Loading/error degrade to neutral/unknown. Only shown for non-admin roles (gated in SidebarFooter).
 */
export function DataQualityIndicator() {
  const { data, isLoading, error } = useDataQualitySummary();

  const status = (data?.status || (isLoading ? 'unknown' : (error ? 'unknown' : 'unknown'))).toLowerCase();
  const last = data?.last_updated_at || null;
  const msg = data?.message || null;

  const copy = getDataQualityCopy(status);

  // Map status to visual + hover/focus text. Use copy.description for fallback consistency.
  const label = 'Data Quality';
  let colorClass: string;
  let titleLines: string[];
  if (status === 'good') {
    colorClass = 'bg-green-500';
    const when = formatWhen(last);
    titleLines = [
      'Data Quality: Good',
      `Last updated: ${when}`,
      msg || copy.description,
    ];
  } else if (status === 'degraded' || status === 'unknown') {
    colorClass = 'bg-yellow-500';
    const when = formatWhen(last);
    titleLines = [
      'Data Quality: Needs attention',
      `Last updated: ${when}`,
      msg || copy.description,
    ];
  } else if (status === 'poor') {
    colorClass = 'bg-red-500';
    titleLines = [
      'Data Quality: Poor',
      'Last updated: Not available',
      msg || copy.description,
    ];
  } else {
    colorClass = 'bg-[var(--hb-muted)]';
    titleLines = ['Data Quality: Unknown', 'Last updated: Not available', 'Status unavailable.'];
  }

  const title = titleLines.join('\n');

  return (
    <div
      className="relative px-2 py-1 text-[10px] text-[var(--hb-muted)] flex items-center gap-1.5 cursor-default select-none group"
      aria-label={label}
    >
      <span
        tabIndex={0}
        className="inline-flex items-center gap-1.5 outline-none focus-visible:ring-1 focus-visible:ring-[var(--hb-border)] rounded"
        aria-describedby="data-quality-tooltip"
        title={title}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            (e.currentTarget as HTMLElement).blur();
          }
        }}
      >
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${colorClass}`} aria-hidden="true" />
        <span>{label}</span>
      </span>
      <div
        id="data-quality-tooltip"
        role="tooltip"
        className="hidden group-hover:block group-focus-within:block absolute left-0 bottom-full mb-1 z-50 whitespace-pre-line rounded border border-[var(--hb-border)] bg-[var(--hb-surface)] px-2 py-1 text-[10px] text-[var(--hb-muted)] shadow"
      >
        {title}
      </div>
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
