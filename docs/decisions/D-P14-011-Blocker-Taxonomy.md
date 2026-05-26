# D-P14-011: Blocker Taxonomy for Delegated Graph Proof

**Date**: 2026-05-27  
**Phase**: 14 (Prompt 01 — Blocker Taxonomy and Evidence Correction)  
**Status**: Accepted

## Decision
The HB Personal Assistant (RMF112018/hb-personal-assistant) adopts an explicit, versioned blocker taxonomy for all delegated Microsoft Graph authentication, proof, and acceptance classification work. The current acceptance posture is:

```
CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER
```

DNS/network may only be labeled the active blocker when fresh command evidence (NameResolutionError, dig/scutil failure on login.microsoftonline.com or Graph endpoints, etc.) proves it in the current runtime. Historical DNS observations from earlier runs (pre-scope-fix or pre-context clarification) are preserved as snapshots only.

## Taxonomy Table

| Classification                        | Meaning                                                                 | Typical Evidence                                      | Action |
|---------------------------------------|-------------------------------------------------------------------------|-------------------------------------------------------|--------|
| `EXTERNAL_ADMIN_CONSENT_BLOCKER`      | Microsoft login/consent flow is reachable but required permissions are awaiting tenant/admin approval. | Browser/Microsoft response, CLI JSON `blocked_no_token`, Graph 403/consent message, `auth status` after scope sanitizer. | Do not patch auth code. Wait for approval, then rerun proof per 15_Deferred_Admin_Consent_Proof_Runbook.md. |
| `EXTERNAL_NETWORK_DNS_BLOCKER`        | Microsoft login or Graph endpoints cannot resolve/reach network.       | NameResolutionError, DNS failure, connection refused on login.microsoftonline.com or tenant endpoint. | Document environment/network issue; do not misclassify as consent. Requires fresh command proof. |
| `LOCAL_PATH_PERMISSION_BLOCKER`       | Application Support, auth cache, DB, logs, or evidence paths are not writable. | `diagnostics paths` errors, EPERM on ensure_dirs.    | Use path repair guidance (see Addendum P02). |
| `LOCAL_DB_READINESS_BLOCKER`          | SQLite DB path cannot initialize/open.                                 | `blocked_db_unavailable`, migrator failures.          | Repair Application Support DB path (Addendum P03). |
| `MSAL_SCOPE_SANITIZER_REGRESSION`     | Reserved scopes (`offline_access`, `openid`, `profile`) are passed to MSAL. | MSAL reject, `auth login` fails with reserved scope error. | Patch sanitizer/tests immediately (Addendum P01). |
| `GRAPH_SCOPE_GAP`                     | Delegated login works, but one or more read scopes are missing.        | 403 on mail/calendar/files after token acquired.     | Request consent/scope update; document exact failing capability. |
| `APP_ONLY_RUNTIME_VIOLATION`          | App-only token used for mail/calendar runtime (forbidden for MVP).     | Token claim or classifier indicates app-only on runtime path. | P0 code/security defect. |
| `UNEXPECTED_RUNTIME_ERROR`            | Any uncategorized exception.                                           | Stack/error not mapped above.                         | Diagnose narrowly; do not overclassify. |

## Rationale
Stale DNS-centric language persisted in root README.md, docs/architecture/00-README.md, and Addendum P06 final evidence after the reserved-scope sanitizer (dc438ac) allowed `auth login` to reach Microsoft Graph consent enforcement. D-P14-003 and the Phase 14 package (00_README acceptance_posture, 03_Repo_Truth_Audit_Basis, 04_Blocker_Taxonomy plan) required this correction as the first action before any further implementation or closeout claims. The taxonomy prevents future misclassification and provides precise post-consent closeout commands.

## Non-Negotiable Rules (from Phase 14 00_README Global Operating Rules)
- Do not classify delegated proof as a code failure if the live evidence shows tenant/admin consent is pending.
- Do not classify DNS as the active blocker unless current command evidence proves a live DNS failure.
- Prefer deterministic local fixtures and dry-runs while delegated Graph consent is pending.
- Preserve all existing user work. Commit after each prompt with the exact expected message unless repo truth requires a narrowly adjusted one.

## References
- docs/plans/ph-14-workstream-Intelligence/04_Blocker_Taxonomy_And_Admin_Consent_Closeout_Plan.md (source of taxonomy table, post-consent proof commands, documentation correction list)
- docs/plans/ph-14-workstream-Intelligence/00_README.md (acceptance_posture, closed decisions, Global Operating Rules)
- docs/plans/ph-14-workstream-Intelligence/prompts/Prompt_01_Blocker_Taxonomy_And_Evidence_Correction.md (this prompt's objective and acceptance criteria)
- D-P14-003 (Correct stale DNS blocker documentation first)
- docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-01/ (correction evidence, validation outputs, final commit SHA)
- Updated files: README.md, docs/architecture/00-README.md, docs/evidence/remediation-addendum/final-closeout/agent-handoff-summary-p06.md, docs/evidence/remediation-addendum/prompt-06/summary.md, docs/evidence/prompt-execution-log.md

## Consequences
- All future delegated proof evidence, acceptance matrices, and handoff summaries must use the taxonomy and cite fresh command output for any DNS label.
- Historical DNS evidence from pre-P01 snapshots remains untouched except for added "historical" headers and cross-references.
- Post-admin-consent proof (Prompt 09 in this package) will be the first time full `CONDITIONALLY_ACCEPTED` without external blocker can be claimed.
