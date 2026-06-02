# 01 — Phase 07D Gap Audit (re-classified against verified repo truth)

**Audit-only.** This file reproduces the gap inventory from the Phase 08A package
(`03_PHASE_07D_COMPLETION_AUDIT.md`) and **re-verdicts each gap against live repo truth at HEAD
`41d896e…`**, captured in `00-repo-truth-rebaseline.md`. No code, schema, CLI, README, or matrix
files were edited; identified fixes are **routed** to their owning prompts, not applied here.

Verdict legend: **Confirmed** (repo matches the package claim) · **Adjusted** (true but
re-scoped/added detail) · **Refuted** (package claim not supported by repo).

## Gap table

| ID | Gap | Verdict | Repo citation | Severity | Routing |
|---|---|---|---|---:|---|
| G-07D-01 | README/status still frames 07D as `In Progress (Prompts 00–13)`; no repo-truth 07D closeout / 08A handoff evidence file exists. | **Confirmed** | `README.md:23` — "Phase 07D (Cross-Source Relationship & Meeting Prep) — **In Progress (Prompts 00–13)**." No `…-second-brain-runtime/` evidence existed before this audit. | High | ✅ **RESOLVED (08A Prompt 01)** — `README.md:23` relabeled **Closed (Prompts 00–14)**; `phase-07d-final-closeout-and-08a-handoff.md` created. |
| G-07D-02 | `phase_07d_validation_matrix.json` references `data-quality phase-07d-no-writeback-proof`, but the implemented command is `data-quality no-writeback-proof` with a 07D arm. | **Confirmed** | `src/hb_assistant/resources/json/phase_07d_validation_matrix.json` (commands[] line ~12) lists `…data-quality phase-07d-no-writeback-proof --json`; `data-quality --help` shows **no** such subcommand. `docs/architecture/55-…md` & `56-…md` acknowledge it is "satisfied by extension" of `no-writeback-proof`. | High | ✅ **RESOLVED (08A Prompt 01)** — added real read-only CLI alias `data-quality phase-07d-no-writeback-proof` delegating to `build_data_quality_no_writeback_proof`; matrix now resolves. CliRunner test added. |
| G-07D-03 | Relationship state split across `confidence_class`, `review_required`, `sensitive_high_impact`, `promotion_status`; no unified retrieval-facing state label. | **Confirmed** | 07D relationship modules present (`no-writeback-proof` `scanned_modules_07d` → `relationships/cross_source_substrate.py`, `contracts.py`). | Medium | **Inside 08A** — retrieval exposes a normalized relationship-state label; preserve original fields. No schema rewrite. |
| G-07D-04 | Cross-source Obsidian apply never run against the real vault; only dry-run + temp-vault tests. | **Confirmed** | `cross-source obsidian` surface present; `phase-07d-gates` ok; package `03_…` states apply-to-real-vault was not performed. | Medium | **Inside 08A** — Obsidian indexing supports dry-run preview, applied output, and explicit operator approval before any vault write. |
| G-07D-05 | Meeting-prep briefs materialized before issue/risk/aging builders; aging/risk sections may be deferred placeholders. | **Confirmed** | `meeting_prep/brief_builder.py` and the later `issue_history` / `risk_digest` / `aging_exposure` builders are all in `scanned_modules_07d` (built in separate prompts per commit history). | Medium | ✅ **RESOLVED (08A Prompt 01)** — decision recorded: **defer + document, no rebuild**. Meeting-prep placeholders are honest/intentional; 08A context builder consumes issue/risk/aging read models directly with warnings. See `phase-07d-final-closeout-and-08a-handoff.md`. |
| G-07D-06 | Source-system record-map backfill counted as no-op while the map was empty; canonical identity/source-map completeness not guaranteed. | **Confirmed** | `table-inventory` shows `operational_empty_blocking` = 9 and `in_contract_not_in_db` = 4 `procore_sync_*` tables; `source-record-map` is a present-but-unpopulated surface. | Medium | **Inside 08A** — query tools & retrieval policy must surface source-coverage and stale/unknown warnings. |
| G-07D-07 | mypy/ruff "green" overstated; config excludes packages and globally ignores `hb_assistant.*` errors. | **Confirmed** | `mypy src` → `Success … 190 source files` **but** `pyproject.toml` has `[[tool.mypy.overrides]]` global `hb_assistant.*` ignore + ruff `extend-exclude`/`per-file-ignores`; mypy also emitted `unused section(s): hb_assistant.retrieval.context`. | Medium | **Inside 08A validation discipline** — strict checks for new 08A modules; report inherited global limitation honestly. |
| **G-07D-08** *(new)* | `tests/test_cross_source_obsidian.py::test_no_raw_content_in_notes_and_report` is intermittently flaky: the `_LEAK` guard regex's case-insensitive `eyJ` JWT heuristic false-positive-matches a 3-char substring under rare cross-test state contamination. | **New finding** | Failed once in a full run (`match='eyj'`); passes 7/7 in isolation; production render path reproduced 60× in-process + 81 fixed `PYTHONHASHSEED` = 0 matches; `no-writeback-proof` green; guard columns all 0. Detail in `00-repo-truth-rebaseline.md` §Test-suite observations. | Medium | ✅ **RESOLVED (08A Prompt 01)** — tightened the `eyJ` alternative to `eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}` across the ten 07D test files sharing the literal (all `_LEAK` uses are negative assertions; no production redaction change). Suite green 2227. |
| G-08A-01 | No second-brain runtime exists. | **Confirmed** | No `second-brain` Typer group (`hb-assistant --help` / CLI inspection). | High | **08A Prompts 02–16**. |
| G-08A-02 | No LlamaIndex / Anthropic dependencies or config surface. | **Confirmed** | Not present in deps; no adapter module. | High | **Prompt 03** — deps/config/adapter boundary with mock-first tests. |
| G-08A-03 | Root `brief` command is a stub; may collide with 08A daily-brief expectations. | **Confirmed** | `brief` is a deliberate "not implemented" stub (per repo CLI conventions in `CLAUDE.md`). | Medium | **Inside 08A** — canonical commands under `second-brain brief …`; optionally bridge root `brief` later. |

## Must-fix BEFORE Phase 08A runtime work — ✅ COMPLETED (08A Prompt 01)

1. ✅ **G-07D-02** — aliased the 07D no-writeback validation command (`phase-07d-no-writeback-proof`
   now resolves to a real CLI surface delegating to the canonical proof builder).
2. ✅ **G-07D-01** — produced the repo-truth 07D closeout + 08A handoff
   (`phase-07d-final-closeout-and-08a-handoff.md`); `README.md` relabeled **Closed (Prompts 00–14)**.
3. ✅ Re-ran 07D gates + both no-writeback proofs locally — all exit 0, `proof_passed=true`.
4. ✅ **G-07D-05** meeting-prep decision recorded: defer + document, no rebuild (08A context builder
   consumes issue/risk/aging directly with warnings).
5. ✅ **G-07D-08** test-isolation flake fixed (regex tightened across the ten 07D test files).

All blocking 07D drift is cleared; Phase 07D is closed and Phase 08A may proceed. Remaining rows
(G-07D-03/04/06/07, G-08A-01/02/03) are Phase 08A build work.

## Implement INSIDE Phase 08A

Normalized retrieval-facing relationship-state label (G-07D-03); approved Obsidian index manifest +
indexing boundaries (G-07D-04); read-only SQLite query tools; context budget, redaction, source
references, review status, stale/unknown + coverage warnings (G-07D-06); model adapter + mock/live
split (G-08A-02); memory proposal/review model; daily-brief context builder + Obsidian writer
(G-08A-01/03); strict checks for new 08A modules (G-07D-07).

## Exit-criteria truthfulness

**As audited (08A Prompt 00, HEAD `41d896e…`):** repo truth did **not** support an unqualified
"Phase 07D closed" statement — README said "In Progress", the validation matrix pointed at a missing
command, and no closeout/handoff evidence existed.

**After remediation (08A Prompt 01):** all three blockers are cleared — README relabeled
**Closed (Prompts 00–14)**, the matrix command resolves via the new `phase-07d-no-writeback-proof`
alias, and `phase-07d-final-closeout-and-08a-handoff.md` exists. With the deterministic suite green
(2227), gates `ok`, and both no-writeback proofs `proof_passed=true` at schema V25, **Phase 07D is
closed and Phase 08A runtime work may proceed** from this baseline.

## Per-gap guardrail line

Every row above carries a source reference (repo path/line or CLI output), a severity, an explicit
classification, and a review/routing status. All findings are **advisory** and **review-required**
until acted on by their owning prompt; none constitutes a legal/contractual/financial/schedule
determination. No raw content, tokens, URLs, or secrets are present in this evidence. Coverage
warning: this audit reflects local HEAD `41d896e…` on 2026-06-02; re-verify before relying on it if
the branch moves.
