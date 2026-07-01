# Phase 19 repo-truth audit

Base: Phase 18A commit `1aa070bf` + Phase 18 on `origin/main`.

## Schedule read models (reuse)

- `ProjectScheduleSummaryService.build_export` — deterministic memo markdown (not `build_summary()` for portfolio)
- `ProjectScheduleControlsService.build_controls` — controls snapshot
- `ProjectSchedulePortfolioReviewService.build_dashboard` / `build_export_markdown` — portfolio snapshot
- `build_review_status_rollup` + thin hub context — review status without full summary

## Obsidian patterns (reuse)

- Vault writes: direct filesystem with managed block replacement (`hb-schedule-note:begin/end`)
- **Not** using `Source Notes/` source-card pipeline or source index queue
- Optional Ollama: gated behind `--summarize --confirm-local-llm`; default `ollama_calls=0`
- Language QA: `validate_rendered_text` (negation-aware), `find_redaction_leaks`

## Vault paths

- `Work/HB Personal Assistant/Schedule Review/Projects/{project_key}/`
- `Work/HB Personal Assistant/Schedule Review/Portfolio/`

## Gaps filled

- `ProjectScheduleSecondBrainNoteService` — PM-safe note source payloads
- `schedule_review_note_generator` — Obsidian markdown + managed block
- `schedule_obsidian_note_writer` — idempotent fixture vault writes
- `scripts/obsidian_schedule_review_notes.py` — dry-run default CLI

## Explicit non-goals honored

- No source-card mutation, graph links, or reciprocal backlinks
- No live vault writes in evidence (dry-run only on live DB)
- No external LLM
