/* Forecasting Config — global staffing-template admin (Phase 5).
 * Operators manage the reusable staffing-template library (create/deactivate templates and add
 * versions) that project staffing rows inherit from. Reads are viewer-safe; writes are operator
 * gated server-side. Responses never surface raw_json. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  ForecastActionButton,
  ForecastBackLink,
  ForecastPageHeader,
  ForecastShell,
  ForecastSubnav,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from '../components/forecast/ForecastPageChrome'
import { EmptyState } from '../components/ui/EmptyState'
import { api, getLocalUiRole } from '../lib/api'

const INPUT = 'w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm'
const VERSION_FIELDS = [
  ['cost_code', 'Cost code'],
  ['cost_code_description', 'Cost code description'],
  ['default_role_title', 'Default role/title'],
  ['default_employment_type', 'Default employment type'],
  ['default_rate_unit', 'Default rate unit'],
  ['default_lab_rate', 'Default LAB rate'],
  ['default_lbn_rate', 'Default LBN rate'],
  ['default_mat_rate', 'Default MAT rate'],
] as const

function describeError(e: unknown): string {
  const message = e instanceof Error ? e.message : ''
  if (message.includes('operator_role_required')) return 'Operator access is required to save.'
  if (message.includes('not_available')) return 'Staffing data is not available.'
  return 'Could not save. Please try again.'
}

export function ForecastStaffingTemplatesPage() {
  const canEdit = getLocalUiRole() === 'operator' || getLocalUiRole() === 'admin'

  const { data: listData, refetch: refetchList } = useQuery({
    queryKey: ['forecast', 'staffing-templates'],
    queryFn: () => api.getForecastStaffingTemplates(),
  })
  const templates = (listData?.templates ?? []) as Record<string, string>[]

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data: detail, refetch: refetchDetail } = useQuery({
    queryKey: ['forecast', 'staffing-template', selectedId],
    queryFn: () => api.getForecastStaffingTemplate(selectedId as string),
    enabled: Boolean(selectedId),
  })
  const versions = (detail?.versions ?? []) as Record<string, string>[]

  const [tplKey, setTplKey] = useState('')
  const [tplName, setTplName] = useState('')
  const [version, setVersion] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onCreateTemplate() {
    if (!tplKey.trim() || !tplName.trim()) {
      setError('Template key and name are required.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.createForecastStaffingTemplate({ template_key: tplKey.trim(), template_name: tplName.trim() })
      setTplKey('')
      setTplName('')
      await refetchList()
    } catch (e) {
      setError(describeError(e))
    } finally {
      setBusy(false)
    }
  }

  async function onDeactivate(templateId: string) {
    setBusy(true)
    setError(null)
    try {
      await api.deleteForecastStaffingTemplate(templateId)
      if (selectedId === templateId) setSelectedId(null)
      await refetchList()
    } catch (e) {
      setError(describeError(e))
    } finally {
      setBusy(false)
    }
  }

  async function onAddVersion() {
    if (!selectedId) return
    setBusy(true)
    setError(null)
    try {
      const resp = (await api.addForecastStaffingTemplateVersion(selectedId, { ...version })) as {
        ok?: boolean
        errors?: { message?: string }[]
      }
      if (resp && resp.ok === false) {
        setError(resp.errors?.[0]?.message || 'That template version is not valid.')
        return
      }
      setVersion({})
      await Promise.all([refetchDetail(), refetchList()])
    } catch (e) {
      setError(describeError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <ForecastShell>
      <ForecastBackLink to="/forecasting/config" label="Back to configuration" />
      <ForecastSubnav />

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Staffing templates"
          subtitle="Reusable staffing defaults that project staffing rows can inherit from. Project rows keep any fields overridden locally."
        />
        {error && <p className="mt-2 text-sm text-rose-300">{error}</p>}

        <div className="mt-3">
          {templates.length === 0 ? (
            <EmptyState title="No staffing templates" hint="Create a template to get started." />
          ) : (
            <ForecastTable
              headers={
                <>
                  <ForecastTh>Key</ForecastTh>
                  <ForecastTh>Name</ForecastTh>
                  <ForecastTh>Status</ForecastTh>
                  <ForecastTh>Actions</ForecastTh>
                </>
              }
            >
              {templates.map((t) => (
                <tr key={t.template_id}>
                  <ForecastTd>{t.template_key}</ForecastTd>
                  <ForecastTd>{t.template_name}</ForecastTd>
                  <ForecastTd className="text-[var(--hb-muted)]">{t.active_status}</ForecastTd>
                  <ForecastTd>
                    <div className="flex gap-2">
                      <ForecastActionButton variant="ghost" onClick={() => setSelectedId(t.template_id)}>
                        Versions
                      </ForecastActionButton>
                      {canEdit && (
                        <ForecastActionButton variant="ghost" disabled={busy}
                          onClick={() => onDeactivate(t.template_id)}>
                          Deactivate
                        </ForecastActionButton>
                      )}
                    </div>
                  </ForecastTd>
                </tr>
              ))}
            </ForecastTable>
          )}
        </div>

        {canEdit && (
          <div className="mt-4 grid gap-2 border-t border-[var(--hb-border)] pt-3 md:grid-cols-3">
            <input aria-label="Template key" placeholder="Template key" className={INPUT}
              value={tplKey} onChange={(e) => setTplKey(e.target.value)} />
            <input aria-label="Template name" placeholder="Template name" className={INPUT}
              value={tplName} onChange={(e) => setTplName(e.target.value)} />
            <ForecastActionButton onClick={onCreateTemplate} disabled={busy}>
              {busy ? 'Saving…' : 'Create template'}
            </ForecastActionButton>
          </div>
        )}
      </section>

      {selectedId && (
        <section className="forecast-panel mt-4">
          <ForecastPageHeader title="Template versions"
            subtitle="Version history for the selected template. Each new version becomes the current default." />
          <div className="mt-3">
            {versions.length === 0 ? (
              <EmptyState title="No versions yet" hint="Add a version below." />
            ) : (
              <ForecastTable
                headers={<><ForecastTh>Version</ForecastTh><ForecastTh>Cost code</ForecastTh><ForecastTh>Role</ForecastTh><ForecastTh>LAB</ForecastTh></>}
              >
                {versions.map((v) => (
                  <tr key={v.template_version_id}>
                    <ForecastTd>{v.version_number}</ForecastTd>
                    <ForecastTd>{v.cost_code}</ForecastTd>
                    <ForecastTd className="text-[var(--hb-muted)]">{v.default_role_title || '—'}</ForecastTd>
                    <ForecastTd className="text-[var(--hb-muted)]">{v.default_lab_rate || '—'}</ForecastTd>
                  </tr>
                ))}
              </ForecastTable>
            )}
          </div>
          {canEdit && (
            <div className="mt-3 grid gap-2 border-t border-[var(--hb-border)] pt-3 md:grid-cols-2">
              {VERSION_FIELDS.map(([key, label]) => (
                <input key={key} aria-label={label} placeholder={label} className={INPUT}
                  value={version[key] ?? ''}
                  onChange={(e) => setVersion((s) => ({ ...s, [key]: e.target.value }))} />
              ))}
              <ForecastActionButton onClick={onAddVersion} disabled={busy}>
                {busy ? 'Saving…' : 'Add version'}
              </ForecastActionButton>
            </div>
          )}
        </section>
      )}
    </ForecastShell>
  )
}
