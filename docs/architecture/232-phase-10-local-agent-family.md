# 232 — Phase 10 Local-Agent Family

Status: experimental (branch `experiment/local-agent-family-proof`). Scope: a coherent,
local-only, review-gated **family of agents** layered on the existing Phase 10A substrate.
Authoritative truth is repo code + tests + the evidence bundle at
`docs/evidence/phase-10-local-agent-family/`.

## Purpose

Turn the existing Phase 10A read/extract substrate into working, source-linked, advisory
agent workflows that converge on a single reviewable surface — without violating any
no-raw / no-writeback / dry-run-first guardrail.

## Agents (this family)

| Agent | Surface | Determinism | Reads | Writes (apply-only, capped) |
|-------|---------|-------------|-------|------------------------------|
| Email extraction | `second-brain extract-packets` | model-assisted (mistral-nemo) | `email_thread_raw_context` | `task_candidates` / `commitment_candidates` + `candidate_source_refs` |
| Acceptance promotion | `phase-10 review-candidate --promote` | deterministic | candidate rows | `accepted_tasks` / `accepted_commitments` |
| Follow-up watch | `follow-up-watch scan` | deterministic, no-clock | `accepted_*` + `candidate_source_refs` | `follow_up_watch_items` / `follow_up_status_events` |
| Procore digest | `procore-digest build` | deterministic-first (optional synth) | `procore_action_signals` + text-intelligence read models | `daily_brief_action_candidates` (section `procore`) |
| Daily-brief synthesis | `daily-brief synthesize-candidates` | deterministic | `accepted_*` + `follow_up_watch_items` + `daily_brief_action_candidates` | `daily_brief_action_candidates` (sections `actions`/`waiting`/`follow_up`) |

All five are registered in `resources/config/phase_08a_agent_registry.seed.yaml` (12 agents
total: 9 required Phase-08A + 3 family entries; the extraction front-end reuses the existing
substrate). `second-brain agents status` validates the registry/tool policy (0 violations).

## Data flow (convergence)

```
email_thread_raw_context ─ extract ─▶ task/commitment candidates ─ review --promote ─▶ accepted_*
                                                                                   │
procore_action_signals ─ procore-digest ─▶ daily_brief_action_candidates(procore)  ├─ follow-up-watch ─▶ follow_up_watch_items
                                                                                   ▼
                          daily-brief synthesize-candidates ──▶ daily_brief_action_candidates(actions/waiting/follow_up)
                                                                                   ▼
                                                    unified, source-linked, reviewable brief candidates
```

`daily_brief_action_candidates` is the **convergence table** — the email family and the
Procore family both feed it, and the synthesis layer presents a unified brief by section.

## Key seams / reuse

- The Procore digest **composes** existing redacted read models (`build_operational_digest`,
  `build_overdue_queue`, `list_procore_action_signals`, `get_procore_text_intelligence`,
  `_dimensions_for`) — it does not reimplement Procore logic. Auxiliary-read-model failures are
  guarded so the deterministic core always returns.
- New store writers (`insert_accepted_*`, `upsert_follow_up_watch_item`,
  `insert_follow_up_status_event`, `insert_daily_brief_action_candidate`) all **omit** the 13
  `_P10_GUARDS` columns so `DEFAULT 0` / `CHECK(=0)` holds — the structural no-raw/no-writeback
  invariant. Inserts are idempotent on deterministic ids.
- No-clock convention: classifiers/builders take `now_utc`; the CLI stamps it once (`--as-of`).

## Guardrails (enforced in code + tests + DB)

Dry-run default; `--apply` fail-closed without `--max-persist`; max-persist caps actual writes;
source-ref gate (no source refs → no persist); redaction (Procore digest never emits
`metadata_json` / `encrypted_full_text_ref` / `text_hash` / free-text titles); optional Procore
synthesis is fed only already-redacted aggregates, is in-memory (never persisted), and fails
closed. No Microsoft 365 / Procore / external writeback; no cloud LLM; state stays local.

## Dispositions (families not implemented this run, evidence-based)

- **Calendar meeting-prep**: data present (Dev `calendar_event_raw_content`=500) but HTML-only
  bodies, no `project_key`/`source_ref_hash`, join-urls to redact → needs a normalization slice
  before it is source-stable. Deferred (next strong candidate).
- **MCP packet builder / Obsidian workflows**: infra exists, tables empty
  (`claude_context_packets`=0, `obsidian_note_index`=0) → build-on-demand, no blocker but lower ROI now.
- **File/document enrichment**: data-blocked (`files`=0, no `extracted_text` table populated).
- **Inbox classification / entity normalization / relationship engine**: detectors/extractors
  exist; deterministic relationship scoring already shipped (`relationship_scoring.py`); no
  high-ROI agent gap this run.
- **Review/API/dashboard**: CLI-only by design; the review surface is the CLI + the unified
  `daily_brief_action_candidates`. No web surface added.

See `docs/evidence/phase-10-local-agent-family/README.md` for command outputs + guardrail proof.
