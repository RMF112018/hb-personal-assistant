# Phase 10 V51 — Ollama-Assisted Candidate Ranking & Daily-Brief Assembly

## Purpose

An additive, deterministic-first, raw-safe, local-only **ranking + assembly overlay** on the V50
candidate lifecycle slice. The system already discovers, persists, and lifecycle-filters candidates;
this layer ranks the operator-relevant ones, calibrates from feedback, optionally enriches with a
**bounded** local Ollama advisory pass, flags possible duplicates for review, and assembles a ranked
daily brief — always preserving a deterministic, source-linked brief when the model is unavailable.

The model is **advisory and bounded**. Deterministic rules, source refs, lifecycle state, raw-safety
gates, and human review state remain authoritative.

## Schema (V51, additive)

`src/hb_assistant/store/migrator.py` — `V51_STATEMENTS`, registered after V50, `LATEST_SCHEMA_VERSION
= 51`. Five tables, each carrying the 13 Phase-10 `_P10_GUARDS` (`CHECK(... = 0)`):

| table | purpose |
|---|---|
| `daily_brief_ranking_runs` | one raw-free metadata row per ranking attempt (hashes, model status, coverage, usefulness) |
| `daily_brief_ranked_candidates` | per-candidate ranking overlay (scores, redacted why, reason codes) |
| `candidate_similarity_edges` | advisory duplicate/similarity edges (`review_duplicate_candidate`; never auto-merge) |
| `daily_brief_assembly_runs` | one metadata row per assembled brief |
| `daily_brief_assembly_sections` | section-level ordered candidate-id lists |

All persistence is idempotent on stable keys (deterministic prefixed-sha ids: `rkr:` / `sme:` /
`asm:`). Store helpers live in `construction/store/repositories.py`.

## Modules (`construction/second_brain/local_ai/`)

- `candidate_ranking_models.py` — strict Pydantic contracts; model-facing schemas use `extra="forbid"`
  and clamp every string; the model may cite only packet aliases (`c1`, `c2`, …).
- `candidate_ranking_packets.py` — builds the deterministic packet from the V50 review-queue rows;
  excludes hidden states; withholds source-missing; fails closed on a planted leak; computes
  `candidate_set_hash`, `feedback_digest_hash`, coverage, `packet_guard_clean`.
- `feedback_calibration.py` — bounded, aggregate, raw-free calibration (`MIN_FEEDBACK_SAMPLES=5`,
  `MAX_CALIBRATION_ADJUSTMENT=±0.10`, no negative transfer).
- `candidate_ranking.py` — deterministic base score + blend; bounded model influence
  (`MAX_RANK_MOVEMENT=3`, `DET_CLOSE_THRESHOLD=0.08`); stable tie-breakers.
- `ollama_candidate_ranking.py` — wraps `StructuredOutputClient`; drops unknown-alias advice;
  withholds the whole layer on leaky narrative; fails closed to deterministic; hash-only receipts.
- `candidate_similarity.py` — deterministic exact clusters + normalized-text match + optional
  hermetic embedding cosine; advisory edges only, never auto-merge/suppress.
- `daily_brief_assembly.py` — orchestration entry point `run_candidate_ranking_and_assembly` +
  `ranking_stage_context` (gate contradictions). Deterministic section order; honest degraded banner.

## Integration

- **CLI**: `hb-assistant second-brain daily-brief rank-candidates` (dry-run default; `--apply`
  requires `--max-persist`; `--no-client`, `--mock-output`, `--include-similarity`, `--db`). Exit
  codes 0 ok / 2 invalid usage / 3 fail-closed / 1 unexpected.
- **Daily run**: `daily_run.run_daily_local_agent` runs the overlay hermetically (deterministic, no
  model call) on apply runs, emits a `candidate_ranking` status block, and feeds `ranking_context` to
  the usefulness gate. The bounded advisory model is opt-in via the CLI (the scheduler stays
  network-free). The overlay never crashes the run; a stage error degrades it.
- **Usefulness gate**: `evaluate_usefulness_gate(..., ranking_context=…)` — opt-in; `None` preserves
  legacy behaviour. Contradictions (model item missing source refs / lifecycle-excluded /
  enriched-without-receipt / fallback-but-claims-success / coverage<1.0) fail a would-be success.

## Safety posture

No production-DB mutation (validated on frozen `/tmp` copies; prod SHA unchanged). No Graph / Procore
/ email / calendar / SharePoint / OneDrive / Obsidian / external writeback. No cloud LLM. No raw
content, prompts, responses, bodies, URLs, tokens, or local paths persisted or emitted — every text
field is re-scanned with the shared forbidden-token scanner; the 13 guard columns stay zero.
