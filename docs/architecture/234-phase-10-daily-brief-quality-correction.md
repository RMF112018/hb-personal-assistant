# 234 — Phase 10 Daily Brief Quality Correction (local-model synthesis + output routing)

Corrective checkpoint after the first scheduled Phase 10 daily run produced a low-value brief in the
wrong vault folder. Two defects, both fixed here:

1. **Output routing.** The scheduled daily-run wrote to
   `Construction Intelligence/Phase 08A Daily Briefs/` because the launchd job passed no
   `--vault-brief-dir`, so `run_daily_local_agent` fell through to the shared
   `daily_brief.output.resolve_brief_path` default (the Phase 08A folder).
2. **Brief quality.** The brief was a deterministic dump of candidate rows (flat `Calendar Prep`,
   `project:__unassigned__` everywhere, raw `Related Context` rows, no executive summary, no meeting
   prep) — no local-model synthesis.

## Design

### Output routing (scheduled run only — surgical)

The Phase 10 scheduled daily-run now routes to the governed folder declared by
`phase_10_obsidian_vault_policy.seed.yaml` (`target_daily_brief_folder: "Work/Daily Brief"`):

- `local_ai/vault_brief_policy.py` — single source of truth: `governed_brief_dir()` (policy-backed,
  fail-closed), `assert_not_legacy()` (refuses the Phase 08A folder unless
  `HB_ALLOW_LEGACY_BRIEF_DIR=1`), `redacted_brief_dir()`.
- `run_daily_local_agent` defaults `vault_brief_dir` to `governed_brief_dir()` and asserts non-legacy
  (fail-closed → `vault_brief_dir_refused`); the launchd installer pins `--vault-brief-dir` explicitly
  so the plist can never drift. Status surfaces `outputs.vault_brief_dir_redacted` +
  `guardrails.vault_brief_folder_pinned`.
- **Scope:** the separate Phase 08A/09 MCP-handoff brief (`run_daily_brief` →
  `resolve_brief_path` default) is intentionally **unchanged** — its source-manifest governance tracks
  the Phase 08A approved root. Only the scheduled operator brief moved. (Migrating the Phase 09
  product is a separate governance change, deliberately out of scope.)

### Local-model executive synthesis (`local_ai/`)

- `daily_brief_context_packet.py` — bounded, source-linked, date-window-aware context packet built
  from existing redacted read models (action candidates, accepted tasks/commitments, follow-up watch,
  relationship candidates, Procore signals, classified calendar events). Conservative caps; no raw
  bodies / join URLs / tokens / attendee lists.
- `daily_brief_synthesis_schema.py` — `DailyBriefSynthesis` (nine operator sections). `extra="ignore"`
  (unknown fields dropped — never rendered/persisted; receipts are hash-only, so the raw boundary is
  unaffected). Size limits are clamped by validators; malformed JSON / wrong types still fail closed.
- `daily_brief_llm_synthesis.py` — `synthesize_daily_brief()` runs the packet through the reusable
  `StructuredOutputClient` (schema validation, bounded retry/self-repair, single-hop fallback,
  hash-only receipts). Fail-closed: unavailable/timeout/schema-invalid/empty → `degraded`, never a
  success. `render_synthesis_markdown()` / `render_degraded_markdown()` produce the brief markdown.
- Profile: `brief_synthesis` (seed) → fallback `default_extract`. Pinned model chosen by the live
  benchmark (see evidence) — mistral-nemo:12b vs qwen2.5:14b on schema-valid rate, latency, section
  completeness, hallucination, egress, meeting-prep + prioritization quality.

### Project inference + calendar quality

- `project_aliases.py` + `project_aliases.seed.yaml` — deterministic alias → canonical `project_key`
  (case-insensitive, word-boundary, longest-alias-wins). Unresolved → grouped under "Needs Project
  Review" (never inline `project:__unassigned__`). `summarize_unresolved_tokens()` diagnostics drive
  alias-coverage improvement.
- `calendar_classify.py` — deterministic pre-model value tier (`requires_prep` / `key_meeting` /
  `fyi` / `excluded`); PTO, IT-maintenance, lunch, holds, zero-attendee, routine syncs are
  demoted/excluded **before** the model sees them. Wired into `calendar_prep` (project inference +
  class + assigned/unassigned counts + unresolved-token diagnostics in the stage summary).

### Hybrid brief + browser

`run_daily_local_agent` composes the **hybrid** brief: synthesized 9-section narrative (primary) +
collapsed `Appendix: Source-Linked Candidates (audit)` (deterministic, redacted, traceable). The
technical relationship rows are folded into the narrative / kept out of the main body.
`daily_run_html.render_daily_run_html` renders the synthesized section cards + appendix (with a
degraded banner when synthesis failed), scrubbed + fail-closed egress-scanned. Never auto-opens.

## Guardrails / boundary (unchanged invariants)

Raw content only in the Obsidian note, browser HTML, and bounded model context. Status JSON,
persisted candidate rows, logs, repo, tests, evidence stay redacted. Guard columns stay 0. No
external/Graph/Procore/calendar/email writeback. No cloud LLM. No raw prompt/response persisted
(hash-only receipts). Degraded runs preserve the last successful brief and are not counted as success.

## Tests / evidence

`tests/test_phase_10_daily_brief_correction.py` (30 scenarios: routing, synthesis fail-closed,
content quality, alias inference, calendar noise, raw-boundary, degraded preservation, egress). Live
validation + model benchmark under `docs/evidence/` (redacted). Phase 10 regression suites remain
green.
