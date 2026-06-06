
// Safe presenter for externally generated Markdown only (Prompt 09 / 08_ contract).
// The app detects the file (via backend), validates freshness, and renders a polished executive brief.
// It MUST NOT generate, rewrite, or execute any of the brief content. "Present/polish only".

const STATE_LABELS: Record<string, string> = {
  not_configured: 'Not configured',
  external_ai_setup_required: 'External AI setup required',
  configured_waiting: 'Configured, waiting for next run',
  brief_available: 'Brief available',
  brief_stale: 'Brief stale',
  brief_generation_failed: 'Brief generation failed',
  markdown_parse_warning: 'Markdown parse warning',
}

export function DailyBriefRenderer({
  content,
  status,
  generatedAt,
  path,
  warnings,
}: {
  content?: string
  status?: string
  generatedAt?: string
  path?: string
  warnings?: string[]
}) {
  const label = status ? (STATE_LABELS[status] || status) : 'Not available'

  if (!content) {
    return (
      <div className="card text-sm">
        Daily Brief: {label} (external file). Configure via external agent + settings.
        <div className="advisory mt-1">Source: externally generated Markdown. The app presents/polishes only and does not generate or materially rewrite content.</div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center gap-2 text-xs mb-2">
        <span className="badge badge-confidence">{label}</span>
        {generatedAt && <span className="text-[var(--hb-muted)]">• {generatedAt}</span>}
        {path && <span className="text-[var(--hb-muted)] truncate">• {path}</span>}
      </div>

      <div className="prose prose-sm prose-invert max-w-none">
        <pre className="whitespace-pre-wrap text-xs bg-[var(--hb-bg)] p-2 rounded border border-[var(--hb-border)]">{content}</pre>
      </div>

      {warnings && warnings.length > 0 && (
        <div className="text-[10px] text-amber-300 mt-1">Parse warnings: {warnings.join('; ')}</div>
      )}

      <div className="advisory mt-2">
        Source: externally generated Markdown file. The app presents/polishes only and does not generate or materially rewrite content.
      </div>
    </div>
  )
}
