
// Safe presenter for externally generated Markdown only (Prompt 10 / 09 / 08_ contract).
// The app detects the file (via backend), validates freshness, and renders a polished executive brief.
// It MUST NOT generate, rewrite, or execute any of the brief content. "Present/polish only".
// Recommended sections (when present in the external MD) are rendered as titled blocks for executive scanning.

const STATE_LABELS: Record<string, string> = {
  not_configured: 'Not configured',
  external_ai_setup_required: 'External AI setup required',
  configured_waiting: 'Configured, waiting for next run',
  brief_available: 'Brief available',
  brief_stale: 'Brief stale',
  brief_generation_failed: 'Brief generation failed',
  markdown_parse_warning: 'Markdown parse warning',
}

const RECOMMENDED = [
  'Executive Summary',
  "Today's Meetings",
  'Projects Needing Attention',
  'Cost / Change Exposure Signals',
  'Aging RFIs / Submittals / Decisions',
  'Correspondence Worth Reviewing',
  'Documents Changed or Requiring Review',
  'Vendor / Subcontractor Attention Items',
  'Billing / Cash / Retention Attention Items',
  'Data Confidence Notes',
]

export function DailyBriefRenderer({
  content,
  status,
  generatedAt,
  path,
  warnings,
  sections,
}: {
  content?: string
  status?: string
  generatedAt?: string
  path?: string
  warnings?: string[]
  sections?: Record<string, string>
}) {
  const label = status ? (STATE_LABELS[status] || status) : 'Not available'

  async function copyPath() {
    if (!path) return
    try {
      await navigator.clipboard.writeText(path)
    } catch {
      /* clipboard may be unavailable in some envs; non-fatal for presenter */
    }
  }

  if (!content && !sections) {
    return (
      <div className="card text-sm">
        Daily Brief: {label} (external file). Configure via external agent + settings.
        <div className="advisory mt-1">Source: externally generated Markdown. The app presents/polishes only and does not generate or materially rewrite content.</div>
        <div className="mt-2 text-xs"><a className="underline" href="#/settings">Open Settings → Daily Brief setup</a></div>
      </div>
    )
  }

  // Prefer structured sections for polished view when available
  const haveSections = sections && Object.keys(sections).length > 0
  const sectionEntries = haveSections
    ? RECOMMENDED.map((h) => [h, (sections as Record<string, string | undefined> | undefined)?.[h]]).filter(([, v]) => v) as [string, string][]
    : []

  return (
    <div className="card">
      <div className="flex items-center gap-2 text-xs mb-2">
        <span className="badge badge-confidence">{label}</span>
        {generatedAt && <span className="text-[var(--hb-muted)]">• {generatedAt}</span>}
        {path && (
          <>
            <span className="text-[var(--hb-muted)] truncate">• {path}</span>
            <button className="badge text-[10px]" onClick={copyPath} title="Copy path to open in your editor or Finder">Copy path</button>
          </>
        )}
      </div>

      {haveSections && sectionEntries.length > 0 ? (
        <div className="space-y-3">
          {sectionEntries.map(([h, body]) => (
            <div key={h}>
              <div className="text-sm font-medium mb-1">{h}</div>
              <div className="prose prose-sm prose-invert max-w-none">
                <pre className="whitespace-pre-wrap text-xs bg-[var(--hb-bg)] p-2 rounded border border-[var(--hb-border)]">{body}</pre>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="prose prose-sm prose-invert max-w-none">
          <pre className="whitespace-pre-wrap text-xs bg-[var(--hb-bg)] p-2 rounded border border-[var(--hb-border)]">{content}</pre>
        </div>
      )}

      {warnings && warnings.length > 0 && (
        <div className="text-[10px] text-amber-300 mt-1">Parse warnings: {warnings.join('; ')}</div>
      )}

      <div className="advisory mt-2">
        Source: externally generated Markdown file. The app presents/polishes only and does not generate or materially rewrite content.
        <span className="ml-2"><a className="underline" href="#/settings">Configure in Settings</a></span>
      </div>
    </div>
  )
}
