# 06 — Local-Summary Marker Compatibility Proof

## What N8C-1 does
- Adds neutral vocabulary + dual-form predicates (`is_local_summary_begin/end`) in
  `hb_assistant.naming`.
- Wires **dual-READ** into every reader so both `assistant-local-summary` (neutral) and
  `hb-local-summary` (legacy) are recognised: `obsidian_mcp/source_notes.py::replace_local_summary_block`,
  `source_local_summary.py::_strip_local_summary_block` + sanitizer scrub,
  `source_card_repair.py::_summary_block`, and `scripts/obsidian_source_card_append_local_summary.py`
  (`_start_marker_status`, `_eligibility` dual-count).
- **Keeps the emitter on the legacy marker** (`source_notes.LOCAL_SUMMARY_*` alias `naming.LEGACY_*`)
  so new cards are byte-identical to before and all existing tests/assets stay valid.

## ⚠️ Explicit N8C-2 compatibility debt (clarification 5)
The neutral **emit flip is deferred to N8C-2.** It is NOT done in N8C-1 because it is a wide,
cosmetic-only change:
- a second validity-guard matcher hardcodes `hb-local-summary:start/end` in
  `scripts/obsidian_source_card_rerender_existing.py:200-202` (needs dual-count);
- **7 test files (27 literal occurrences)** assert `hb-local-summary` + `.count()==1` on freshly
  rendered cards.

**N8C-2 must:** point the emitter at `naming.LOCAL_SUMMARY_*`; dual-count the rerender guard; update
the ~8 hardcoded-marker tests; add a legacy→neutral migration-on-`replace` test. The dual-READ landed
here makes that flip additive. This debt is also recorded in `17-risk-and-defer-list.md` and the
naming-policy doc §3.

## Verification (`tests/test_obsidian_source_card_local_summary_marker.py`)
- Emitter stays legacy; neutral marker not yet emitted.
- Both marker forms recognised by `replace`/`strip`/`repair`/sanitizer; interior-only swap preserves
  surrounding canonical sections; exactly-one-block invariant held.
- Regression bug found + fixed during implementation: `_eligibility` initially double-counted the
  legacy marker (the re-exported constant aliases the legacy value this slice); fixed to count the
  distinct `naming.LOCAL_SUMMARY_*` + `naming.LEGACY_*` values. All appender/enrich regressions green.
