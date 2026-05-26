# 04 — Blocker Taxonomy and Admin Consent Closeout Plan

## Objective

Prevent future misclassification of delegated Graph proof failures and provide a precise post-consent closeout plan.

## Active Classification

```text
CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER
```

## Taxonomy

| Classification | Meaning | Typical Evidence | Action |
|---|---|---|---|
| `EXTERNAL_ADMIN_CONSENT_BLOCKER` | Microsoft login/consent flow is reachable but required permissions are awaiting tenant/admin approval. | Browser/Microsoft response, CLI JSON, Graph 403/consent message. | Do not patch auth code. Wait for approval, then rerun proof. |
| `EXTERNAL_NETWORK_DNS_BLOCKER` | Microsoft login or Graph endpoints cannot resolve/reach network. | NameResolutionError, DNS failure, connection failure. | Document environment/network issue; do not misclassify as consent. |
| `LOCAL_PATH_PERMISSION_BLOCKER` | Application Support, auth cache, DB, logs, or evidence paths are not writable. | `diagnostics paths` or structured CLI error. | Use path repair guidance. |
| `LOCAL_DB_READINESS_BLOCKER` | SQLite DB path cannot initialize/open. | `blocked_db_unavailable`. | Repair Application Support DB path. |
| `MSAL_SCOPE_SANITIZER_REGRESSION` | Reserved scopes are passed to MSAL. | Error names `offline_access`, `openid`, or `profile` as rejected reserved scopes. | Patch sanitizer/tests immediately. |
| `GRAPH_SCOPE_GAP` | Delegated login works, but one read scope is missing. | 403 on mail/calendar/files after token acquired. | Request consent/scope update; document exact failing capability. |
| `APP_ONLY_RUNTIME_VIOLATION` | App-only token used for mail/calendar runtime. | Token claim or classifier indicates app-only on runtime path. | P0 code/security defect. |
| `UNEXPECTED_RUNTIME_ERROR` | Any uncategorized exception. | Stack/error not mapped above. | Diagnose narrowly; do not overclassify. |

## Documentation Correction Requirements

Update all stale references that state DNS is the active blocker unless current evidence proves DNS failure. Expected files include, subject to repo truth:

- `README.md`
- `docs/architecture/00-README.md`
- `docs/evidence/remediation-addendum/final-closeout/agent-handoff-summary-p06.md`
- delegated proof summaries under `docs/evidence/`
- any final closeout manifest/known-issues file that labels DNS as active.

## Post-Consent Proof Commands

```bash
.venv/bin/hb-assistant auth clear-cache --json
.venv/bin/hb-assistant auth login --json
.venv/bin/hb-assistant auth status --json
.venv/bin/hb-assistant diagnostics graph --safe --json
.venv/bin/hb-assistant diagnostics proof delegated-graph --json
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
```

## Required Proof Capabilities

The proof must validate:

- delegated token classification using `scp`;
- `/me`;
- mail metadata;
- bounded body retrieval;
- calendarView;
- attachment metadata;
- drive/file metadata;
- controlled eligible file download if allowed;
- app-only rejection/non-use for runtime mail/calendar;
- no Microsoft 365 mutation paths;
- no committed secrets, full bodies, or full file contents.

## Evidence Commit Requirements

Commit sanitized evidence only:

- command outputs with tokens redacted or absent;
- final classification summary;
- updated README/architecture note;
- sensitive scan output;
- proof JSON.

## Non-Negotiable Rule

Do not claim delegated Graph proof is complete until the post-consent proof actually passes.
