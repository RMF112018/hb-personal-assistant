/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { api } from '../lib/api'
import { ErrorState } from '../components/common/ErrorState'
import { TechnicalDetails } from '../components/common/TechnicalDetails'

// Data Health (P07): business-readable admin support surface for source coverage, task status, safety, answer quality, access, and data coverage.
// Role-denied uses shared ErrorState (no dev role instructions). Technical diagnostics behind per-section disclosures.
// All data advisory/metadata-only.

export function DataHealthPage() {
  const { data: root, error: rootError } = useQuery({ queryKey: ['admin'], queryFn: api.getAdmin })
  const { data: srcSync, error: srcSyncError } = useQuery({ queryKey: ['admin', 'source-sync-health'], queryFn: api.getAdminSourceSyncHealth })
  const { data: jobs, error: jobsError } = useQuery({ queryKey: ['admin', 'workflow-job-health'], queryFn: api.getAdminWorkflowJobHealth })
  const { data: guard, error: guardError } = useQuery({ queryKey: ['admin', 'evidence-guardrails'], queryFn: api.getAdminEvidenceGuardrails })
  const { data: ret, error: retError } = useQuery({ queryKey: ['admin', 'retrieval-ai-quality'], queryFn: api.getAdminRetrievalAiQuality })
  const { data: perm, error: permError } = useQuery({ queryKey: ['admin', 'permissions-governance'], queryFn: api.getAdminPermissionsGovernance })
  const { data: comp, error: compError } = useQuery({ queryKey: ['admin', 'data-completeness'], queryFn: api.getAdminDataCompleteness })

  const sections = [
    { key: 'source', title: 'Source Updates', data: srcSync, hint: 'Coverage, freshness, Graph/mailbox/calendar deltas, blocked/review items.' },
    { key: 'jobs', title: 'Background Tasks', data: jobs, hint: 'Automation, daily brief receipts, retries, no-overlap locks.' },
    { key: 'guard', title: 'Safety Checks', data: guard, hint: 'Data quality gates, no-raw/no-writeback proofs, evidence freshness.' },
    { key: 'ret', title: 'Answer Quality', data: ret, hint: 'Vector/embedding/llamaindex readiness, evals, unsupported claim checks, memory quality.' },
    { key: 'perm', title: 'Access & Permissions', data: perm, hint: 'MCP receipts/denials, policy posture, prohibited attempts (metadata only).' },
    { key: 'comp', title: 'Data Coverage', data: comp, hint: 'Table inventory, Procore/financial/document/correspondence coverage.' },
  ]

  // Role-denied detection (fail-closed; 403 or admin_role_required). Used only to choose clean ErrorState (no dev selector guidance).
  const anyAdminError = rootError || srcSyncError || jobsError || guardError || retError || permError || compError
  function isRoleDenied(err: any): boolean {
    if (!err) return false
    const status = (err as any)?.status
    const msg = String((err as any)?.message || err || '')
    return status === 403 || msg.includes('admin_role_required') || msg.includes('403')
  }

  const roleDenied = isRoleDenied(anyAdminError)

  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-center gap-2">
        <FreshnessBadge status={root?.freshness?.overall || 'unknown'} />
        <ConfidenceBadge level={root?.confidence_summary?.overall || 'not_available'} />
        <span className="text-xs text-[var(--hb-muted)]">Data Health — advisory diagnostics</span>
        <Link to="/today" className="text-xs underline ml-auto">Back to Today →</Link>
      </div>

      {roleDenied && (
        <ErrorState userMessage="Admin role required for detailed Data Health." error={anyAdminError} />
      )}

      <div className="grid md:grid-cols-2 gap-3">
        {sections.map((s) => (
          <div key={s.key} className="card">
            <div className="font-medium mb-1">{s.title}</div>
            {!s.data ? (
              roleDenied ? (
                <div className="text-[var(--hb-muted)] text-xs">See error above for access requirements.</div>
              ) : (
                <div className="text-[var(--hb-muted)]">Data unavailable.</div>
              )
            ) : (
              <TechnicalDetails
                summary="Diagnostics"
                defaultOpen={false}
                details={
                  <>
                    {(s.data.metrics || []).slice(0, 6).map((m: any, i: number) => (
                      <div key={i} className="text-xs mb-0.5">{m.name || m.metric_id} — {m.status || '—'}</div>
                    ))}
                    {s.data.attention_items && s.data.attention_items.length > 0 && (
                      <div className="mt-1 text-[10px] text-amber-300">Attention: {s.data.attention_items.map((a: any) => a.note || a.kind).join('; ')}</div>
                    )}
                    <div className="text-[10px] text-[var(--hb-muted)] mt-1">{s.hint}</div>
                  </>
                }
              />
            )}
          </div>
        ))}
      </div>

      <div className="advisory">
        Advisory surface for construction data coverage, freshness, and operational safety posture.
        All values are metadata-only. No legal, financial, schedule, safety, or entitlement determinations.
      </div>
    </div>
  )
}
