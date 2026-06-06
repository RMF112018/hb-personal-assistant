# 181 — Phase 09 Addendum (Daily Brief V2): Obsidian Output Path & Receipt Policy

**Status:** Corrects the rendered daily-brief output path (defect D7) and hardens the rendered-output
receipt policy.
**Schema:** unchanged (V39; no migration; no persistence to trusted stores).
**Version:** 1.3.0-phase-09-addendum-v2 (package: Daily Brief V2 Executive Utility Hardening, Prompt 04).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/daily-brief-output-receipt-policy.md`,
`daily-brief-rendered-output-receipt-proof.{json,md}`;
`docs/evidence/construction-intelligence-phase-09-addendum-daily-brief-v2/daily-brief-v2-output-path-receipt-proof.{json,md}`.
**Builds on:** records 174 (output receipts & import policy), 178–180 (V2 packet, enrichment, rendering template).

---

## 1. Objective

The Prompt 00 baseline flagged **D7 — output path is wrong**: the executive-facing rendered brief had
no corrected, canonical landing location (`RENDERED_NARRATIVE_LOCATION` pointed at
`<vault>/Construction Intelligence/Phase 09 Rendered Daily Briefs/`). Prompt 04 corrects the rendered
brief path and tightens the receipt policy.

## 2. Canonical path & filename

```
/Users/bobbyfetting/Documents/Obsidian Vault/Work/Daily Brief/<date>-daily-brief.md
```

Filename convention is date-stable: `YYYY-MM-DD-daily-brief.md` (e.g. `2026-06-06-daily-brief.md`).
`Path` carries the space in "Daily Brief" natively. A local write creates the directory if missing.

## 3. Scope decision — rendered narrative only (two artifacts)

The repo has **two** distinct daily-brief artifacts, and Prompt 04 touches only the second:

1. **Deterministic Phase 08A brief** — `daily_brief/output.py` `resolve_brief_path`/`write_brief_output`
   (underscore filename, root `Construction Intelligence/Phase 08A Daily Briefs`). This is an **approved,
   source-linked, indexed, manifest-referenced** generated output: an approved index root in
   `resources/config/phase_08a_obsidian_index_policy.seed.yaml` and asserted in
   `tests/test_phase_09_source_manifest.py`. It **is** imported into the manifest/vector index by design.
   **Left unchanged** — moving it would contradict Prompt 04's own exclusion requirements and disturb
   governed seeds.
2. **Claude-rendered V2 narrative** — `daily_brief/output_receipt.py` + the Claude templates + the
   metadata receipt. **Advisory, not source truth, excluded** from memory/vector/manifest/source-linked
   proof. This is the artifact Prompt 04 relocates.

## 4. Implementation

`daily_brief/output_receipt.py`:

- `RENDERED_VAULT_SUBDIR = Path("Work") / "Daily Brief"`; `RENDERED_NARRATIVE_LOCATION` is derived from
  it (single source of truth — kills D7-style drift).
- `rendered_brief_filename(brief_date)` → `<date>-daily-brief.md`.
- `resolve_rendered_brief_path(brief_date, *, vault_brief_dir=None)` → `<vault>/Work/Daily Brief/<date>-daily-brief.md`
  (vault-governed via `PathPolicy().get_vault_root()`; override accepted).
- `write_rendered_brief(*, brief_date, body, vault_brief_dir=None, apply=False)` → advisory local writer.
  Dry-run computes a content hash and writes nothing; apply creates the dir if missing (reuses
  `output._atomic_write_text` → `mkdir(parents=True, exist_ok=True)`) and writes the body atomically.
  **No SQLite/DB access**; returns metadata only (`written`, `rendered_path_redacted`, `content_hash`,
  `persisted_to_sqlite=False`).
- `build_rendered_brief_receipt` gains self-describing attestations: `imported_to_source_manifest`,
  `imported_to_source_linked_proof`, `persisted_to_sqlite` (all `False`).
- The proof (`build_daily_brief_rendered_output_receipt_proof`, CLI
  `second-brain daily-brief output-receipt-proof`) adds `rendered_path_is_correct` and
  `not_persisted_to_sqlite` checks and folds the new receipt flags into the manifest/source-linked
  exclusion checks (12 checks total; `proof_passed=true`).

Claude templates (`resources/templates/claude_daily_brief_{scheduled_task,manual_run}.md`) pin the
absolute path + filename convention in the Storage Policy section and add "do not persist to SQLite".

## 5. Guardrails preserved

Advisory only; not source truth; excluded from accepted memory / vector index / source manifest /
source-linked proof; import deferred (`import_rendered_brief` fails closed, `IMPORT_ENABLED=False`); no
external writeback; rendered body never persisted to SQLite.

## 6. Verification

`ruff`/`mypy` clean on touched modules; `tests/test_phase_09_daily_brief_output_receipt.py` (new path /
date-stable / dir-creation-with-spaces / metadata-only / exclusion / no-SQLite tests) green;
`tests/test_daily_brief_output.py` + `tests/test_phase_09_source_manifest.py` green (prove the
deterministic Phase 08A writer/governance is undisturbed); `output-receipt-proof --json` →
`proof_passed=true` with all 12 checks. Pre-existing `test_phase_0X_schema_vNN` lifecycle and
`test_phase_08b_data_quality_gates` failures are unrelated (fail identically on clean `HEAD`).
