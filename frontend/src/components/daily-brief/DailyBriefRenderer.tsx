
import { Link } from 'react-router-dom'
import { TechnicalDetails } from '../common/TechnicalDetails'

const STATE_LABELS: Record<string, string> = {
  not_configured: 'Not available yet',
  external_ai_setup_required: 'Setup needed',
  configured_waiting: 'Waiting for the next brief',
  brief_available: 'Brief available',
  brief_stale: 'May need refresh',
  brief_generation_failed: 'Brief unavailable',
  markdown_parse_warning: 'Brief available with formatting notes',
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
      <div className="text-sm">
        <div className="font-medium">Brief not available yet.</div>
        <div className="mt-1 text-xs text-[var(--hb-muted)]">Check Daily Brief setup in Settings.</div>
        <div className="mt-3 text-xs"><Link to="/settings" className="underline">Open Settings</Link></div>
        <TechnicalDetails
          summary="Technical details"
          details={[`Status: ${label}`, path ? `Path: ${path}` : null, ...(warnings || [])].filter(Boolean).join('\n')}
          className="mt-3"
        />
      </div>
    )
  }

  // Prefer structured sections for polished view when available
  const haveSections = sections && Object.keys(sections).length > 0
  const sectionEntries = haveSections
    ? RECOMMENDED.map((h) => [h, (sections as Record<string, string | undefined> | undefined)?.[h]]).filter(([, v]) => v) as [string, string][]
    : []

  return (
    <div>
      <div className="flex items-center gap-2 text-xs mb-2">
        <span className="badge badge-confidence">{label}</span>
        {generatedAt && <span className="text-[var(--hb-muted)]">Last updated {generatedAt}</span>}
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
        <div className="text-[10px] text-amber-300 mt-1">Some brief formatting may need review.</div>
      )}

      <div className="mt-2 text-xs"><Link to="/settings" className="underline">Daily Brief setup</Link></div>
      <TechnicalDetails
        summary="Technical details"
        details={[
          path ? `Path: ${path}` : null,
          warnings && warnings.length > 0 ? `Warnings: ${warnings.join('; ')}` : null,
        ].filter(Boolean).join('\n')}
        className="mt-3"
      />
      {path && (
        <button className="badge text-[10px] mt-2" onClick={copyPath} title="Copy local file path">
          Copy path
        </button>
      )}
    </div>
  )
}
