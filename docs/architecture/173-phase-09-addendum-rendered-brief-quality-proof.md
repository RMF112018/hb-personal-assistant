# 173 — Phase 09 Addendum: Rendered Brief Quality & Guardrail Proof

**Status:** New read-only validation surface for Claude-*rendered* daily-brief markdown (review-only).
**Schema:** unchanged (V39; no migration; no persistence). **Version:** 1.3.0-phase-09-addendum (package: Daily Brief / MCP Handoff & Rendering, Prompt 04).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/daily-brief-rendered-quality-proof.{json,md}` + `daily-brief-rendered-quality-fixture.md`.
**Builds on:** record 170 (packet), 171 (MCP tool), 172 (render templates).

---

## 1. Objective

The package cannot control Claude's output, but it can deterministically check rendered brief text that
an operator copies/exports back for review: did the rendering preserve the required sections/warnings,
and did it avoid overclaiming? This is **review-only** — rendered text is never imported into trusted
retrieval/memory/source-of-truth surfaces.

## 2. Validator

`daily_brief/rendered_quality.py` → `validate_rendered_brief(packet, rendered_md)` is a pure function
returning per-check results. Ten checks (conditional ones only fail when applicable to the packet):
`sections_present` (the 7 executive-brief headers), `advisory_notice_present`,
`source_coverage_section_present`, `review_required_warnings_present` (only if the packet has
review-required items), `stale_low_confidence_warnings_present` (only if the packet has them),
`no_final_determinations`, `no_raw_shaped_values`, `no_unsupported_source_families`,
`no_source_system_update_claims`, `coverage_limitations_not_omitted` (only when packet coverage is weak).

Notes:
- Conditional warning checks scan the **body with section headers stripped**, so the header word
  "Stale" in `## Aging / Stale Items` is not mistaken for a preserved warning.
- Determination detection uses a dedicated **affirmative** lexicon (e.g. "approve payment", "we
  approve"), deliberately not the packet's `_reject_final_determination` substring set — a faithful
  brief's Advisory Notice legitimately says "makes no … determinations" and must not be penalized.
- `no_unsupported_source_families` flags any of the 10 canonical family ids
  (`ALLOWLISTED_SOURCE_FAMILIES`) cited in the text but absent from the packet's `families_present`.
- Raw-shaped values are caught by `_assert_no_raw`.

## 3. Proof & CLI

`build_daily_brief_rendered_quality_proof` builds a realistic sample packet over controlled seed inputs
(`packet._seed_proof_db`), validates the bundled safe fixture (`_SAMPLE_RENDERED_BRIEF`, which passes
all ten checks), and runs six tampered variants — missing advisory notice; missing stale warning vs a
stale packet; final-determination language; raw-shaped value; source-system update claim; coverage
omission vs a weak packet — asserting each fails exactly its expected check. It writes the proof JSON+MD
and the fixture markdown. CLI `hb-assistant second-brain daily-brief rendered-proof`: with
`--packet <path> --rendered <path>` it validates operator-supplied files; otherwise it runs the built-in
fixture proof. Exit 0 on pass, 3 on fail.

## 4. Validation

`ruff`/`mypy` clean. `tests/test_phase_09_daily_brief_rendered_quality.py` (9 tests) green: safe brief
passes; missing advisory notice / missing stale (vs stale packet) / final-determination / raw-shaped /
source-system update claim / unsupported family / coverage omission (vs weak packet) each fail; proof
writes artifacts. Both CLI modes verified. The daily-brief + MCP suites stay green; the pre-existing
`test_phase_08d_schema_v37` lifecycle failure is unrelated (fails identically on clean `HEAD`).

## 5. Limitation

Pure read-only validation; no retrieval, writeback, or persistence. Rendered text is review-only and
must never be imported into accepted memory / vector index / source manifest / source-linked proof /
source systems.
