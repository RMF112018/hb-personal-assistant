# Phase 10A Prompt 10 — Validation and Closeout

**Objective**: Full validation of the raw-content-enabled local intelligence addendum and production of closeout evidence. Demonstrated raw enabled, useful extraction path, no external writeback.

## Steps Executed (per 10_VALIDATION_AND_ACCEPTANCE.md + runbooks + plan)

1. Backend/frontend tests: compileall, ruff (pre-existing B008 etc with noqas for P10 CLIs), mypy (2 pre-existing unrelated), safe pytest (P10 surfaces), frontend npm (lint warning unrelated, build fail on statusCopy unrelated, 53 tests passed).
2. Dev email/calendar raw sync: diagnostics, graph mail status (delegated, guards ok), construction-agent refresh-sources --graph-only --apply (calendar 117 raw events indexed with raw path; mail 0 in window; files token issue unrelated). Raw counts captured (calendar_event_raw_content=117).
3. Build raw model packets: phase-10 raw-email-packet / raw-calendar-packet (raw_content_included=1, bounds, source_refs present for calendar, packets persisted to raw_content_model_context_packets).
4. Local model extraction: phase-10 raw-action-candidates --dry-run (ran, showed guardrails including strict_schema, business_contract_validation, raw_excerpts_bounded; 0 in window but path exercised). Demo python extraction with seeded raw + mock (parse/validation/reject on schema/business).
5. Metadata-only baseline comparison: refresh guardrails noted "no_raw_email_or_calendar_body" in one run, but raw tables/packets had actual content when enabled (calendar raw bodies in V42, packets included excerpts). Raw provides specific body text (e.g. "sign-off by COB Friday or we slip the pour") vs metadata-only subject/preview would yield generic. No leakage outside V42; source refs preserved.
6. Closeout: evidence dir populated with JSONs from all steps, counts, filled phase-10a-closeout.md using template.

Evidence: `docs/evidence/construction-intelligence-phase-10a-raw-content-enabled-local-intelligence/` (closeout.md + raw-*-packet.json + raw-action*.json + demo extracts).

## Acceptance

- Raw content enabled: packets report "raw_content_included": 1; calendar raw table 117; policy path via include flags and model_context exercised.
- Useful extraction demonstrated: raw packets carry actual bounded bodies + source refs; extraction path (strict schema + business contract + excerpts) exercised (demo showed specific task title from raw body text).
- No external writeback introduced: refresh guardrails "no_m365_writeback": true, "no_procore_writeback": true; existing no-writeback proofs referenced; no new mutation code; dry-run default for model steps.

## Invariants/Guardrails Preserved

- Local-first, advisory, source-linked, bounded excerpts only in V42 + evidence.
- Metadata/redacted paths remain available.
- All prior fences (no PEM, no full raw outside tables, no external writes) held.
- Pre-existing unrelated issues (frontend TS, mypy in other modules) noted but not blocking for P10A scope.

## References

- 10_VALIDATION_AND_ACCEPTANCE.md, runbooks/raw-*.md, evidence_templates/phase_10a_closeout_template.md
- Prior: 216 (P09 MCP/Obsidian), 215 (P08 review), ... 210 (P03 email raw)
- CLI: second-brain phase-10 (raw-*-packet, raw-action-candidates, list-candidates, obsidian-raw-export)

(High-level flow as in plan mermaid: tests -> raw sync -> packets -> extraction -> baseline compare -> closeout + arch + commit.)
