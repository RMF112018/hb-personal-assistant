# Phase 04B Prompt 00 — Repo Truth Rebaseline & Payload Coverage Audit

**Date:** 2026-05-29 · **Phase:** 04B (Procore Second-Brain Enrichment) · **Prompt:** 00
**Scope:** read-only rebaseline + payload coverage inventory. No code-behavior change, no live calls,
no DB mutation. Companion artifacts in this directory:
[`payload-field-inventory.json`](./payload-field-inventory.json),
[`normalizer-coverage-baseline.md`](./normalizer-coverage-baseline.md).

---

## 1. Baseline verification

| Check | Expected | Actual | Result |
|---|---|---|---|
| `git rev-parse HEAD` | `48dbcc4c3de09c02cd797289c8fd048f9b8a3347` | `48dbcc4c3de09c02cd797289c8fd048f9b8a3347` | ✅ match |
| Branch | (any) | `main` | documented |

`git status --short` at audit start (all pre-existing/unrelated — **not touched by this prompt**):

```
 M CLAUDE.md
 M docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker
 M docs/evidence/mvp-local-runtime/outputs/scan-sensitive.json
 M docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json
?? .code-graph/
```

`git log --oneline -n 5` (top of branch):

```
48dbcc4 feat(procore): Phase 04A re-target inspection-sections + inspection-items to project-scoped flat list endpoints and remove 2-level dispatch
6a1ba89 feat(procore): Phase 04A add inspection-sections bridge endpoint and verify inspection-items via 2-level dispatch
250a7f6 feat(procore): Phase 04A add inspections + inspection-items endpoints with PII-hashed people and per-list N+1 dispatch
b967c8f docs(evidence): refresh MVP local runtime harness and delegated-graph outputs ...
8527b1c fix(procore): retire hilltop and hilltop-gardens pending mappings and resolve mapping_consistent validate failure
```

**HEAD matches the reported Phase 04B starting point. No divergence. Cleared to proceed.**

---

## 2. Audit scope inventory

### 2.1 Endpoint registry — `src/hb_assistant/procore/endpoints.py` (23 endpoints, all `live_verified=True`)

| Endpoint id | Family | Scope | Parent / dispatch | Sensitivity |
|---|---|---|---|---|
| `projects` | foundation | none | — | low |
| `rfis` | rfis | project | inline child `replies` → rfi-responses | medium |
| `rfi-responses` | rfis | project+rfi (child) | parent = rfi id | medium |
| `submittals` | submittals | project | inline child `responses` → submittal-responses | medium |
| `submittal-responses` | submittals | project+submittal (child) | parent = submittal id | medium |
| `submittal-packages` | submittals | project (sibling) | parent = `standalone` | medium |
| `observations` | observations | project | inline child comments | high |
| `meetings` | meetings | project (grouped envelope) | flatten groups | medium |
| `meeting-detail` | meetings | project+meeting (N+1) | per-meeting GET | high |
| `meeting-topics` | meetings | project (v1.1) / nested | from meeting-detail categories | medium |
| `daily-log-weather` | daily_logs | project | — | low |
| `daily-log-manpower` | daily_logs | project | — | low |
| `daily-log-notes` | daily_logs | project | — | high (review) |
| `daily-log-deliveries` | daily_logs | project | — | medium |
| `daily-log-delays-review-routed` | daily_logs | project | — | critical (safety-routed) |
| `daily-log-inspections` | daily_logs | project | — | medium |
| `daily-log-dcrs` | daily_logs | project | — | medium |
| `punch-items` | punch_items | query-param (project_id) | — | high |
| `schedules` | schedules | company+project (v2.0) | — | medium |
| `activities` | schedules | company+project+schedule (N+1) | per-schedule GET, parent = schedule_id | medium |
| `inspections` | inspections | project (`checklist/lists`) | — | high |
| `inspection-sections` | inspections | project (`checklist/list_sections`) | — | low |
| `inspection-items` | inspections | project (`checklist/list_items`) | parent = `list_id` | high |

### 2.2 Live sync orchestrator — `src/hb_assistant/procore/live_sync.py`

`run_live_sync()` gate sequence: adapter resolve → mode/guardrails (`apply`, `sqlite_only`) →
`HB_PROCORE_LIVE` + `--confirm-live-get` → strict project-mapping gate → fail-closed for any
`live_verified=False` (structured `not_live_verified` receipt, **no API call, no DB write**). On the
verified path it paginates, runs the per-endpoint normalizer, and **upserts latest-state** to
`procore_live_records`. Inline-child dispatch (rfi `replies`, submittal `responses`, meeting `topics`)
and per-item N+1 fetch (`meeting-detail`, `activities`). **`raw_body_persisted=False` everywhere** —
raw payloads are never written to SQLite.

### 2.3 Normalizers — `src/hb_assistant/procore/normalizers/` (9 modules)

`rfi.py`, `submittal.py`, `observation.py`, `punch_item.py`, `meeting.py`, `schedule.py`,
`inspection.py`, `daily_log.py`, plus shared `hashing.py`. `projects` and the 7 per-section
daily-log normalizers are defined inline in `live_sync.py`. Every endpoint has a registered
normalizer. PII/people → SHA-256 hash summaries; free text → hash-only `*_summary`; URLs →
path-only; attachments → count/metadata. (Field-level fates in
[`normalizer-coverage-baseline.md`](./normalizer-coverage-baseline.md).)

### 2.4 SQLite migrations — `src/hb_assistant/store/migrator.py` (idempotent, additive; latest = V6)

| Version | Purpose | Procore-relevant |
|---|---|---|
| V1 | Phase 01 core tables | — |
| V2 | construction delta crawler | — |
| V3 | construction review queue | — |
| V4 | Ollama model-decisions audit | — |
| V5 | Phase 02 canonical construction index | `construction_project_identity.procore_project_id` x-ref |
| **V6** | **Phase 04A Procore live sync** | `procore_live_sync_runs`, `procore_live_records`, `procore_live_sync_watermarks` |

`procore_live_records` is **latest-state upsert** keyed by
`(project_key, endpoint_id, parent_procore_id, procore_record_id)`, normalized payload stored in a
single `canonical_json_redacted` column, with schema CHECK `raw_body_persisted = 0`.
**No history / snapshot / change-event / timeline table exists** — this is the Phase 04B schema gap.

### 2.5 Repository functions — `src/hb_assistant/store/procore_repositories.py` (8 public)

`record_sync_run_start`, `record_sync_run_complete`, `upsert_procore_live_record` (latest-state),
`update_watermark`, `count_procore_live_records`, `get_first_procore_record_id`, `get_sync_run`,
`delete_procore_live_records_by_sync_run` (rollback-by-run, dry-run default). **No history-tracking /
change-event function exists.**

### 2.6 CLI surface — `src/hb_assistant/cli/procore.py`

`auth` (status/login/refresh/logout) · `tools` (list/catalog/audit) · `mapping` (validate/list) ·
`projects list` · `companies list` · `audit` (dry-run/execute) · `sync run` · `live`
(endpoints list / sync / inspect / smoke / records count) · `obsidian` (preview/register) ·
`validate`. Live GETs are gated by `HB_PROCORE_LIVE` + `--confirm-live-get`; `live inspect` raw dumps
additionally require `--confirm-raw-payload-dump` and an explicit **non-repo** `--output-dir`.
**No `history` / `changes` / `timeline` / `actions` / `coverage` commands exist** — Phase 04B adds these.

### 2.7 Tests — `tests/` (48 Procore test files)

Normalizers, live-sync verified/fail-closed chains, endpoint registry/verification, idempotency &
rollback, CLI (auth/sync/validate/obsidian), OAuth/token/secret isolation, sensitive routing &
redaction, offline enforcement. Synthetic fixtures live in
`src/hb_assistant/construction/fixtures/procore.py` (all values `synthetic-`prefixed).

### 2.8 Phase 04A evidence — `docs/evidence/construction-intelligence-phase-04a/` (files 00–22)

23 markdown evidence files (`00-rebaseline-readiness` … `22-inspection-flat-list-endpoints`). All 23
endpoints documented as live-verified; evidence carries **redacted** sync_run_ids only — **no raw
payload bodies** are stored in the Phase 04A bundle.

---

## 3. Payload provenance (for the field inventory)

Field inventory built from **operator-provided local raw inspect payloads** at
`/private/tmp/procore-payload-review/` — 43 JSON files, project `tropical`, captured 2026-05-29 via
`procore live inspect` (GET-only). **This is the prompt's "use local raw inspect payloads if
available" path; no live calls were made by this audit.**

Only **field names, value types, nesting, and observed record counts** are recorded in the repo.
**No raw values, IDs, free text, people data, URLs, or secrets are persisted.** `custom_field_<uuid>`
keys are generalized to `custom_field_*`. The companion JSON was structurally validated (every
`fields[]` row contains only `path`/`type`/`fate`) and passed the repo sensitive-content scan.

---

## 4. Coverage gaps — endpoint-by-endpoint

| Endpoint | Local payload | Observed records | Field paths | Inventory source |
|---|---|---|---|---|
| `projects` | ✅ | 1 | 59 | local_raw_inspect |
| `rfis` | ✅ | 1 | 69 | local_raw_inspect |
| `rfi-responses` | ✅ | 1 | 8 | local_raw_inspect |
| `submittals` | ✅ | 1 | 107 | local_raw_inspect |
| `submittal-responses` | ⚠️ not nested in submittals + no file | 0 | 5 | normalizer_source |
| `submittal-packages` | ⚠️ returned 0 records | 0 | 6 | normalizer_source |
| `observations` | ✅ | 1 | 62 | local_raw_inspect |
| `meetings` | ✅ (grouped) | 31 | 22 | local_raw_inspect |
| `meeting-detail` | ✅ | 1 | 44 | local_raw_inspect |
| `meeting-topics` | ✅ nested in meeting-detail | 20 | 19 | local_raw_inspect |
| `daily-log-weather` | ⚠️ returned 0 records | 0 | 10 | normalizer_source |
| `daily-log-manpower` | ⚠️ returned 0 records | 0 | 8 | normalizer_source |
| `daily-log-notes` | ⚠️ returned 0 records | 0 | 8 | normalizer_source |
| `daily-log-deliveries` | ⚠️ returned 0 records | 0 | 9 | normalizer_source |
| `daily-log-delays-review-routed` | ⚠️ returned 0 records | 0 | 9 | normalizer_source |
| `daily-log-inspections` | ⚠️ returned 0 records | 0 | 9 | normalizer_source |
| `daily-log-dcrs` | ⚠️ returned 0 records | 0 | 25 | normalizer_source |
| `punch-items` | ✅ | 1 | 97 | local_raw_inspect |
| `schedules` | ✅ | 1 | 16 | local_raw_inspect |
| `activities` | ✅ | 1 | 31 | local_raw_inspect |
| `inspections` | ✅ | 1 | 64 | local_raw_inspect |
| `inspection-sections` | ✅ | 1 | 5 | local_raw_inspect |
| `inspection-items` | ✅ | 1 | 46 | local_raw_inspect |

**Coverage caveats for Phase 04B:**

1. **Empty-on-capture (8 endpoints):** the 7 `daily-log-*` sections and `submittal-packages`
   returned 0 records on the `tropical` capture. Their inventory reflects the **normalizer field
   contract**, not observed raw payloads — the true raw surface must be re-confirmed once records
   exist (a different project or active day).
2. **Nested-only child (`submittal-responses`):** absent both as a standalone capture file and as a
   nested array in the submittals payload (`tropical` submittals carry no `responses[]`). Inventory =
   normalizer contract; re-confirm against a submittal that has responses.
3. **`meeting-topics`** was recovered from `meeting-detail.meeting_categories[].meeting_topic[]`
   (20 nested records), not a standalone endpoint capture.
4. **Single-record samples:** most `local_raw_inspect` endpoints had 1 record captured; the field
   path set is a strong but not exhaustive union — sparse/optional fields may surface with more
   records.

---

## 5. Acceptance check

- ✅ Exact HEAD verified (`48dbcc4…`), no divergence.
- ✅ 23-endpoint registry + 9 normalizer modules (+ inline) documented.
- ✅ Raw payload **field-name** inventory generated with **no raw payload values** persisted.
- ✅ Coverage gaps documented endpoint-by-endpoint (above + companion docs).
- ✅ No live sync write or DB mutation performed.
