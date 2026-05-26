# Addendum Prompt 05 Command Log

**Prompt**: Addendum Prompt 05 — Implement Bounded Body Mention Detection Beyond Preview  
**Started**: 2026-05-26 (continuation after 947469d)  
**Evidence dir**: `docs/evidence/remediation-addendum/prompt-05/`

## Phase 0 Pre-Work (Env Readiness — per handoff §10)

All commands executed with full stdout/stderr + exit code capture into `command-results/`.

**Captured (01-25)**:
- 01-06: Canonical starting checks (git, python, hb-assistant version) — success.
- 07 + 23: `diagnostics paths --json` (pre/post) — **all paths now writable:true / chmod_ok:true / no errors**. (Improvement vs P04 EPERM state.)
- 08-11: Full runbook inspection (`ls -lde`, `stat -f`, `ls -lae`, `find ... stat`) on ~/Library + app support tree.
- 12-17: DNS/network probes (`scutil --dns`, nslookup, dig, curl -I, ping, tenant endpoint) — all confirm NameResolutionError for login.microsoftonline.com.
- 18: `auth status --json` — exit 1, status_error with DNS (as expected).
- 19: `files ingest --dry-run --json` — exit 1, structured (P03 hardening validated).
- 20: `run morning --dry-run --json` — exit 0 (or structured), no traceback.
- 21: `diagnostics graph --safe --json` — handled gracefully (network error in JSON).
- 22: `diagnostics proof delegated-graph --json` — exit 1, blocked_no_token (no Graph steps reached).
- 24: `diagnostics scan-sensitive --repo . --json` — clean (P01 baseline).
- 25: `pytest tests/test_config.py tests/test_store.py tests/test_auth.py` — 25+ passed, green.

(See individual NN-*.txt and *.exit files for full outputs.)

**Key observation**: Path readiness is now green in this runtime. The prior EPERM was either transient, resolved by prior ensure_dirs calls, or environmental state change. No sudo steps from runbook were executed because diagnostics showed success. DNS remains the persistent external blocker.

## Phase 1 Implementation + Validation (P05 body mention)

- BodyInspector + safe HTML stripper implemented (stdlib only).
- MailClient.get_message_body_for_inspection added (guarded, in-memory).
- Classifier extended with body_fetcher + detection_method.
- Additive schema columns + store support.
- New tests/test_body_mentions.py + updates to existing tests.
- All P05 validation commands (26-28) + full ruff (29) + mypy (30) green.
- 11/11 tests in the P05 matrix passed.

Commit prepared: feat(mail): add bounded body mention detection beyond preview

(See 26-30 outputs + updated summary/known-issues.)

## Phase 1 Implementation + Validation

(To be populated live during execution.)

---

**Operating Rules honored** (from prompt spec + handoff):
- Scoped only to body mention gap closure + required env diagnostics for truthful proof classification.
- No M365 writeback, no secret disclosure, no broad refactors.
- Evidence truthful: failures recorded as failures.
- Git hygiene: explicit scoping only; unrelated modified file + gap-closure/ + .tmp* never staged.
- Venv activation for all hb/python runs.