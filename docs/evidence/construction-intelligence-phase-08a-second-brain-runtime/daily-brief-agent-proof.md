# Phase 08A — Daily Brief Agent (daily_brief_agent) + Output Evaluation Agent (A05) Proof (Prompt 12)

Generate → evaluate → (gated) apply → hand off. The Daily Brief Agent assembles the brief
context (Prompt 11), generates mock-first through the Claude adapter's research-packet gate,
runs the Output Evaluation Agent (A05), and **blocks apply unless evaluation passes** and
the context is not blocked. On apply it writes approved Obsidian output; it always emits a
local-only, source-linked Phase 08B delivery-handoff payload (eligibility flag + data-only
notification summary + HTML render-data). No macOS notification, no HTML, no external
delivery, no raw content. Proofs run against temporary DBs + a temporary vault dir.

## Repo-truth preflight

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` (pre-commit) | `27f2d63` (Prompt 11) |
| Package-cited baseline | `c2656e1c` — does **not** match local repo; repo truth governs |
| `schema_version` | 26 (unchanged — no migration) |
| `contract_table_count` | 141 (unchanged) |
| Tables used | `second_brain_evaluation_runs` (first writer here), `daily_brief_runs` (now records `evaluation_run_id` + `output_path_*`), `daily_brief_source_refs` |

## Files changed

Created:
- `construction/second_brain/synthesis/store.py` — `write_evaluation_run` (A05 persistence)
- `construction/second_brain/daily_brief/generate.py` — `run_daily_brief` + agent/handoff proofs
- `construction/second_brain/daily_brief/output.py` — redacted marker-bounded renderer + safe vault writer
- `tests/test_output_evaluation_agent.py`, `tests/test_daily_brief_agent.py`,
  `tests/test_daily_brief_output.py`, `tests/test_second_brain_daily_brief_generate_cli.py`
- `docs/architecture/68-phase-08a-daily-brief-generation-evaluation-and-delivery-handoff.md`
- evidence: `daily-brief-dry-run.md`, `daily-brief-delivery-handoff-proof.json`,
  `output-evaluation-agent-proof.json`, this file

Modified:
- `synthesis/evaluation.py` (+A05 proof), `synthesis/__init__.py`
- `daily_brief/context.py` (extract `_assemble_daily_brief`), `daily_brief/store.py`
  (extend `write_daily_brief_run` with `evaluation_run_id` + `output_path_*`),
  `daily_brief/models.py` (NotificationSummary, HtmlRenderingData, DeliveryHandoffPayload,
  DailyBriefResult), `daily_brief/__init__.py`, `second_brain/__init__.py`
- `cli/second_brain.py` (`daily-brief generate`),
  `resources/config/phase_08a_daily_brief_policy.seed.yaml` (apply_gate + delivery)

## Validation commands and results

| Command | Result |
| --- | --- |
| `python -m compileall -q src tests` | exit 0 |
| `ruff check .` | All checks passed |
| `mypy src` | Success: 239 source files (benign pre-existing unused-override note) |
| `pytest` Prompt-12 + related files | all passed |
| `pytest -m "not live and not integration and not manual"` | exit 0 (full suite green) |
| `construction-agent validate --json` | `{total:4, passed:4, ok:true}` |
| `data-quality table-inventory --json` | `schema_version=26`, `contract_table_count=141` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |
| `second-brain daily-brief generate --date 2026-06-02 --json` | exit 0 (dry-run; no write) |
| `second-brain daily-brief generate --mode bogus` | exit 2 (`invalid_mode`) |

## Evidence proofs

- `output-evaluation-agent-proof.json` → `proof_passed: true`: a seeded tier-1 brief
  evaluates `passed=true` (score 1.0) and persists to `second_brain_evaluation_runs`
  (row `passed=1`, `review_status=pending_review`, `checklist_total=10`, guard columns 0);
  an empty-DB brief evaluates `passed=false` (`source_references_present=false`).
- `daily-brief-agent-proof.json` (via `build_daily_brief_agent_proof`) → `proof_passed: true`:
  the apply run writes `2026-06-02_daily_brief.md` to the temp vault, links
  `daily_brief_runs.evaluation_run_id` + `output_path_redacted`, mode `apply`, eligible for
  delivery; the empty-DB apply run is **blocked** (`apply_blocked_reason=evaluation_failed`),
  writes no file, persists as `dry_run`, and is not eligible. Guard columns 0; no raw content.
- `daily-brief-delivery-handoff-proof.json` → `proof_passed: true`: handoff `phase=08B`,
  `local_only=true`, `external_delivery_performed=false`, notification `channel=local_only`
  / `emitted=false`, HTML `format=render_data` / `rendered=false`, source-linked refs, no raw.
- `daily-brief-dry-run.md` — rendered redacted, marker-bounded brief content a dry-run would
  hand off (no file written in dry-run).

## Guardrail proof points

- **Requires research packet**: context is assembled via the Prompt-07 packet; a blocked
  packet yields a blocked brief that cannot apply.
- **Evaluation required before apply / apply blocked when evaluation fails**: `apply_allowed`
  requires `evaluation.passed` and `status != blocked`; the empty-DB proof + the
  `test_apply_blocked_when_evaluation_fails` test confirm no output and a `dry_run`-persisted
  row when evaluation fails.
- **Approved output, write only on apply**: dry-run computes the would-be content + hash and
  writes nothing; apply atomically writes a marker-bounded
  (`HB-SECOND-BRAIN-DAILY-BRIEF`) section to
  `<vault>/Work/HB Personal Assistant/12_Daily_Brief/<date>_daily_brief.md` (user text
  outside the markers is preserved). Tests/proofs use a temp vault dir; the real vault is
  never touched by the suite.
- **No raw content**: output is rendered from redacted cards, never from
  `adapter_result.answer`; the adapter result drives evaluation + an in-memory model-call
  receipt only and is never written to disk/DB (live-mode raw-response safety).
- **Handoff local-only + source-linked, no external delivery**: `DeliveryHandoffPayload`
  validator-forces `local_only=True` / `external_delivery_performed=False`; notification
  summary `emitted=False` and HTML render-data `rendered=False` are validator-forced.
- **Metadata-only persistence**: `second_brain_evaluation_runs` + `daily_brief_runs` guard
  columns stay 0 (DB CHECK-enforced).

## Reconciliations / known limitations

- No new schema/contract tables. Output Evaluation reuses `evaluation_criteria_contract`;
  the daily_brief_agent `output_contract` is `agent_result` (no contract file).
- No macOS notification, no HTML rendering — both are structured data payloads only.
- Model-call / agent-run receipts remain in-memory (V27-deferred); not persisted here.
- `meeting_prep_brief_sections` still lacks a reader → meeting cards degrade gracefully.

## Next prompt readiness

- Schema final at V26 / 141 tables; Prompt 06–11 proofs unchanged.
- Phase 08B can consume `DeliveryHandoffPayload` (with `eligible_for_delivery`) to render
  HTML / emit notifications downstream; this prompt deliberately stops at the local handoff.
