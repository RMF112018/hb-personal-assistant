# Phase 8 — Source-card renderer + taxonomy tuning (sanitized, counts only)

Fixture-driven, code/test-only. NO production card generation, NO queue ops, NO scans, NO summaries,
NO backend writes, NO re-enabling frozen flags, NO modification of the 25 existing production cards.

## Preconditions (verified before any change)
- Branch off `origin/main` @ `112ff008`; worktree clean. Port 8000 clear (no backend).
- Frozen runtime flags confirmed false: external_source_watch / source_card_auto_generate /
  source_summary_auto_generate / source_note_auto_refresh. Capability preserved true:
  source_card_generation / writes / vault_markdown_write.
- Live DB read-only check: generated notes = {generated: 25, not_generated: 67}; Work generated = 25;
  stale = 0. Source Notes/Work = 26 Markdown files. Required Phase-6 artifacts present.
- Phase-7 audit script absent on main → SOW Step 10 skipped.

## Code changes (4 modules)
- `config.py`: default unsupported file types extended with internal-app/binary-data extensions
  (`pcp`, `bak`, `ini`, `db`, `dat`). Production runtime JSON NOT touched (remains frozen).
- `source_analyzers.py`:
  - New `template_form` document_type, detected from the FILENAME with HIGH precedence (overrides
    every classified type in `from_detail`). Body text is not scanned for template signals.
  - Tightened deterministic extraction: status only from a labeled field or a discrete filename
    segment (bare-keyword scan removed; dropdown/instruction/example contexts rejected); amount only
    from an explicit `$` value (example/template/placeholder/sample context, `$0.00`, and ranges
    rejected); date only from a filename ISO or a labeled body date (unlabeled body-ISO fallback
    removed). status/amount suppressed entirely for `template_form`.
- `source_value.py`: `template_form` forced to `metadata_only` (never auto-card, never path-signal
  promoted — a template inside a "Change Orders" folder is not promoted); confidence → low.
- `source_notes.py`: `_render_card` rewritten to the canonical 11-section template body in fixed order
  (Source Summary, Why This Matters, PM Review Cues, Key Facts, Related Project, Related People /
  Companies, Related Decisions, Related Meetings, Source Basis, Advisory Summary, Follow-Up).
  - Type-specific deterministic detail (drawing / bid / spreadsheet) folded into Key Facts; the raw
    indexed-text preview, the Overview / Source Reference / File Analysis blocks, and the competing
    top-level *Identity* sections are removed.
  - Deterministic document-type-specific PM guidance registry (`_PM_GUIDANCE`) drives Why / Cues /
    Follow-Up (no empty boilerplate; class-generic fallback for unlisted types).
  - Related sections distinguish DETECTED facts from RESOLVED records ("Detected … ; no record linked
    yet"); no relationship is implied unless one was actually resolved. Referenced-sheet links that
    resolve to an indexed source are surfaced under Key Facts ("linked in index").
  - Strengthened Source Basis (card basis, document type, classification reason, matched filename
    tokens, extension, spreadsheet caveat, template detection, extraction reasons, disposition,
    confidence, source id/sha — no full source path).
  - Advisory Summary is one clearly-labelled section, or an honest "No advisory summary (deterministic
    card; summaries disabled)." Never fabricated.
  - `card_version` bumped to `phase8-v1` (new cards only). `template_form` added to ambiguous types →
    `needs_review`. Orphaned helpers removed.

## Tests
- NEW `tests/test_obsidian_source_card_quality_regression.py`: 16 synthetic tests — 11-section order,
  template-form demotion/needs-review, status/amount suppression on templates, schedule stays
  schedule, drawing extraction-unsupported, pcp/internal-app unsupported, RFI closed-from-filename,
  PO status only-when-explicit, dropdown/zero/example/range rejection, filename/labeled date only,
  spreadsheet promotion-requires-evidence, meaningful Source Basis, doc-type-specific Follow-Up,
  detected-not-resolved Related sections.
- Updated existing suites for the new renderer / tightened extraction: source_notes, source_analyzer
  (File-Analysis block removed; `_prompt_for` tests retained), cards_pm_grade, spreadsheet_card,
  bid_package_analyzer, taxonomy_pm, auto_generate, summaries.
- Result: the focused source-card test set passes (174 in the combined run; new regression file = 16);
  the bounded first-indexing-apply and domain-routing suites pass UNCHANGED. `ruff check` clean on all
  changed files (no `ruff format` whole-file churn). `py_compile` OK for the 4 modules + 2 scripts.

## Safety / scope confirmations
- No production cards generated or modified; live DB read-only (counts above unchanged by this work).
- Runtime config remains frozen and untouched; no backend write session started.
- Diff scope = the 4 modules + 9 test files + this count-only evidence. A test run had refreshed two
  unrelated phase-07a evidence artifacts (timestamp/sha only); they were reverted out of scope.
- No denylist token introduced; the pre-existing synthetic `QUARANTINED` fixture line in the
  apply test was not touched (stays out of this diff).
