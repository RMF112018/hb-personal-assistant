# Phase 08A — Daily Brief Context Builder (daily_brief_agent) + Review Triage Agent (review_triage_agent) Proof (Prompt 11)

Builds the bounded, source-linked daily-brief **context** package (attention / meeting /
project / warning / review-required cards + a structured delivery-handoff input) from the
Retrieval Broker + Research Packet, and the **review-load status** summary grouped by tier,
source, project, and urgency. Deterministic, read-only, metadata-only persistence; no model
call, no HTML, no notifications. Proofs run against temporary SQLite DBs.

## Repo-truth preflight

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` (pre-commit) | `03bfadb` (Prompt 10) |
| Package-cited baseline | `c2656e1c` — does **not** match local repo; repo truth governs (same posture as Prompts 06–10) |
| `schema_version` | 26 (unchanged — no migration) |
| `contract_table_count` | 141 (unchanged) |
| `live_table_count` | 137 |
| Tables reused | `daily_brief_runs`, `daily_brief_source_refs` (V24) — already shipped; no schema change |

## Files changed

Created:
- `src/hb_assistant/construction/second_brain/daily_brief/{__init__,models,policy,triage,context,store}.py`
- `resources/config/phase_08a_daily_brief_policy.seed.yaml`
- `src/hb_assistant/resources/json/daily_brief_contract.json`
- `tests/test_daily_brief_policy.py`, `tests/test_daily_brief_context.py`,
  `tests/test_review_triage.py`, `tests/test_second_brain_daily_brief_cli.py`
- `docs/architecture/67-phase-08a-daily-brief-context-and-review-triage.md`
- `docs/evidence/construction-intelligence-phase-08a-second-brain-runtime/`
  `daily-brief-context-builder-proof.json`, `review-triage-agent-proof.json`, this file

Modified:
- `src/hb_assistant/cli/second_brain.py` — `daily-brief` subgroup (`build`, `triage`)
- `src/hb_assistant/construction/second_brain/__init__.py` — daily_brief re-exports
- `src/hb_assistant/construction/second_brain/contracts.py` — register `daily_brief_contract`
- `tests/test_phase_08a_contracts.py` — `daily_brief_contract` in `_REQUIRED_KEYS`

## Validation commands and results

| Command | Result |
| --- | --- |
| `python -m compileall -q src` | exit 0 |
| `ruff check .` | All checks passed |
| `mypy src` | Success: no issues in 236 source files (benign pre-existing unused-override note) |
| `pytest` daily-brief + contracts files | all passed |
| `pytest -m "not live and not integration and not manual"` | exit 0 (full suite green) |
| `construction-agent validate --json` | `{total:4, passed:4, ok:true}` |
| `data-quality table-inventory --json` | `schema_version=26`, `contract_table_count=141` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |
| `second-brain daily-brief build --date 2026-06-02 --json` | exit 0; `output_format=structured_data` |
| `second-brain daily-brief triage --json` | exit 0; review load grouped |
| `second-brain daily-brief build --mode bogus` | exit 2 (`invalid_mode`) |

## Evidence proofs

- `daily-brief-context-builder-proof.json` → `proof_passed: true`: context carries
  `source_coverage` + `review_tier_counts`; all five card kinds exercised (attention=2,
  project=1, warning=1, review_required=1; meeting=0 degrades gracefully with a
  `no_read_model:meeting_prep_brief_sections` warning); delivery handoff is
  `structured_data`, `notification_emitted=false`, source-linked per line; run persisted to
  `daily_brief_runs` with all guard columns 0 and `daily_brief_source_refs` count matching
  `source_ref_count`; empty DB → `status=blocked` / `degradation_mode=blocked` /
  `context_quality_class=insufficient`; no raw content in any output.
- `review-triage-agent-proof.json` → `proof_passed: true`: review load grouped by tier,
  source family, project, and urgency; Tier-3 surfaced as mandatory review
  (`tier_3_count>=1`, `mandatory_review_count>=1`); empty DB → zero review load; no raw
  content.

## Guardrail proof points

- **Context from research packet + broker**: `build_daily_brief_context` retrieves once via
  `RetrievalBroker`, assesses via `build_research_packet_from_envelope` (reused envelope),
  and never calls a model.
- **No HTML / no notifications**: `DeliveryHandoffInput.output_format` is the literal
  `"structured_data"`; a field validator rejects `notification_emitted=True`. No output file
  is rendered (`daily_brief_runs.output_path_*` stay NULL).
- **Source-linked + no raw content**: every card / handoff line / context source-ref is a
  redacted `{source_family, source_ref, record_type, review_tier}`; field validators reject
  any forbidden raw reference field; output scanned for forbidden tokens.
- **Tier-3 never a final conclusion**: tier-3 items become `ReviewRequiredCard`s and feed
  the `file_review_queue` handoff section; triage counts them as mandatory review.
- **Insufficient context degrades, never overstates**: empty/blocked context yields a
  blocked brief with degraded handoff — no fabricated cards.
- **Metadata-only persistence**: `write_daily_brief_run` leaves all `*_persisted` /
  `external_writeback_performed` guard columns at 0 (DB CHECK-enforced).
- **Read-only / dry-run default**: `--mode` defaults to `dry_run`; `--no-emit-receipt`
  performs zero local writes; external systems untouched.

## Reconciliations / known limitations

- **No new schema.** V26 already ships `daily_brief_runs` + `daily_brief_source_refs`; this
  prompt reuses them. Schema head stays V26 / 141 contract tables.
- **Triage has no dedicated persistence table** (none exists in V26). The Review Triage
  Agent is a read-only status summary (consistent with its `review_triage`/`status` tool
  groups); its registry `output_contract` is the existing `review_tier_contract`, reused
  rather than duplicated.
- **Two retrieval families still lack readers** (`meeting_prep_brief_sections`,
  `review_controlled_correspondence_context`): meeting cards degrade to empty with a
  surfaced coverage warning.
- **Output Evaluation Agent (A05) still deferred**: the brief carries computed
  review-tier / degradation signals; no `second_brain_evaluation_runs` writer is added here.
- **No HTML/notification rendering**: out of scope by design — the brief is a context /
  delivery-handoff input package only.

## Next prompt readiness

- Downstream delivery / Obsidian-brief rendering can consume `DeliveryHandoffInput`
  (structured, source-linked) without further context work.
- Schema is final at V26 / 141 tables; the Prompt 06–10 proofs remain unchanged.
- An 08A no-writeback proof arm covering the daily-brief tables and an A05 evaluation writer
  remain owned by later prompts.
