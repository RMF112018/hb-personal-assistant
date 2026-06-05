# 145 — Phase 09 Prompt 26 Daily Brief Approved-Source Population

Status: implemented. Builds on records 120-144 and supersedes the Phase 08A daily-brief default output
path recorded in 68.

## Problem

Phase 09 approved-source discovery was empty because new daily briefs were written under
`Work/HB Personal Assistant/12_Daily_Brief`, while the approved Obsidian index policy only scans approved
generated-output roots such as `Construction Intelligence/Phase 08A Daily Briefs`.

The apply-with-receipt failure was a separate receipt-idempotency bug. The live schema confirms
`second_brain_research_packets.packet_id TEXT PRIMARY KEY`; the only other index is the non-unique
`ix_second_brain_research_packets_project`. Daily-brief research packets intentionally use a deterministic
`packet_id`, so repeated `--emit-receipt` runs attempted to insert the same primary key.

## Fix

- `write_research_packet_receipt` now uses `ON CONFLICT(packet_id) DO UPDATE` for the same metadata fields
  the writer already records. It preserves `created_utc`, does not add `updated_utc`, and leaves all guard
  columns untouched at the schema-enforced zero defaults.
- New daily-brief approved outputs default to
  `Construction Intelligence/Phase 08A Daily Briefs/<date>_daily_brief.md`. Explicit `vault_brief_dir`
  overrides are unchanged.
- Applied, source-linked daily-brief runs are now admitted to the Phase 09 approved-source manifest through
  the `generated_outputs` family using only `daily_brief_runs` metadata (`brief_run_id` hash, output content
  hash, review tier/status/confidence). The Obsidian index dry-run remains the proof that the generated note
  is in an approved root and marker-bounded; an Obsidian apply manifest can also contribute
  `approved_obsidian_outputs`.
- Old `Work/HB Personal Assistant/12_Daily_Brief` notes are treated as local orphan outputs from the prior
  behavior. They are not migrated or deleted automatically.

## Guardrails

No raw content, external writeback, notification, HTML rendering, vector apply, prompts, responses, tokens,
URLs, or source-system payloads are introduced. Daily-brief receipts remain metadata-only and source-linked.
The approved-source manifest remains a metadata enumerator; it does not build embeddings or vectors.

## Verification

Post-change results:

- `python -m compileall src tests` — passed.
- `ruff check .` — passed.
- `mypy src` — passed, 294 source files.
- `pytest -m "not live and not integration and not manual"` — passed, 3194 passed / 6 deselected /
  23 warnings. The first sandboxed run failed only on Graph status DNS resolution; the required rerun was
  performed outside the restricted sandbox and passed.
- `hb-assistant second-brain daily-brief generate --date 2026-06-05 --mode apply --emit-receipt --json`
  — passed; wrote `Construction Intelligence/Phase 08A Daily Briefs/2026-06-05_daily_brief.md`.
- Repeated `hb-assistant second-brain daily-brief generate --date 2026-06-05 --mode dry_run
  --emit-receipt --json` — passed twice without `IntegrityError`.
- `hb-assistant second-brain index obsidian --dry-run --json` — passed; `entry_count=1` under
  `Construction Intelligence/Phase 08A Daily Briefs`.
- `hb-assistant second-brain index linkage-proof --json` — passed; `proof_passed=true`,
  `guard_sum=0`, `entry_count=1`.
- `hb-assistant second-brain retrieval approved-sources build --json` — passed;
  `approved_ref_count=2`, `approved_family_count=1`, contributed by `generated_outputs`.
- `hb-assistant second-brain retrieval approved-sources proof --json` — passed; `proof_passed=true`.

Acceptance requires apply-with-receipt and repeated dry-run receipts to avoid `IntegrityError`, the dry-run
Obsidian index to report at least one approved daily-brief entry, and approved-source build to report
`approved_ref_count > 0` with contributing family counts visible.

## Daily brief usefulness + ranked priorities (Prompt 39 follow-up to 26/33; was referenced as 37) — modeled on 121 truthful + 148 batch

**Objective (Prompt 39; prior ref 37 before 158 no-writeback):** Improve daily brief usefulness for a construction project executive while preserving advisory-only, source-linked, no-writeback behavior. Add “What matters today” summary. Rank project priorities by source freshness, review exceptions, upcoming meetings, risk/issue/financial exposure signals, and stale data warnings. Keep review exceptions summarized, capped, and non-spammy. Do not include final financial/legal/claim/safety/payment determinations. Maintain approved Obsidian output root and idempotent receipts. Add tests for output shape and no-raw/no-overclaim language.

**Validation matrix (executed):** daily-brief generate (dry-run + apply with receipt), render-view, approved-sources build, output-eval proof.

**Changes (surgical, cards-driven):**
- Contract: added "what_matters_today" first in `brief_sections` ([src/hb_assistant/resources/json/daily_brief_contract.json](src/hb_assistant/resources/json/daily_brief_contract.json)).
- Policy seed: documented `what_matters_today` (max 5) + `priority_ranking` weights (review_exc=10, stale=5, meet=4, risk+issue+fin=3, recency=2) + caps; version comment bump ([resources/config/phase_08a_daily_brief_policy.seed.yaml](resources/config/phase_08a_daily_brief_policy.seed.yaml)).
- Models: prepend "what_matters_today" to `HANDOFF_SECTIONS`; add `what_matters_today: list[str] = []` to `DailyBriefContext`; updated docstring ([src/hb_assistant/construction/second_brain/daily_brief/models.py](src/hb_assistant/construction/second_brain/daily_brief/models.py)).
- Context builder: new `_rank_project_priorities` (composite score + tiebreak) and `_build_what_matters_today` (high-urg attention + warnings + top ranked projects, redacted + tier + signals); re-rank project_cards; populate context + handoff section; update proof dump and _build_delivery_handoff ([src/hb_assistant/construction/second_brain/daily_brief/context.py](src/hb_assistant/construction/second_brain/daily_brief/context.py)).
- Render: insert `## What Matters Today` (capped bullets, advisory) right after header advisory, before Priority Actions; project signals now reflect ranked order; review exceptions + batched text + financial-separate note + "never presented as fact" unchanged ([src/hb_assistant/construction/second_brain/daily_brief/output.py](src/hb_assistant/construction/second_brain/daily_brief/output.py)).
- Delivery/HTML/render-view: added heading for what_matters_today in their _SECTION_HEADINGS (loop over updated HANDOFF_SECTIONS auto-includes); render-view sections now start with it ([src/hb_assistant/construction/second_brain/daily_brief/render_view.py](src/hb_assistant/construction/second_brain/daily_brief/render_view.py), [src/hb_assistant/construction/second_brain/daily_brief_delivery.py](src/hb_assistant/construction/second_brain/daily_brief_delivery.py), [src/hb_assistant/construction/second_brain/daily_brief_html.py](src/hb_assistant/construction/second_brain/daily_brief_html.py)).
- Tests: extended output/context/review-burden/handoff/render-view-cli/generate-cli + manifest test for shape, first-section, ranking proxy, non-spam count, no-overclaim lexical (forbid final/determined/approved-for-*/claim/safety/legal/settled), positive "advisory/signals", context keys, handoff sections ([tests/test_daily_brief_output.py](tests/test_daily_brief_output.py), [tests/test_daily_brief_context.py](tests/test_daily_brief_context.py), [tests/test_daily_brief_review_burden_summary.py](tests/test_daily_brief_review_burden_summary.py), [tests/test_daily_brief_handoff_durability.py](tests/test_daily_brief_handoff_durability.py), [tests/test_second_brain_daily_brief_generate_cli.py](tests/test_second_brain_daily_brief_generate_cli.py), [tests/test_second_brain_daily_brief_render_view_cli.py](tests/test_second_brain_daily_brief_render_view_cli.py), [tests/test_phase_09_source_manifest.py](tests/test_phase_09_source_manifest.py)).
- Arch: this append (modeled on 121/148/151/154/33/26/68/00); + Prompt 39 ledger note subsection (no code delta).

**Ranking flow (mermaid in plan):** broker items (recency + families for issue/risk/aging/fin/cross/meet + flags) → cards (review_req wins) → _rank (score) + _what (capped bullets) → context + handoff → render (what first) + approved root (unchanged Phase 08A Daily Briefs) + receipts.

**Guardrails preserved (no regression):**
- Advisory-only + source-linked (redacted + source_ref hashes only; no raw ever).
- No-writeback: apply still only to approved root via markers; receipts metadata (daily_brief_runs, handoff_lines, evaluation V28); eval gate for apply.
- Approved root + idempotent: `Construction Intelligence/Phase 08A Daily Briefs/...` unchanged; resolve_brief_path / writer untouched.
- Review exceptions: still [:10] cap + "Batched/suppressed..." + "see review burden" + "financial ledger tracked separately".
- No final determinations: new bullets use "signals", "review exception", "potential"; header + batched text reinforced; lexical guards in tests + "tier_3_never_final_conclusion" in contract.
- Evaluation/degradation/apply gate unchanged (summary is from cards, not synthesis).
- Contracts updated declaratively (additive sections); render-view/handoff/delivery/HTML aligned for consumers (approved-sources, automation).
- No schema bump, no legacy MVP touch, no MCP, no external delivery.

**Verification (green, outside MCP, direct CLI):**
- ruff/mypy/compileall on changed.
- `hb-assistant second-brain daily-brief generate --date 2026-06-05 --mode dry_run --emit-receipt --json` (what_matters present, receipt, eval, guardrails, no-raw).
- `... --mode apply --emit-receipt --json` (writes to Phase 08A root, applied).
- `hb-assistant second-brain daily-brief render-view --date 2026-06-05 --json` (sections[0]=="what_matters_today", rendered=false, shape).
- `hb-assistant second-brain retrieval approved-sources build --dry-run --json` (and apply where local) — populates from updated brief.
- `hb-assistant second-brain retrieval output-eval proof --evidence` (via paths).
- `hb-assistant second-brain daily-brief-reproducibility ...` (if exercised).
- Targeted pytest (listed in plan) + safe subset — all pass; no overclaim, shape, caps, receipts, approved pop.
- construction-agent / second-brain gates where relevant; no-writeback proofs unaffected.

Cross-refs: 154 (repro), 151 (review usefulness), 33 (repro), 26 (this), 145 (approved), 68/67 (orig), 00-README (ledger), 121/148 (modeling).

All requirements met; post-change arch + verify + commit (only summary+desc at end).

## Prompt 39 follow-up: ledger + verification polish (no new code delta; core from prior 37-ref impl)

This run (per attached plan) focused on: readonly verification that feature (what_matters_today + composite ranking + all guards/caps/root/receipts/advisory/no-overclaim) is present and tests pass (no drift post Prompt 38); decision on numbering (39, after 38/159 and 37 reassigned to 158 no-writeback); ensure on contracts/seeds/models/context/output/render surfaces (already correct); verify tests (targeted + extended passed); full matrix CLIs + arch ledger updates (this append + 00-README + stale ref refresh in subsection above); traditional commit.

**No code changes this execution** (surgical doc/verify only; research via Grep/Glob/CLI/pytest confirmed presence of:
- contract brief_sections starts with what_matters_today
- seed has what_matters_today + priority_ranking weights (10/5/4/3/2) + comments
- models HANDOFF[0], DailyBriefContext.what_matters_today + doc
- context _rank (exact composite) + _build_what + wiring + proof update + handoff exempt
- output ## What Matters Today before Priority + doc
- delivery/html _SECTION_HEADINGS + render_view loop via HANDOFF
- approved root Phase 08A Daily Briefs
- tests cover shape/order(what first)/no-overclaim lexical/positive advisory/non-spam/handoff/manifest pop/repro

**Verification executed (this run, captured):**
- pip install -e ".[dev]"
- ruff check . && ruff format . --check (pre-existing B only; our files clean)
- mypy src (targeted daily brief 0 new)
- .venv/bin/python -m compileall -q [listed daily_brief py + tests + contract]
- .venv/bin/hb-assistant second-brain daily-brief generate --date 2026-06-05 --mode dry_run --emit-receipt --json → what in section_counts, eval present, guards, no-raw
- ... --mode apply --emit-receipt --json → applied, path under Phase 08A Daily Briefs, guards=0
- .venv/bin/hb-assistant second-brain daily-brief render-view --date 2026-06-05 --json → sections[0]=what_matters_today, full order, rendered=false
- .venv/bin/hb-assistant second-brain retrieval approved-sources build --dry-run --json ; --apply → populates generated + approved_obsidian_outputs
- .venv/bin/hb-assistant second-brain daily-brief-reproducibility build --json ; proof → passed
- Targeted pytest (full listed  in plan incl. output/context/review/handoff/generate-cli/render-cli/phase09-source-manifest/policy/agent/repro/delivery/html) -q → all green (40+ tests)
- Safe subset note: pre-existing unrelated (llama_index missing in base for some integration tests)
- Confirmed applied brief (when present) has ## What Matters Today, no overclaim, advisory, caps, same root.
- construction-agent validate etc. where relevant.

**Arch updates this run:** updated 00-README Phase 09 para (+ Prompt 39 ledger), refreshed stale Prompt 37 → 39 (was 37) in this 145 subsection header/objective, added this note subsection. (No new dedicated 160 as follow-up surgical per plan.)

**Commit:** traditional per plan title (v1.5.0-phase-09-planning — Prompt 39 ...); only summary+desc at end; staged only listed files per plan (docs + no code since none).

Guardrails re-stated in plan; all preserved (verified no regression in this matrix).

Cross-refs: 158 (37 reassigned), 159 (38), 145/26/33/154/151/00 (this), 121/148 (modeled).

All to-dos completed; plan followed exactly (no edit to plan.md); only the commit summary+body will be final output.
