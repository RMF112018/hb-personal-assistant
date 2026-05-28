# Phase 04A — Prompt 01: Live-Readiness Hardening

**Date:** 2026-05-28
**Posture:** Hardening pass before live transport (Prompt 02). No live HTTP performed.
**Outcome:** Phase 04A — Prompt 01 — ACCEPTED-WITH-DEFERRALS — 2026-05-28

## 1. Purpose

Prompt 01 closes three live-readiness gaps that Prompt 00 surfaced: the
absence of any `HB_PROCORE_LIVE` environment-variable gate in the Procore
CLI, the absence of a strict mapping-enforcement check at the live
execution boundary, and the absence of strict-typing coverage for the
new gate module. The remaining three sub-areas named in the prompt
spec (stale docs, endpoint metadata, broader pyproject coverage) were
inspected and determined to be already clean or out of minimal scope —
see section 3.

No live HTTP, no live OAuth, no Procore mutation, no `mapping_consistent`
fix (carried as Phase 04A item 05-C).

## 2. Repo State

| | Value |
|---|---|
| HEAD before | `c2b7901` (Phase 04A Prompt 00 close) |
| HEAD after | landed by this prompt's commit |
| Branch | `main` |
| Manifest version | `1.3.0` (unchanged) |
| Validate checks | 26 → 28 (test assertion updated) |

## 3. Sub-Area Reconciliation Summary

| Sub-area | Disposition | Detail |
|---|---|---|
| Stale docs | **Already clean** | Architecture README is current through Phase 04A Prompt 00. Historical Phase 04 evidence files (e.g., `daily-log-selection-scope-proof.md` referencing 24 checks) are intentional point-in-time snapshots and are not retroactively edited. Runbook gets a one-paragraph Phase 04A Prompt 01 note documenting the new env-var gate. |
| Command surfaces | **Hardened here** | Live branches of `audit execute` and `sync run --apply` now call `require_live_env`. Dry-run paths (`audit dry-run`, default `sync run`) are unaffected. No new CLI groups or commands added. |
| Endpoint metadata | **Already clean** | All 16 endpoints carry consistent `verification_status`, `official_reference_url`-or-`verification_reason`, `verified_at_utc`, and `verified_by`. No drift. |
| Project mapping enforcement | **Hardened here** | New `assert_live_mapping_strict()` at the live boundary. Distinct from the registry-level `mapping_consistent` check, which stays deferred as item 05-C. |
| Pyproject validation coverage | **Narrowly extended here** | `hb_assistant.procore.live_gate` added to the strict mypy override block. Broader `hb_assistant.procore.*` coverage is a separate hardening project (out of scope for this prompt). Ruff per-file-ignores unchanged. |
| Live gates | **Hardened here** | `HB_PROCORE_LIVE` env-var gate introduced; exact-`"1"` enabler; non-truthy parsing by design. Wired into the two existing live-execution branches. |

## 4. Live Env-Var Gate

Module: `src/hb_assistant/procore/live_gate.py`.

### Public API

| Name | Purpose |
|---|---|
| `LIVE_ENV_VAR = "HB_PROCORE_LIVE"` | The env-var name. |
| `LIVE_ENV_ENABLER = "1"` | The exact opt-in string. |
| `LiveEnvNotSet(ProcoreAPIError)` | Raised when a live path runs without the env-var. Carries `code="live_env_not_set"` and the offending command name. |
| `live_env_active() -> bool` | True only when env-var equals the exact enabler string. |
| `require_live_env(*, command: str) -> None` | Raises `LiveEnvNotSet` if inactive. |
| `assert_live_mapping_strict(registry, target_keys) -> None` | Raises `ProcoreAPIError(code="live_mapping_strict_violation")` listing offenders if any target is unknown / non-pilot / missing `procore_project_id`. |

### Call sites (live branches only)

| CLI command | Call sequence on the live branch |
|---|---|
| `procore audit execute --confirm` | After `--confirm` is verified, call `require_live_env(command="procore audit execute")`. On `LiveEnvNotSet`, emit redacted stderr message and `typer.Exit(2)`. |
| `procore sync run --apply --confirm` | After the existing `--confirm` / TTY guard, call `require_live_env(command="procore sync run --apply")`, then load the projects registry and call `assert_live_mapping_strict(registry, target_keys)`. On `LiveEnvNotSet`, exit 2. On `ProcoreAPIError` from the strict mapping check, exit 3. |

### Dry-run paths are unaffected

The gate is *never* called on:

- `procore audit dry-run`
- `procore sync run` (default, no `--apply`)
- `procore tools list`, `procore tools catalog`, `procore tools audit`
- `procore mapping validate`, `procore mapping list`
- `procore projects list`, `procore companies list`
- `procore obsidian preview` (no Procore HTTP)
- `procore validate`

### Error envelope shape

A redacted stderr line of the form:

```
ERROR: live execution requires HB_PROCORE_LIVE=1; command='procore <subcommand>' refused. Set HB_PROCORE_LIVE=1 explicitly to opt in.
```

No secrets, no tokens, no HTTP fields. Exit code `2` for the env-var gate;
exit code `3` for the strict mapping-check failure (mapping detail is
listed inline by offender key).

### Smoke verification (no live HTTP)

```
$ hb-assistant procore audit execute --project tropical --confirm
ERROR: live execution requires HB_PROCORE_LIVE=1; command='procore audit execute' refused. Set HB_PROCORE_LIVE=1 explicitly to opt in.

$ hb-assistant procore sync run --apply --confirm --project tropical
ERROR: live execution requires HB_PROCORE_LIVE=1; command='procore sync run --apply' refused. Set HB_PROCORE_LIVE=1 explicitly to opt in.

$ hb-assistant procore sync run --project tropical --json
{"sync_id": "<redacted-uuid>", "mode": "dry_run", ...}   # dry-run unaffected; exit 0
```

## 5. Live Mapping Enforcement

`assert_live_mapping_strict(registry, target_keys)` walks the target key
set against the projects registry and rejects any of:

- `unknown_key` — key not present in the registry.
- `status_not_pilot:<status>` — row has `status` other than `pilot`.
- `procore_project_id_empty` — row has `status == "pilot"` but no Procore
  ID (structurally impossible per `ProcoreProjectMapping`'s post-init
  validator, but retained as a belt-and-braces guard).

Distinct from registry-level `mapping_consistent`: the latter scores the
whole registry (4 pilot + 2 pending → fails) and is deferred as item 05-C.
This new check fires only on the live-execution target set, after both
`--confirm` and `HB_PROCORE_LIVE=1` have been satisfied, so the deferred
registry state does not block dry-run workflows or routine validation.

## 6. Validate-Check Trajectory

| | Before | After |
|---|---|---|
| Total checks | 26 | **28** |
| Passing | 25 | **27** |
| Failing | 1 (`mapping_consistent`, deferred 05-C) | 1 (unchanged) |

New checks (both AST-/import-level; neither executes any CLI path):

1. `live_env_gate_module_present` — imports `hb_assistant.procore.live_gate`
   and asserts the three public names exist.
2. `live_commands_require_env_var` — AST-parses `cli/procore.py`, locates
   the `audit_execute` and `sync_run` function bodies, and asserts each
   calls `require_live_env`. Wire-up regression guard.

Test `tests/test_procore_cli_validate.py` assertion bumped 26 → 28.

## 7. Pyproject Coverage Extension

Single-line addition to the strict mypy override block in
`pyproject.toml`:

```
"hb_assistant.procore.live_gate",
```

This forces strict typing on the new gate module while leaving the
broader `hb_assistant.procore.*` tree under the existing blanket
`ignore_errors = true` override (a much larger conformance project that
is intentionally out of scope here). `[tool.ruff.lint.per-file-ignores]`
unchanged — the new test file does not trip any rule under the existing
blanket pattern.

mypy now reports `Success: no issues found in 166 source files` (was 164;
delta is the new `live_gate.py` module + the new test file).

## 8. Validation Gates

| Gate | Command | Result |
|---|---|---|
| Test suite | `python -m pytest --no-header` | **851 passed, 1 skipped in 22.98s** (was 831 + 1; +20 new tests in `test_procore_live_gate.py`) |
| Lint | `ruff check .` | **All checks passed!** |
| Type-check | `mypy .` | **Success: no issues found in 166 source files** |
| Bytecode compile | `python -m compileall -q src tests` | clean (no output) |
| Procore validate | `hb-assistant procore validate --json` | 28 checks; 27 pass; `mapping_consistent` deferred |
| Procore tools list | `hb-assistant procore tools list --json` | 16 endpoints, unchanged (10/3/1/2 by `verification_status`) |
| Procore mapping validate | `hb-assistant procore mapping validate --json` | Deterministic envelope; 4 pilot + 2 pending = 6 (unchanged) |

The single pytest skip is the live-gated OAuth test
(`tests/test_procore_oauth_live.py`); behavior unchanged.

## 9. Sensitive-Scan Attestation

| Gate | Command | Result |
|---|---|---|
| Repo-wide sensitive scan | `python -m pytest -q tests/test_repo_sensitive_scan.py` | PASS |
| Offline-boundary regression | `python -m pytest -q tests/test_procore_offline_enforcement.py` | PASS |
| Client-secret isolation regression | `python -m pytest -q tests/test_procore_client_secret_isolation.py` | PASS |

Per-file attestations for this artifact and the touched docs:

- No client secret, OAuth token, refresh token, or access token appears
  in this evidence file or in any prose authored for this prompt.
- No raw Procore response bodies captured.
- No live HTTP request was issued at any point in this prompt's execution.
- The new module reads only the `HB_PROCORE_LIVE` env-var; it never
  imports `requests`, the HTTP client, or any auth path.

## 10. Deferral Ledger Carry-Forward

| ID | Item | Status |
|---|---|---|
| 05-A | Production-wired `requests` transport in `ProcoreHTTPClient` | Deferred to Phase 04A Prompt 02 |
| 05-B | Candidate-endpoint promotion (list-observations, list-meetings, list-meeting-topics) | Deferred |
| 05-C | `mapping_consistent` validate-check failure (Phase 03 residual) | Deferred (registry-level check; the new live-boundary strict-mapping check is *additive*, not a substitute) |
| 05-D | `{meeting_id}` path-template placeholder generalization | Deferred |
| 05-E | Normalizer tuple/dict return-shape consolidation | Deferred |

Pre-existing dirty tree entries (3 modified evidence files +
`.code-graph/` untracked) remain outside the Phase 04A arc.

## 11. Stop-Condition Matrix

| Stop condition | Tripped? | Note |
|---|---|---|
| Live request would occur before allowed prompt | No | New gate explicitly refuses live entry without the env-var |
| Live env/confirm flags absent during live attempt | N/A | No live attempt; gate verified by negative-path tests + CLI smoke |
| Non-GET HTTP method introduced | No | No HTTP code touched |
| Client secret appears in API Authorization | No | No HTTP request issued; client-secret isolation regression PASS |
| Project mapping invalid | Partial | `mapping_consistent` deferred (05-C). Live-boundary strict-mapping check **added** to block any future live execution from running against an invalid target set |
| Raw response body would be persisted | No | No persistence path exercised |
| Token or secret appears in evidence / logs / SQLite / Obsidian | No | Sensitive-scan PASS |
| Validation gate fails and cannot be classified | No | Only `mapping_consistent` fails; classified as deferred under 05-C |

## 12. Acceptance Line

**Phase 04A — Prompt 01 — ACCEPTED-WITH-DEFERRALS — 2026-05-28.**

Live env-var gate in place; live mapping enforcement in place; validate
coverage extended 26 → 28; pyproject narrowly extended to type-check the
new module strictly. Dry-run workflows unaffected. Surface is ready for
Prompt 02 (real transport) without live wiring having occurred.
