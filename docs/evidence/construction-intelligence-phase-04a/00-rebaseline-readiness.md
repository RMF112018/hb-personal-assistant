# Phase 04A — Prompt 00: Rebaseline & Readiness Audit

**Date:** 2026-05-28
**Posture:** Verification-only. No functional code changes. No live calls.
**Outcome:** Phase 04A — Prompt 00 — ACCEPTED-WITH-DEFERRALS — 2026-05-28

## 1. Purpose

Phase 04A ("Procore Live Enablement") opens at the Phase 04 closeout baseline.
Prompt 00 establishes the canonical evidence directory and attests that the
repo state, command surface, HTTP transport posture, OAuth readiness
references, validate trajectory, endpoint catalog, and pilot mapping all
match the inbound handoff before any live-transport work begins in
subsequent prompts. Live Procore calls are explicitly out of scope for this
prompt.

## 2. Repo State Attestation

```
$ git rev-parse HEAD
e90a5e241695535ede1e66200328f15bea20feeb

$ git branch --show-current
main

$ git merge-base --is-ancestor e90a5e2 HEAD; echo $?
0

$ git log --oneline -10
e90a5e2 docs(procore): Phase 04 final closeout summary and handoff
72b9779 test(procore): close Phase 04 validation evidence
d39487c feat(procore): add Phase 04 Obsidian register preview
faada6c feat(procore): add Phase 04 sensitive routing proof
3b33efe feat(procore): add selected daily log dry-run scope
3a670e1 feat(procore): add meeting dry-run sync normalization
400a704 feat(procore): add observation dry-run sync normalization
1ca4a43 feat(procore): add submittal dry-run sync normalization
01d0d19 feat(procore): add RFI dry-run sync normalization
ce59a98 fix(procore): clean envelope on missing secret + Keychain-aware auth status
```

```
$ git status --short
 M docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker
 M docs/evidence/mvp-local-runtime/outputs/scan-sensitive.json
 M docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json
?? .code-graph/
```

The four dirty-tree entries above pre-date this prompt and are **not within
Phase 04A scope**. They will remain unstaged for the duration of this audit
and the Phase 04A commit will touch only the three doc paths enumerated in
section 14.

## 3. Manifest and Version

| Source | Value |
|--------|-------|
| `pyproject.toml` (line 7) | `version = "1.3.0"` |
| `src/hb_assistant/__init__.py` (line 6) | `__version__ = "1.3.0"` |
| `ProcoreHTTPClient` User-Agent (line 67) | `HB-Personal-Assistant/1.3.0 (GET-only)` |

Manifest is unchanged from Phase 04 close. No version bump in this prompt.

## 4. Command Surface Snapshot

The current `hb-assistant procore` command tree at baseline `e90a5e2`:

| Group | Commands |
|-------|----------|
| `auth` | `status`, `login`, `refresh`, `logout` |
| `tools` | `list`, `catalog`, `audit` |
| `mapping` | `validate`, `list` |
| `projects` | `list` |
| `companies` | `list` |
| `audit` | `dry-run`, `execute` |
| `sync` | `run` |
| `obsidian` | `preview` |
| top-level | `validate` |

Phase 04A future-prompt territory (explicitly **not** present yet at this
baseline):

- No `procore live` subcommand group exists.
- No `procore live smoke` command exists.
- No live `requests`-backed HTTP transport is wired into `ProcoreHTTPClient`
  (see section 5).

These surfaces will be introduced by later Phase 04A prompts and will
remain gated behind `HB_PROCORE_LIVE=1` + `--confirm-live-get` until
acceptance.

## 5. HTTP Transport Posture

Reference: `src/hb_assistant/procore/http_client.py` lines 61–180.

| Property | Value |
|----------|-------|
| Transport injection | Required; default raises `ProcoreAPIError("transport_not_injected")` |
| Auto-live capability | None — the default code path cannot reach the network |
| Access token acquisition | Obtained at request time via injectable `ProcoreTokenProvider`; never persisted |
| User-Agent | `HB-Personal-Assistant/1.3.0 (GET-only)` |
| HTTP method posture | GET-only — non-GET emit is structurally absent from the client |

The transport boundary is the gating point for Phase 04A item 05-A
(production-wired live transport). Until that prompt lands, every test and
CLI invocation that exercises `ProcoreHTTPClient` must inject a fake
transport or skip; `tests/test_procore_offline_enforcement.py` is the
canonical guard.

## 6. OAuth Readiness Reference

Reference: `src/hb_assistant/procore/auth.py`.

The helper module exists and references:

- macOS Keychain entry name: `hb-assistant-procore` (via
  `macos_keychain_entry_exists()`).
- Token cache directory resolved at runtime via
  `PathPolicy().get_auth_dir()`; canonical macOS location is
  `~/Library/Application Support/HB Personal Assistant/auth/procore_token.json`.

This is a static reference attestation. **No live OAuth probe was
performed in this prompt.** No tokens were read or written; no Keychain
items were accessed. The audit confirms only that the helper module names
the expected Keychain entry and the expected cache path.

## 7. Validate-Check Trajectory

`hb-assistant procore validate --json` returned 26 checks (25 passed, 1
failed). The single failing check (`mapping_consistent`) is the Phase 03
residual carried forward through the entire Phase 04 arc and is retained
as a deferred item — its remediation is tracked under Phase 04A item 05-C.

The 26 check names, in order:

1. `seed_endpoint_contract_loadable` — pass
2. `seed_projects_loadable` — pass
3. `mapping_consistent` — **fail** (Phase 03 residual; 4 pilot + 2 pending of 6)
4. `app_profile_loadable` — pass
5. `auth_status_present` — pass
6. `redaction_module_importable` — pass
7. `obsidian_templates_resolvable` — pass (10 templates resolved)
8. `obsidian_routing_rules_loadable` — pass
9. `vault_root_configurable` — pass
10. `sqlite_schema_at_expected_version` — pass (V5)
11. `procore_tables_present` — pass (tables created on demand)
12. `http_client_demands_access_token` — pass (fail_closed)
13. `sync_pagination_method_aligned` — pass
14. `pending_projects_not_default_target` — pass (4 pilot keys; no leaks)
15. `token_provider_default_chain_shape` — pass (env_or_keychain → oauth_refreshing → missing)
16. `oauth_acquisition_path_present` — pass
17. `endpoint_verification_metadata_complete` — pass
18. `live_eligibility_blocks_ineligible` — pass (10 live-eligible; no leaks)
19. `procore_init_exports_complete` — pass
20. `rfi_normalizer_dispatch_present` — pass
21. `submittal_normalizer_dispatch_present` — pass
22. `observation_normalizer_dispatch_present` — pass
23. `meeting_normalizer_dispatch_present` — pass
24. `daily_log_selection_and_dispatch_present` — pass
25. `sensitive_routing_rules_cover_phase_04_families` — pass
26. `obsidian_renderer_phase_04_register_coverage` — pass

Summary envelope: `{"total": 26, "passed": 25, "failed": 1, "ok": false,
"strict": false}`.

## 8. Endpoint Catalog Snapshot

`hb-assistant procore tools list --json` returned 16 endpoints. Counts by
`verification_status`:

| `verification_status` | Count | Endpoint IDs |
|---|---|---|
| `official_docs_verified` | 10 | list-projects, list-rfis, list-submittals, list-drawings, list-daily-logs, list-punch-items, list-change-events, list-commitments, list-prime-contracts, list-invoices |
| `candidate` | 3 | list-observations, list-meetings, list-meeting-topics |
| `excluded_by_guardrail` | 1 | list-correspondence |
| `deferred_by_guardrail` | 2 | list-schedule, list-tasks |
| **total** | **16** | |

`is_live_eligible: true` count: **10** (all `official_docs_verified`). The
three candidate endpoints carry `is_live_eligible: false` and are skipped
by `sync.apply()` with `skipped_not_live_eligible` receipt entries until
promotion. Promotion to `official_docs_verified` is Phase 04A future-prompt
territory and depends on production transport (item 05-A) plus per-endpoint
live reconciliation.

Catalog guardrails envelope (verbatim):

```json
{
  "external_systems": "read_only",
  "writeback": "none",
  "metadata_only": true,
  "live_calls_disabled": true,
  "correspondence_excluded": true,
  "schedule_tasks_deferred": true
}
```

## 9. Pilot Mapping Snapshot

`hb-assistant procore mapping validate --json` returned the deterministic
envelope. Distribution: 4 pilot rows mapped, 2 pending rows unmapped, total
6. `ok: false` reflects the same `mapping_consistent` residual from
section 7. Envelope keys: `command`, `company_id`, `company_display_name`,
`report`, `guardrails`. The full row set is captured live in the JSON
output and is not duplicated in narrative prose to keep prose token-clean.

## 10. Validation Gates

| Gate | Command | Result |
|------|---------|--------|
| Test suite | `python -m pytest --no-header` | **831 passed, 1 skipped in 22.23s** |
| Lint | `ruff check .` | **All checks passed!** |
| Type-check | `mypy .` | **Success: no issues found in 164 source files** |
| Bytecode compile | `python -m compileall -q src tests` | clean (no output) |

The single skip is the live-gated OAuth test
(`tests/test_procore_oauth_live.py`); behavior is by design and matches
Phase 04 close. No code paths changed in this prompt — pass count is
expected to remain at 831/1-skipped until a future Phase 04A prompt adds
or removes tests.

## 11. Sensitive-Scan Attestation

| Gate | Command | Result |
|------|---------|--------|
| Repo-wide sensitive scan | `python -m pytest -q tests/test_repo_sensitive_scan.py` | PASS |
| Offline-boundary regression | `python -m pytest -q tests/test_procore_offline_enforcement.py` | PASS |
| Client-secret isolation regression | `python -m pytest -q tests/test_procore_client_secret_isolation.py` | PASS |

Attestations for this evidence artifact:

- No client secret appears in this file or in any prose authored for this
  prompt.
- No OAuth tokens, refresh tokens, or access tokens were read, written, or
  printed during this audit.
- No Procore raw response bodies were captured.
- No live HTTP request was issued.
- No SQLite, Obsidian, or log writes occurred against the local user
  directories during this audit.

## 12. Deferral Ledger Carry-Forward

The four Phase 04 deferrals carry forward unchanged into Phase 04A as the
starting state:

| ID | Item | Status | Owner / Trigger |
|----|------|--------|-----------------|
| 05-A | Production-wired `requests` transport in `ProcoreHTTPClient` | Deferred | Phase 04A future prompt; precondition for 05-B and 05-D |
| 05-B | Candidate-endpoint promotion (list-observations, list-meetings, list-meeting-topics) | Deferred | Requires 05-A + per-endpoint live reconciliation |
| 05-C | `mapping_consistent` validate-check failure (Phase 03 residual; pilot mapping update) | Deferred | Inspect `loader.py` mapping check + `procore_projects.seed.yaml` |
| 05-D | `{meeting_id}` path-template placeholder generalization in `sync.apply()` | Deferred | Two-arg `path_template.format(project_id=...)` needs multi-arg dispatch |
| 05-E | Normalizer tuple/dict return-shape consolidation (4 tuple + 1 dict) | Deferred | Blocks `_hash_summary` consolidation across the family |

Pre-existing dirty tree entries listed in section 2 are outside the Phase
04A arc and are not tracked in this ledger.

## 13. Stop-Condition Matrix

| Stop condition | Tripped? | Note |
|---|---|---|
| Live request would occur before allowed prompt | No | Default transport raises `transport_not_injected`; no live invocation attempted |
| Live env/confirm flags absent during live attempt | N/A | No live attempt |
| Non-GET HTTP method introduced | No | Client is GET-only; no edits in this prompt |
| Client secret appears in API Authorization | No | No HTTP request issued; isolation regression PASS |
| Project mapping invalid | Partial | `mapping_consistent` carries forward as deferred (item 05-C); 4 pilot mappings remain valid for routine work |
| Raw response body would be persisted | No | No persistence path exercised |
| Token or secret appears in evidence / logs / SQLite / Obsidian | No | Sensitive-scan PASS; no live OAuth or HTTP performed |
| Validation gate fails and cannot be classified | No | Only `mapping_consistent` fails, and it is classified as the Phase 03 residual deferred under item 05-C |

## 14. Files Touched by This Prompt

| Path | Change |
|------|--------|
| `docs/evidence/construction-intelligence-phase-04a/00-rebaseline-readiness.md` | New (this file) |
| `docs/architecture/00-README.md` | One-line Phase 04A Prompt 00 pointer appended |
| `docs/operations/procore-operator-runbook.md` | One short paragraph noting Phase 04A opens at baseline `e90a5e2` |

No `src/`, `tests/`, `resources/`, or template files were modified. The
four pre-existing dirty-tree entries listed in section 2 remain unstaged.

## 15. Acceptance Line

**Phase 04A — Prompt 00 — ACCEPTED-WITH-DEFERRALS — 2026-05-28.**

Baseline `e90a5e2` confirmed. Command surface, transport posture, OAuth
readiness reference, validate trajectory (26/25/1), endpoint catalog
(10/3/1/2 = 16), and pilot mapping (4/2 = 6) captured. All Phase 04
deferrals carried forward as the Phase 04A starting state under items
05-A through 05-E. Future Phase 04A prompts open from this snapshot.
