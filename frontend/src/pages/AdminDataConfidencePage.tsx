import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'

// Admin / Data Confidence is intentionally more technical but still plain-language first.
// Primary screens must link here instead of surfacing raw diagnostics.

export function AdminDataConfidencePage() {
  return (
    <div className="space-y-4 text-sm">
      <div className="flex gap-2"><FreshnessBadge status="unknown" /><ConfidenceBadge level="not_available" /></div>

      <div className="grid md:grid-cols-2 gap-3">
        <div className="card">
          <div className="font-medium mb-1">Source / Sync Health</div>
          <div>Procore connections, Graph delta freshness, last-good-run, pending approvals (admin only surfaces).</div>
        </div>
        <div className="card">
          <div className="font-medium mb-1">Workflow / Job Health</div>
          <div>Automation runs, daily brief file detection, safe-replay status.</div>
        </div>
        <div className="card">
          <div className="font-medium mb-1">Evidence / Guardrail Health</div>
          <div>Redaction, no-raw, no-writeback attestations, output fences.</div>
        </div>
        <div className="card">
          <div className="font-medium mb-1">Retrieval / AI Quality</div>
          <div>Coverage parity, keyword registry effectiveness, classification confidence.</div>
        </div>
        <div className="card">
          <div className="font-medium mb-1">Permissions / Governance</div>
          <div>Viewer / Operator / Admin role surfaces (X-HB-UI-Role), sync approval gates.</div>
        </div>
        <div className="card">
          <div className="font-medium mb-1">Data Completeness / Coverage</div>
          <div>Keyword registry vs observed terms, Procore object coverage, financial readiness (WBS/cost codes/currency).</div>
        </div>
      </div>

      <div className="advisory">This surface exists so primary screens (Today/Projects/My Items) stay construction-focused and free of low-level telemetry.</div>
    </div>
  )
}
