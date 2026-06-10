# Priority 4 — Source-Ref Gate & Model-Facing Contract (Prompt 04)

## What changed

- **New** `src/hb_assistant/construction/second_brain/local_ai/source_ref_gate.py`:
  - `gate_model_candidate_context(store, brief_date)` → `(candidates_by_section, report)`. The
    section buckets contain **only** candidates with ≥1 `candidate_source_refs` link; the report
    carries `total_candidates`, `source_linked_candidates`, `coverage`, `executive_total`,
    `executive_source_linked`, `executive_coverage`, `withheld_candidate_ids`,
    `supported_short_ids`, `withhold_synthesis`, and a `verdict`.
  - `drop_unsupported_bullets(bullets, supported_short_ids)` → splits model bullets into
    (supported, dropped) so a bullet may claim a meeting / Procore risk / follow-up / action only if
    it cites a source-linked candidate id.
  - `executive_coverage_ok(report)` → True only at 100% executive coverage (the `success` bar).
  - `EXECUTIVE_SECTIONS = {actions, procore, calendar, follow_up, waiting}`.
- **Wired into** `daily_brief_context_packet.build_daily_brief_context_packet`: the model's
  `candidates_by_section` is now the **gated** set, and a `source_ref_gate` block is added to the
  packet. Also hardened the packet's calendar project labeling to treat every `__…__` sentinel
  (unassigned / needs_review / internal_*) as "Needs Project Review" so the new category sentinels
  don't leak as project keys.
- **Wired into** `daily_brief_llm_synthesis.synthesize_daily_brief`: when candidates exist but none
  are source-linked (`withhold_synthesis`), the model is **never called** — the result is
  `status="blocked"`, `degraded=True`, `degraded_reason="no_source_linked_context"`.

## Contract enforced

- The model only ever sees source-linked deterministic rows.
- Executive/top-priority rows require 100% source-ref coverage for `success` (checked by the
  usefulness gate, Priority 5).
- Missing-ref rows are withheld; all-withheld degrades and skips synthesis (fail-closed).
- Coverage metrics + withhold reasons are available for status JSON (consumed in Priority 5).

## Tests

- `tests/test_phase_10_daily_brief_source_ref_gate.py` — 8 passed (linked included; missing-ref
  withheld; mixed includes only linked; full executive coverage; unsupported bullet dropped;
  all-withheld blocks synthesis; no-candidates does not block; no raw/hashed ref leaks into context).
- `tests/test_phase_10_daily_brief_correction.py` (incl. context-packet + synthesis), 
  `test_phase_10_daily_brief_synthesis.py`, `test_phase_10_mcp_packet_hardening.py` — all green
  (no regression; packet sentinel hardening keeps unassigned accounting correct).
- `ruff check` on changed files: clean.
