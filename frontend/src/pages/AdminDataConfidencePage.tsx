/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { api } from '../lib/api'

// Admin / Data Confidence (Prompt 11 / UI-11): secondary support surface.
// Detailed diagnostics for source/sync, jobs, evidence/guardrails, retrieval/AI, permissions, completeness.
// Primary screens link here; they only show compact badges + "View in Admin".
// All data advisory/metadata-only. No raw sensitive fields. Admin role required for these views.

export function AdminDataConfidencePage() {
  const { data: root } = useQuery({ queryKey: ['admin'], queryFn: api.getAdmin })
  const { data: srcSync } = useQuery({ queryKey: ['admin', 'source-sync-health'], queryFn: api.getAdminSourceSyncHealth })
  const { data: jobs } = useQuery({ queryKey: ['admin', 'workflow-job-health'], queryFn: api.getAdminWorkflowJobHealth })
  const { data: guard } = useQuery({ queryKey: ['admin', 'evidence-guardrails'], queryFn: api.getAdminEvidenceGuardrails })
  const { data: ret } = useQuery({ queryKey: ['admin', 'retrieval-ai-quality'], queryFn: api.getAdminRetrievalAiQuality })
  const { data: perm } = useQuery({ queryKey: ['admin', 'permissions-governance'], queryFn: api.getAdminPermissionsGovernance })
  const { data: comp } = useQuery({ queryKey: ['admin', 'data-completeness'], queryFn: api.getAdminDataCompleteness })

  const sections = [
    { key: 'source', title: 'Source / Sync Health', data: srcSync, hint: 'Coverage, freshness, Graph/mailbox/calendar deltas, blocked/review items.' },
    { key: 'jobs', title: 'Workflow / Job Health', data: jobs, hint: 'Automation, daily brief receipts, retries, no-overlap locks.' },
    { key: 'guard', title: 'Evidence / Guardrail Health', data: guard, hint: 'Data quality gates, no-raw/no-writeback proofs, evidence freshness.' },
    { key: 'ret', title: 'Retrieval / AI Quality', data: ret, hint: 'Vector/embedding/llamaindex readiness, evals, unsupported claim checks, memory quality.' },
    { key: 'perm', title: 'Permissions / Governance', data: perm, hint: 'MCP receipts/denials, policy posture, prohibited attempts (metadata only).' },
    { key: 'comp', title: 'Data Completeness / Coverage', data: comp, hint: 'Table inventory, Procore/financial/document/correspondence coverage.' },
  ]

  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-center gap-2">
        <FreshnessBadge status={root?.freshness?.overall || 'unknown'} />
        <ConfidenceBadge level={root?.confidence_summary?.overall || 'not_available'} />
        <span className="text-xs text-[var(--hb-muted)]">Admin / Data Confidence — secondary support surface</span>
        <Link to="/today" className="text-xs underline ml-auto">Back to Today →</Link>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        {sections.map((s) => (
          <div key={s.key} className="card">
            <div className="font-medium mb-1">{s.title}</div>
            {!s.data ? (
              <div className="text-[var(--hb-muted)]">Loading… (or start the analytics shell for live data)</div>
            ) : (
              <>
                {(s.data.metrics || []).slice(0, 6).map((m: any, i: number) => (
                  <div key={i} className="text-xs mb-0.5">{m.name || m.metric_id} — {m.status || '—'}</div>
                ))}
                {s.data.attention_items && s.data.attention_items.length > 0 && (
                  <div className="mt-1 text-[10px] text-amber-300">Attention: {s.data.attention_items.map((a: any) => a.note || a.kind).join('; ')}</div>
                )}
                <div className="text-[10px] text-[var(--hb-muted)] mt-1">{s.hint}</div>
              </>
            )}
          </div>
        ))}
      </div>

      <div className="advisory">
        This surface exists so primary screens (Today / Projects / My Items) stay construction-focused and free of low-level telemetry.
        All values are advisory/metadata-only. No legal, financial, schedule, safety or entitlement determinations.
        Compact badges and "View source &amp; sync details → Admin" links appear on operational pages.
      </div>

      <div className="text-[10px] text-[var(--hb-muted)]">
        Data from /api/admin/* read models (Prompt 11). See metrics catalog for ADC-001…ADC-035 definitions and caveats.
      </div>
    </div>
  )
}
