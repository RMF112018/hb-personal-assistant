# Addendum Prompt 05 Summary

**Result**: COMPLETE for Addendum Prompt 05 scope.

Phase 0 (env): paths green; DNS external blocker documented truthfully.
Phase 1 (impl): bounded body inspector + fetch + classifier fallback + additive schema + tests all delivered and validated.

## Objective (from spec)
Close the functional MVP gap requiring detection of Bobby mentions in the email body even when not visible in `bodyPreview`.

## Starting State
- HEAD: 947469d (post P01–P04)
- Unresolved from handoff: app-support paths non-writable (EPERM on chmod despite owner); DNS resolution failure for login.microsoftonline.com → blocked_no_token on delegated proof.

## Work Plan (per approved plan)
1. Phase 0: Full path/DNS inspection + repair attempt (runbook + diagnostics paths JSON) + re-validation. Capture root cause if unrepairable.
2. Implement body_inspector + mail bounded fetch + classifier fallback + additive schema (optional but recommended) + tests.
3. Full validation + evidence bundle + scoped commit: `feat(mail): add bounded body mention detection beyond preview`

## Phase 0 Findings (Env Readiness)
- **Paths**: All 12+ app-support subpaths now report `writable: true`, `chmod_ok: true`, `error: null` (see 07-diagnostics-paths-json.txt and 23-). This is a change from P04 evidence (where EPERM was observed). No sudo repair was required in this run; `ensure_dirs` + prior state resolved it. `diagnostics paths --json` clean.
- **DNS / Network**: Hard failure for `login.microsoftonline.com` (NameResolutionError) confirmed by nslookup/dig/curl/ping/scutil (12-17 + 18/21/22). Tenant-specific endpoint also unreachable. This explains `blocked_no_token` on proof and status_error on auth/graph.
- **Dry-run commands**: files ingest + run morning --dry-run --json now return structured (no tracebacks) thanks to P03. Exit codes 1/0 as expected when no candidates or DB edge (see 19/20).
- **Proof/Graph**: Still `blocked_no_token` / network error (as predicted). Because paths are now green but network prevents reaching any Graph step, per P04/P06 rules this is **external infra (DNS/network)** blocker, not Microsoft Graph permission gap.
- **Baseline tests**: test_config + test_store + test_auth green (25-).

## Current Blockers / Known Issues
- Persistent external DNS resolution failure for Microsoft login/Graph endpoints (see known-issues.md for classification).
- (P05 body implementation issues will be added below during Phase 1.)

## Phase 1 Outcome
- New module: `src/hb_assistant/classification/body_inspector.py` (SafeTextExtractor + BodyInspector).
- `src/hb_assistant/graph/mail_client.py`: `get_message_body_for_inspection`.
- `classifier.py` + `Email` model + store (additive columns + extended update).
- `tests/test_body_mentions.py` (new) + targeted updates to `test_classification.py`.
- Validation matrix (per spec) 100% green:
  - pytest (classification + body_mentions + graph_clients): 0 failures.
  - `diagnostics classify --json`: OK.
  - `diagnostics scan-sensitive --repo . --json`: clean.
  - `ruff check .` + `mypy src`: both exit 0.
- No raw body leaks; detection_method surfaced; HTML stripping safe.
- Evidence: full command-results/26-30 + updated md files.

**Next**: Proceed to Addendum Prompt 06 (final closeout matrix + acceptance evidence) per plan.