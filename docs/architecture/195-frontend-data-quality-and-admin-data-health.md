# 195. Frontend Data Quality and Admin Data Health

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package (P07)

## Decision

Non-admin users see a compact Data Quality status indicator (green/yellow/red/gray dot + "Data Quality" label) in the pinned SidebarFooter. The indicator is role-gated (getLocalUiRole() !== 'admin'); admins reach the translated "Data Health" surface exclusively via the support nav item (labeled "Data Health", shield icon, route /admin) and links from DataHealthPanel / Today etc.

The /admin route and backend contracts (/api/admin/* and /api/settings/data-quality/*) are unchanged. The former AdminDataConfidencePage is now DataHealthPage with:

- All 6 section titles translated per spec: Source Updates, Background Tasks, Safety Checks, Answer Quality, Access & Permissions, Data Coverage.

- Denied states use shared ErrorState with clean "Admin role required for detailed Data Health." (no "Local dev role" or selector instructions).

- Per-section metrics/attention/hints are inside <TechnicalDetails summary="Diagnostics"> disclosures (business first, tech optional).

- Header, advisory, and all cross-ref copy (StaleDataBanner, project links, AppShell footer/title, nav) updated to "Data Health"; forbidden internal terms removed from visible UI.

- DataQualityIndicator uses keyboard-accessible focusable trigger + visible role="tooltip" + aria-describedby + Escape handling (plus retained title attr); integrates getDataQualityCopy for desc fallback.

## Rationale

Implements P07 objective and acceptance criteria from the phase README and implementation package: non-admin Data Quality footer, business-readable Data Health for admins, keyboard accessible tooltip, technicals behind disclosures, no dev instructions in denied states, no changes to calculations/auth/externals.

Aligns with copy remediation standard (06), gap register (COPY-P1-001 etc.), and prior ADR 194 style.

## Guardrails

- No changes to data quality calculations, hooks, api fns, or backend.

- Local ui role remains dev simulation only; real guards fail-closed.

- No new external reads or sync.

- 'Data Confidence Notes' in Daily Brief renderer left as-is (data-facing section name outside this surface).

- Forbidden string tests retain the old "Admin / Data Confidence" literal as regression guard.

- Architecture doc added as required for major docs/code change.
