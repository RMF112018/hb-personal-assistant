// Evidence-provenance badge for Schedule Health cockpit sections (Phase 9A.2). Labels each section
// by the basis of the evidence it shows so Source-export and Application-computed CPM are never
// conflated. Display-only.

export type EvidenceBasis =
  | 'source_export'
  | 'application_computed_cpm'
  | 'quality_metric'
  | 'baseline_crosswalk'
  | 'identity_safe_version_diff'
  | 'package_manifest'
  | 'derived_read_model'
  | 'not_measurable'
  | 'deferred'

const BASIS_LABEL: Record<EvidenceBasis, string> = {
  source_export: 'Source-export',
  application_computed_cpm: 'Application-computed CPM',
  quality_metric: 'Quality metric',
  baseline_crosswalk: 'Baseline crosswalk',
  identity_safe_version_diff: 'Identity-safe diff',
  package_manifest: 'Package manifest',
  derived_read_model: 'Derived',
  not_measurable: 'Not measurable',
  deferred: 'Deferred',
}

// Computed CPM is the only application-computed basis; everything else is source/derived/proxy.
const BASIS_CLASS: Record<EvidenceBasis, string> = {
  application_computed_cpm: 'border-indigo-300 text-indigo-700',
  quality_metric: 'border-emerald-300 text-emerald-700',
  baseline_crosswalk: 'border-emerald-300 text-emerald-700',
  identity_safe_version_diff: 'border-emerald-300 text-emerald-700',
  source_export: 'border-[var(--hb-border)] text-[var(--hb-muted)]',
  package_manifest: 'border-[var(--hb-border)] text-[var(--hb-muted)]',
  derived_read_model: 'border-[var(--hb-border)] text-[var(--hb-muted)]',
  not_measurable: 'border-amber-300 text-amber-700',
  deferred: 'border-amber-300 text-amber-700',
}

export function ScheduleHealthProvenanceBadge({ basis }: { basis: EvidenceBasis }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${BASIS_CLASS[basis]}`}
      title={`Evidence basis: ${BASIS_LABEL[basis]}`}
    >
      {BASIS_LABEL[basis]}
    </span>
  )
}
