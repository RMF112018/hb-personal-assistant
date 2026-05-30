# 10 — Email Review Routing, Sensitive Category Classification & Encrypted Body Eligibility

Phase 06 Prompt 10 · **local-only** (no Graph, no mailbox) · routing is conservative;
categories are signals, not determinations · plaintext body is never persisted.

## Rebaseline

- HEAD before edits: `0168def` (Prompt 09 — email relationship candidates).
- Branch: `main`.
- Working tree before edits carried only the 3 pre-existing regenerated artifacts
  (`docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker`,
  `…/scan-sensitive.json`, `docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json`)
  and untracked `.code-graph/` — all intentionally excluded from this prompt's commit.
- Active email policy file (confirmed present):
  `src/hb_assistant/construction/policy/email_active.py` +
  `resources/config/email_intelligence_active_policy.yaml`.
- Email schema version before: **V12**; after this prompt: **V13** (additive ADD COLUMN
  on `email_review_queue`; idempotent re-apply returns 13).
- Body policy fields already existed (Prompt 08A): `full_body_storage_allowed`,
  `full_body_storage_mode='encrypted_text_vault'`, `plaintext_body_persistence_allowed`
  (Literal-locked `False`), `obsidian/evidence/log_full_body_allowed` (locked `False`),
  `encrypted_body_requires_review_for_sensitive` (`True`), `max_full_body_fetch_per_run`
  (100), `low_confidence_threshold` (0.75).

## What landed

- **`construction/email/review_categories.py`** (new) — the authoritative 23-category
  review registry (`ReviewCategory` + `REVIEW_CATEGORIES` + `classify_review_categories`).
  Reproduces the 19 legacy `attachment_analyzer` categories *exactly* (ids/levels/keywords)
  and adds the 4 Prompt 10 categories (`confidential_bid_or_estimate`, `owner_directive`,
  `subcontractor_default`, `schedule_recovery_or_acceleration`). Every category permits
  encrypted capture but **requires review first**.
- **`construction/email/review_router.py`** (new) — `ReviewRouter` + the
  `EmailBodyCaptureDecision` model. Local-only synthesis over persisted
  `email_project_matches` + `email_messages`: classifies sensitive categories, decides
  full-body-fetch + encrypted-storage eligibility (policy-gated, folder-scoped, per-run
  capped), and routes sensitive / low-confidence messages to `email_review_queue`.
- **`store/migrator.py`** — Migration **V13** (`v13_email_review_body_capture_decision`):
  additive `ALTER TABLE email_review_queue ADD COLUMN` × 4
  (`body_capture_eligible`, `encrypted_body_capture_allowed`,
  `review_required_before_body_use`, `body_capture_decision_json`). ADD COLUMN only;
  gated behind the version row so re-apply is safe. No plaintext-body column.
- **`construction/store/repositories.py`** — `enqueue_email_review_item` /
  `list_email_review_queue` extended with the 4 decision columns (defaults keep prior
  callers unaffected).
- **`cli/graph.py`** — `graph mail review-queue --project … [--lookback-days N]
  [--max-messages N] [--dry-run/--no-dry-run] --json` (local-only; default dry-run).
- **`resources/config/email_sensitivity_review_categories.json`** — the 23-category set
  with metadata (kept in sync with the module by a drift-guard test).

## Review routing modules identified

`review_categories.py` (classification), `review_router.py` (eligibility + routing),
`attachment_analyzer.py` (attachment-level sensitivity, untouched), `project_matcher.py`
(confidence bands). The pre-existing `email_review_queue` table is reused (extended), not
replaced.

## Tests added/updated

- `tests/test_review_categories.py` (new) — 23 ids, legacy parity, per-category routing,
  JSON parity, encryption-posture.
- `tests/test_review_router.py` (new) — sensitive → review, low-confidence → review,
  encrypted-storage only when policy permits, excluded folder ineligible, per-run cap,
  lookback bound, dry-run persists nothing, plaintext never marked allowed, idempotent.
- `tests/test_graph_mail_cli.py` — `review-queue` envelope + no-leak case.
- Migration version-assert bump `12 → 13` in 8 files
  (`test_migrator.py` constant + the 7 `_migrate(...) == 13` / `apply()/current_version()`
  files).
- Static `test_email_body_security.py` / `test_mutation_lockout.py` auto-scan the two new
  `construction/email/` modules — clean (no write verbs, no mutation/plaintext tokens).

## Validation

- `ruff check .` → All checks passed.
- `mypy src` → Success (127 source files).
- `python -m compileall -q src tests` → OK.
- `pytest -m "not integration and not live and not manual" --ignore=tests/test_automation.py`
  → **654 passed**.
- `tests/test_automation.py` → 4 failed — pre-existing, date-driven (today 2026-05-30 is a
  Saturday; the morning orchestrator skips weekends). Unrelated to this prompt.

See `email-review-routing-proof.md` + `email-review-routing-dry-run.json` for the category
matrix and live (redacted) routing output.
