# 02 — Mailbox Policy & Threat Model (Phase 06 / Prompt 02)

**Generated:** 2026-05-29 (audit run)

This is the numbered Prompt-02 evidence: how the *active* Phase 06 email policy relates to the
preserved *deferred* policy, the threat model the read-only locks defend against, and the
reconciliation decisions taken against the package.

---

## 1. Active vs. deferred policy

| | Deferred (Phase 02 — preserved) | Active (Phase 06 — added) |
| --- | --- | --- |
| Module | `construction/policy/email_deferred.py` | `construction/policy/email_active.py` |
| Seed | `resources/config/email_intelligence_deferred_policy.yaml` | `resources/config/email_intelligence_active_policy.yaml` |
| DB row | V5 `construction_email_intelligence_deferred_state` (untouched) | V10 `email_intelligence_active_policy` (new) |
| Role | Records tenant grant + locks writeback/full-body false | Governs operational read-only, metadata-only, project-aware workflows |

The active policy is **additive**: the deferred module, seed, and V5 row are byte-for-byte
unchanged. V10 is `CREATE TABLE IF NOT EXISTS` only (no `ALTER`/`DROP`). The historical record of
"email intelligence was deferred in Phase 02" remains intact alongside "email intelligence is
active in Phase 06."

## 2. Threat model

The threat is that delegated tenant consent is **broader than what Phase 06 needs** — the cached
delegated token can carry `Mail.ReadWrite` (grant-but-suppress; see Prompt 00 readiness proof).
The defense is to never *rely* on the consent surface and instead lock read-only behavior in code:

| Threat | Defense |
| --- | --- |
| Code path attempts a mailbox write | Graph client is GET-only (Prompt 01 contract); `test_mutation_lockout.py` static scan |
| Policy edited to enable writeback/mutation | Pydantic `Literal` locks → `ValidationError` |
| Adapter called with a loosened flag | `ValueError` raised before SQL |
| Direct SQL write with a bad flag | SQLite `CHECK` → `IntegrityError` |
| Runtime requests a write scope | Config requests `Mail.Read` only |
| Full-mailbox backfill | `initial_backfill_mode` locked `pilot_projects_only`; `default_lookback_days` bounded 1–366 |
| Full body / attachment content persisted | `full_email_body_in_obsidian`, `attachment_content_download_by_default` locked `False` at all layers |
| Raw mailbox owner / PII stored | Owner stored as sha256 hash; no raw address in any row or `source_id` |

The four-layer lock matrix with real outputs is in `mailbox-readonly-guardrail-proof.md`.

## 3. Reconciliation decisions (repo truth vs. package)

- **Table naming:** new operational email tables adopt the package's `email_*` family
  (`email_intelligence_active_policy`, `email_source_locations`); Prompt 03 extends it. The repo's
  existing `construction_email_intelligence_deferred_state` is preserved.
- **Scope:** Prompt 02 owns only the active policy + the mailbox source registry. The remaining
  operational tables (messages, recipients, attachments, project matches, relationship candidates,
  thread summaries, review queue, processing receipts, sync state, crawl runs) are **Prompt 03**
  (V11), per the package's `05_SCHEMA_AND_DATA_MODEL.md`.
- **Policy home:** the active policy lives beside the deferred one in `construction/policy/` rather
  than a new top-level `email_intelligence/` package (which the package's target architecture
  sketches); that package can emerge in later prompts as project-match/relationship/summary modules
  land.
- **Seed location:** repo convention `resources/config/*.yaml` (the package template
  `resources/templates/email_intelligence_policy.seed.yaml` is the content source).

## 4. Validation

`137 passed` targeted; `ruff` clean; `mypy src` clean (117 files); full safe subset
`1311 passed, 1 skipped, 1 deselected`. **No stop condition triggered.**
