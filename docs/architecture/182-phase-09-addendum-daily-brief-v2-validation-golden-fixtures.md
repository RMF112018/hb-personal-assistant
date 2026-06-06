# 182 — Phase 09 Addendum (Daily Brief V2): Validation & Golden Fixtures

**Status:** Adds executive-utility quality validation + three golden fixtures and a `v2-proof` surface.
**Schema:** unchanged (V39; no migration; no persistence to trusted stores).
**Version:** 1.4.0-phase-09-addendum-v2 (package: Daily Brief V2 Executive Utility Hardening, Prompt 05).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-addendum-daily-brief-v2/daily-brief-v2-quality-proof.{json,md}`
and `daily-brief-v2-golden-{full-detail,detail-unavailable,rejected-internal}.md`;
`docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/daily-brief-rendered-quality-proof.{json,md}`.
**Builds on:** records 178–181 (V2 packet, enrichment, rendering template, output path/receipt).

---

## 1. Objective

Enforce the executive-utility standard for the rendered V2 brief: a construction executive can read it
in under three minutes and understand yesterday / today / next 7 days / needs attention / focus, with
no internal proof/governance commentary, no count-only tables passed off as actionable detail, and no
raw values, final determinations, or source-system writeback claims.

## 2. Validator (21 checks)

`daily_brief/rendered_quality.py` `validate_rendered_brief(packet, rendered_md)` (the `packet` arg is
accepted for signature stability but unused — the V2 brief is validated on its own) grew from 16 to 21
checks. The five new checks (Prompt 05):

- `brief_length_within_max` — `len(md) <= _MAX_BRIEF_CHARS` (8000; the configured max).
- `agenda_today_or_none` — the Today section is non-empty and carries a table/bullet OR states "no
  calendar items / no meetings / nothing scheduled / none" (`_section_has_rows_or_none`).
- `next_7_days_deadlines_or_none` — same shape on Next 7 Days ("no deadline / nothing due / none").
- `focus_count_in_range_or_none` — 3–5 numbered focus items OR a "no focus items" statement.
- `attention_counts_backed_or_unavailable` — generalizes the schedule count-backing rule to
  RFI/submittal/punch/procurement/deadline: a bare count line (not a table row) must be backed by a
  table or a "detail unavailable" notice in its section, else fail.

The existing 16 structural/forbidden-content checks (required sections, single advisory disclaimer,
no provenance/guardrail/coverage/source-family/proof-path/generated-utc/dry-run/follow-up/JSON,
schedule count-backing, no final determinations, no source-system writeback, no raw-shaped values via
`_assert_no_raw`) are unchanged.

## 3. Golden fixtures + `v2-proof`

`build_daily_brief_v2_quality_proof` validates three module-constant fixtures and is fail-closed:

- **A — full detail** (`daily-brief-v2-golden-full-detail.md`): record-level Today/Next-7-Days/Needs-
  Attention tables + 3–5 focus items → passes every check.
- **B — detail unavailable** (`daily-brief-v2-golden-detail-unavailable.md`): "No calendar items
  present.", "No deadlines in the next 7 days.", "Open RFIs: 5 — detail unavailable …", "No focus
  items at this time." → passes (exercises the none / detail-unavailable branches; no count-only
  passed off as actionable).
- **C — rejected internal** (`daily-brief-v2-golden-rejected-internal.md`): provenance table, guardrail
  matrix, source-coverage wall, and "we approve payment" → rejected.

`proof_passed = A.passed and B.passed and not C.passed`. The committed rejected fixture carries **no**
real URLs/tokens/emails (so the evidence no-raw gate passes); raw-shaped-value rejection is verified
with a synthetic in-memory token in tests, never persisted.

## 4. CLI

- `second-brain daily-brief v2-proof --json` — runs the golden-fixture quality proof.
- `second-brain daily-brief rendered-proof --version v1|v2` — v1 (default) keeps the existing
  fixture + tampered-variant proof; v2 runs the golden-fixture quality proof. File validation
  (`--packet`/`--rendered`) uses the enhanced validator regardless of version.
- `second-brain daily-brief output-receipt-proof --version v1|v2` — both validate the receipt, which
  is V2 by construction (record 181). Invalid `--version` → exit 2.

## 5. Guardrails

Review-only; rendered text is never imported into accepted memory / vector index / source manifest /
source-linked proof. Proofs are metadata-only and no-raw-gated.

## 6. Verification

`ruff`/`mypy` clean; `tests/test_phase_09_daily_brief_rendered_quality.py` (extended),
`tests/test_phase_09_daily_brief_v2_quality.py` (new), and `tests/test_second_brain_daily_brief_cli.py`
(v2 cases) green; daily-brief + MCP-handoff suites green; `v2-proof --json` / `rendered-proof
--version v2 --json` / `output-receipt-proof --version v2 --json` → `proof_passed=true`. Pre-existing
`test_phase_0X_schema_vNN` / `test_phase_08b_data_quality_gates` failures are unrelated.
