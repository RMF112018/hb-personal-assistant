# Phase 04 Prompt 01 — Entry Hardening Proof

**Date:** 2026-05-28
**Phase:** HB Construction Intelligence Phase 04 — Procore Core Project Controls
**Prompt:** 01 — Entry Hardening (surgical, no OAuth implementation)
**Operator:** local code agent (Claude, opus-4-7)

---

## 1. Purpose

Close concrete hazards in the existing Procore module surface before Phase 04
OAuth / live-GET / sync work proceeds. Surgical only. No OAuth token-exchange
implementation. No live HTTP. No writeback. Tests remain offline by default.

## 2. Inputs / scope

- Hazard map produced at Phase 04 entry rebaseline (see `00-phase-04-rebaseline.md`)
  and recon during this prompt (2 parallel `Explore` agents).
- Repo state at Phase 04 entry: `6e7ee16` (one commit above Phase 03 closeout `19e21db`).

## 3. Before / After hazard matrix

| # | Hazard | Before (file:line) | After |
|---|--------|--------------------|-------|
| 1 | `Authorization: Bearer ${client_secret}` injection | `src/hb_assistant/procore/http_client.py:70-72` resolved the client secret and injected it directly into the bearer header | Client now demands an OAuth **access token** from an injectable `access_token_provider`. Missing token raises `ProcoreAuthRequired` before any transport call. `get_procore_client_secret` is no longer imported by the client. New env path: `PROCORE_ACCESS_TOKEN` (Keychain account `access-token` under service `hb-assistant-procore`). Verified by `test_client_fails_closed_when_no_access_token`, `test_authorization_header_uses_access_token_not_client_secret`, and the new `http_client_demands_access_token` validation check. |
| 2 | Method-name mismatch (`sync.py:285` called `client.paginate(...)` but `http_client.py:147` defined `get_paginated(...)`) | Live execution would have raised `AttributeError` | `http_client.paginate` renamed; no `get_paginated` anywhere in the runtime. Verified by `test_paginate_method_aligned_with_sync_call_site` and the new `sync_pagination_method_aligned` validation check. |
| 3 | Fake `_Project` / `_Projects` fallback with hard-coded ID `"2525840"` | `src/hb_assistant/procore/sync.py:340-358` (`_load_projects_for_gate`) fabricated stub project objects assigning Tropical's pilot ID to every requested key | Method removed entirely. `_load_project_registry()` calls the real `loader.load_procore_projects()` and raises `ProcoreMappingUnavailable` on failure. Verified by `test_stub_project_loader_no_longer_exists` and `test_mapping_loader_failure_raises_mapping_unavailable`. |
| 4 | Default sync target included `pending` keys (`["hilltop", "hilltop-gardens"]`) | `src/hb_assistant/procore/sync.py:115-121` | `_resolve_pilot_projects(None)` now returns mapping-derived `status == "pilot"` keys only. Verified by `test_default_sync_target_excludes_pending_projects` and the new `pending_projects_not_default_target` validation check. |
| 5 | No fail-closed guard against pending projects in `plan()` / `apply()` | `sync.py:144-169` + `241-260` accepted any caller-supplied key | New `_assert_no_pending()` guard runs **before** any audit/transport call in both `plan()` and `apply()`. Pending keys raise `ProcorePendingProjectRejected`. `allow_pending=True` is the explicit override (also threaded through `run_sync()` and the CLI as `--allow-pending`). Verified by `test_pending_project_rejected_in_plan_without_allow_flag`, `test_pending_project_accepted_with_explicit_allow_pending`, and `test_pending_project_rejected_in_apply_without_allow_flag`. |
| 6 | Stale `__init__.py` docstring (claimed "no HTTP client lives in this module"; `__all__` omitted `ProcoreSyncCoordinator`, `run_sync`, `SyncReceipt`) | `src/hb_assistant/procore/__init__.py:1-13` + `41-62` | Docstring rewritten to reflect current capability (HTTP client + dry-run sync exist; OAuth + writeback do not). New exports added: `ProcoreHTTPClient`, `ProcoreSyncCoordinator`, `run_sync`, `SyncReceipt`, plus the three new fail-closed exceptions. Verified by the new `procore_init_exports_complete` validation check. |
| 7 | `procore validate` had no coverage of Phase 04 hazard surfaces | `src/hb_assistant/procore/validate.py:240-252` ran 11 checks; none touched bearer behavior, pagination naming, pending guard, or `__init__` exports | Four new checks added (see §4 below). Total = 15. |

Stop conditions per the prompt are all cleared:

- `Bearer.*client_secret` and `client_secret.*Bearer` searches across `src/` are empty.
- `get_paginated` remains only as a regression-check **string** in `validate.py` and `test_procore_http_client.py` — no live references.
- The four pilot project IDs (`2525840`, `2091445`, `2982068`, `3215931`) are still present in `tests/test_procore_endpoint_audit.py` and one explanatory comment in `models.py:61`. These are **pre-existing** auditor-module test fixtures using the real seed values, not the removed stub-fallback hazard. Prompt 01 scope was to remove the **stub fallback**, which is done.
- `procore validate --json` includes all 4 new checks; all pass on a fresh checkout.

## 4. New validation checks

`procore validate --json` now runs 15 checks (was 11). The four new ones, all green on the operator's machine:

```
http_client_demands_access_token:   ok=True   fail_closed=True
sync_pagination_method_aligned:     ok=True   paginate=True   legacy_get_paginated=False
pending_projects_not_default_target: ok=True  default_keys=[<pilots only>]  leaked_pending=[]
procore_init_exports_complete:      ok=True   missing=[]
```

The existing `mapping_consistent` continues to surface the 2 pending pilots (`hilltop`, `hilltop-gardens`) as informational (status==pending, no Procore ID), matching the Phase 03 closeout disposition.

## 5. Validation suite results

All commands executed offline from `/Users/bobbyfetting/hb-personal-assistant`.

| Command | Result |
|---------|--------|
| `python -m pytest tests/test_procore_*.py -q --no-header` | **119 passed** |
| `python -m pytest -q --no-header` (full suite) | **649 passed** (+9 over Phase 04 entry baseline of 640) |
| `ruff check .` | **All checks passed!** |
| `mypy .` | **Success: no issues found in 130 source files** |
| `python -m compileall src tests` | Clean |
| `hb-assistant procore validate --json` | **15 checks, 14 pass, 1 informational (`mapping_consistent` — by design)** |
| `tests/test_repo_sensitive_scan.py` | 2/2 pass (new test files contain no credential-shaped strings outside allowlists) |
| `tests/test_procore_offline_enforcement.py` | 2/2 pass (new `test_procore_sync_guards.py` uses only the injected-transport pattern; no real HTTP imports) |

## 6. Files changed in this prompt

**Created:**
- `tests/test_procore_sync_guards.py` (6 tests — pending fail-closed + mapping-unavailable)
- `docs/evidence/construction-intelligence-phase-04/01-entry-hardening-proof.md` (this file)

**Modified:**
- `src/hb_assistant/procore/errors.py` — added `ProcoreAuthRequired`, `ProcorePendingProjectRejected`, `ProcoreMappingUnavailable`
- `src/hb_assistant/procore/config.py` — added `get_procore_access_token()` (separate from `get_procore_client_secret`)
- `src/hb_assistant/procore/http_client.py` — access-token provider DI; raise `ProcoreAuthRequired` if missing; renamed `get_paginated` → `paginate`; removed `get_procore_client_secret` import
- `src/hb_assistant/procore/sync.py` — removed `_load_projects_for_gate` stub; added `_load_project_registry` (real loader) and `_assert_no_pending`; pilot-only default; `allow_pending` plumbed through `plan()`, `apply()`, and `run_sync()`
- `src/hb_assistant/procore/__init__.py` — docstring rewrite + 7 new exports
- `src/hb_assistant/procore/validate.py` — 4 new checks
- `src/hb_assistant/cli/procore.py` — `--allow-pending` flag on `procore sync run`
- `tests/test_procore_http_client.py` — pivoted fixture to access-token provider; 3 new tests
- `tests/test_procore_sync.py` — switched test project key from `hilltop` (pending) to `tropical` (pilot)
- `tests/test_procore_cli_validate.py` — updated envelope-key count from 11 → 15

**Not modified (intentionally):**
- `resources/config/procore_*.seed.yaml` (clean per rebaseline)
- `pyproject.toml`
- Pre-existing pilot-ID test fixtures in `tests/test_procore_endpoint_audit.py` (real auditor test data, not stubs)

## 7. Residual conditions

1. **OAuth token-exchange not yet implemented.** Operators must populate
   `PROCORE_ACCESS_TOKEN` (env) or Keychain account `access-token` under
   service `hb-assistant-procore` until a later prompt wires real OAuth.
2. **`procore validate` `mapping_consistent`** still reports `pending` for
   `hilltop` and `hilltop-gardens` — informational, data-action only.
3. **Pre-existing operator-side runtime artifacts** (`docs/evidence/mvp-local-runtime/outputs/...`)
   continue to be rewritten by pytest/CLI runs. Per Phase 03 / Prompt 00 guidance,
   they are not staged in this commit. Operator discards with `git checkout --`.

## 8. Phase 04 Prompt 02 readiness

- Bearer-token injection hazard closed; the client demonstrably fails closed
  on missing access token.
- Pagination method name aligned with sync call site.
- All default sync targets are now mapping-validated pilots; pending mappings
  require explicit `--allow-pending`.
- Mapping load is the only source of project IDs; no stubs remain.
- Public API surface and operator-facing CLI both reflect the new posture.
- Validation suite extended; 4 new checks attest each fix on every run.

**Greenlight for Phase 04 Prompt 02** (OAuth token-exchange + first delegated GET).
