# Phase 10A — Taxonomy / disposition cleanup + Qwen-summary readiness (sanitized, counts only)

Code/test/evidence phase + a controlled in-place re-render of the existing 25 Work cards. NO broad
indexing, NO Qwen/Ollama call, NO summaries generated, runtime automation frozen.

- branch: `feat/obsidian-phase10a-taxonomy-qwen-readiness-20260630T212854Z`
- origin/main commit: `1225de69` (Phase 9 merged first as a prerequisite: PR #232)
- runtime freeze check (ACTUAL runtime config, read-only): **pass** — watch/auto-card/auto-summary/
  auto-refresh = false; source_card_generation / writes / vault_markdown_write = true. Runtime JSON
  not mutated.
- pre-change DB: generated 25 / not_generated 67 / stale 0; work generated 25; Work md 26; queue 0/0.

## Taxonomy / disposition fixes
- **DWG/CAD → drawing**: `.dwg/.dxf/.dwf/.rvt/.rfa/.skp/.nwd/.nwc/.ifc` classify as `drawing`
  (CAD ext wins over a "schedule" keyword, e.g. M301 Mechanical Schedule.dwg → drawing). Binary →
  extraction-unsupported + `needs_review`; Source Basis states no OCR/CAD parsing occurred.
- **Schedule precedence**: native `.xer/.mpp/.mpx` → schedule; PDFs need a STRONG schedule signal
  (construction/baseline/project schedule, schedule update/narrative, lookahead, critical path, CPM,
  gantt, primavera, P6, glued "ConstructionSchedule"). Bare "Schedule Discussion/Question" → NOT
  schedule.
- **Blank submittal covers**: a submittal cover/transmittal with no submittal number/spec/package →
  `template_form` (metadata_only); real submittals (number/spec/package) stay `submittal` (high).
- **Label-gated amounts**: for bid_package/scope_of_work/subcontract/contract/purchase_order/
  change_order/PCO/pay_application/cost_report/project_controls, an amount is extracted ONLY next to a
  strong label (Contract/PO/Change Order/Application Amount, Total Bid/Amount, Schedule of Values
  Total, Retainage, Allowance, Alternate, Contract Sum, Grand Total, …). Stray `$1`/`$42`/bond/
  insurance/phone values are suppressed; Source Basis notes the suppression when a `$` was present.
  Labeled CO/PO/pay-app/cost-report amounts still extract. (Added `scope_of_work` classification so
  SOW exhibits are gated; it is high-value.)
- **Master cost-code / reference demotion**: master/standard cost-code & chart-of-accounts files →
  `reference_document` (metadata_only, needs_review); Source Basis: "reference metadata, NOT a project
  cost instrument". `.xls/.xlsb` added to the spreadsheet + metadata-only handling. Project-specific
  cost reports (incl. cost-to-complete) stay `cost_report` (high).
- **Generic-spreadsheet restraint**: generic/communications-matrix/coordination-matrix workbooks stay
  metadata_only (never high).
- **Internal-consistency guard**: a generic/reference workbook is NEVER path-signal-promoted to
  `auto_card_high` — a card that reports "no high-value workbook class" cannot be high.

## Qwen-summary readiness
- Advisory Summary now carries exactly one `hb-local-summary` block; deterministic cards emit
  `status="pending"` naming the model target.
- model target: `qwen2.5:14b`.
- append contract: pure `replace_local_summary_block(...)` helper replaces only the block interior
  (flips status→generated, stamps model/time) and leaves frontmatter / Key Facts / Source Basis /
  Follow-Up and the canonical 11-section order untouched. No Ollama/Qwen call in this phase.
- advisory/deterministic separation: the renderer never fabricates advisory content; "not
  authoritative" only labels a real (generated) advisory.
- card_version: **phase10a-v1**.

## Controlled production re-render (Phase 9 tool, DB-only)
- re-verified the tool is DB-only: renders from stored metadata, reads no external source file, no
  scan/enqueue/drain, no Ollama, backups under local-sensitive only.
- selected 25, staged 25, staged-validated 25/25, overwritten 25, created 0, deleted 0, queue delta 0.
- renderer input source: stored DB metadata; external source files read 0; cloud download: no.
- DB mutations: 0 (generated_at preserved; re-render reflected via card `updated_at`).
- post-apply: generated 25 / not_generated 67 / stale 0; work generated 25; Work md 26; Home/Shared 1
  each; queue 0/0; backend not listening.
- production card quality: 25/25 pass — canonical 11 sections in order, no old sections, card_version
  phase10a-v1, exactly one hb-local-summary block each, no invented relationships.

## Tests / lint
- new `test_obsidian_source_taxonomy_phase10a.py`: 46 passed (incl. no-source-read render proof +
  replace_local_summary_block contract).
- focused obsidian source-card suite (taxonomy/quality/notes/value/spreadsheet/rerender/first-indexing
  apply+dryrun/domain-routing/skip-codes/self-index/work-home-seed/summaries/auto-generate/pm-grade/
  bid/analyzer): 227 passed.
- slow suites (watch_ownership + mcp_backend): 31 passed (0 failures).
- `py_compile`: OK. `ruff check` (changed source modules + tests): clean.

## Confirmations
- no Qwen/Ollama call · no advisory summaries generated · no broad source indexing · no queue ops
  (queue 0/0 before+after, delta 0) · no source-root scan · no backend started · runtime config
  unchanged/frozen · quarantine untouched · external roots untouched (no source file read; no cloud
  download) · backups/staged cards/details kept local-sensitive + untracked · sensitive evidence not
  committed.

## Recommended next phase
Phase 10B — implement the authorized `qwen2.5:14b` local-summary appender (Ollama) that replaces only
the hb-local-summary block on a bounded set, with the same freeze/evidence discipline.
