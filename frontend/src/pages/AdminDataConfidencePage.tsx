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
  const { data: root, error: rootError } = useQuery({ queryKey: ['admin'], queryFn: api.getAdmin })
  const { data: srcSync, error: srcSyncError } = useQuery({ queryKey: ['admin', 'source-sync-health'], queryFn: api.getAdminSourceSyncHealth })
  const { data: jobs, error: jobsError } = useQuery({ queryKey: ['admin', 'workflow-job-health'], queryFn: api.getAdminWorkflowJobHealth })
  const { data: guard, error: guardError } = useQuery({ queryKey: ['admin', 'evidence-guardrails'], queryFn: api.getAdminEvidenceGuardrails })
  const { data: ret, error: retError } = useQuery({ queryKey: ['admin', 'retrieval-ai-quality'], queryFn: api.getAdminRetrievalAiQuality })
  const { data: perm, error: permError } = useQuery({ queryKey: ['admin', 'permissions-governance'], queryFn: api.getAdminPermissionsGovernance })
  const { data: comp, error: compError } = useQuery({ queryKey: ['admin', 'data-completeness'], queryFn: api.getAdminDataCompleteness })

  const sections = [
    { key: 'source', title: 'Source / Sync Health', data: srcSync, hint: 'Coverage, freshness, Graph/mailbox/calendar deltas, blocked/review items.' },
    { key: 'jobs', title: 'Workflow / Job Health', data: jobs, hint: 'Automation, daily brief receipts, retries, no-overlap locks.' },
    { key: 'guard', title: 'Evidence / Guardrail Health', data: guard, hint: 'Data quality gates, no-raw/no-writeback proofs, evidence freshness.' },
    { key: 'ret', title: 'Retrieval / AI Quality', data: ret, hint: 'Vector/embedding/llamaindex readiness, evals, unsupported claim checks, memory quality.' },
    { key: 'perm', title: 'Permissions / Governance', data: perm, hint: 'MCP receipts/denials, policy posture, prohibited attempts (metadata only).' },
    { key: 'comp', title: 'Data Completeness / Coverage', data: comp, hint: 'Table inventory, Procore/financial/document/correspondence coverage.' },
  ]

  // Prompt 16 baseline: detect role-denied (403 from backend require_admin_role) without weakening guards.
  const anyAdminError = rootError || srcSyncError || jobsError || guardError || retError || permError || compError
  function isRoleDenied(err: any): boolean {
    if (!err) return false
    const status = (err as any)?.status
    const msg = String((err as any)?.message || err || '')
    return status === 403 || msg.includes('admin_role_required') || msg.includes('403')
  }

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
              <div className="text-[var(--hb-muted)]">
                {isRoleDenied(anyAdminError)
                  ? 'Admin role required for detailed Data Confidence. Use the "Local dev role" selector in the header (switch to Admin). Backend guards remain enforced and fail-closed.'
                  : 'Loading… (or start the analytics shell for live data)'}
              </div>
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
