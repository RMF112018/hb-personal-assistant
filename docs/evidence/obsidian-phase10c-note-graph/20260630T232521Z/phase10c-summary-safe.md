# Phase 10C — Local note graph: content/related tags + reciprocal wiki links (sanitized, counts only)

Deterministic candidate retrieval + advisory qwen2.5:14b vetting + deterministic reciprocal wiki-link/
tag writers, confined to managed regions. No broad indexing, source-file read, source-root scan,
queue/DB/runtime-JSON mutation, note create/delete, or cloud model. The local model only VETS.

- base commit: `2cef8c86` (origin/main; Phase 9/10A/10B present — Phase 10B merged first as PR #236).
- branch: `feat/obsidian-phase10c-note-graph-20260630T232521Z`.
- files changed: `src/hb_assistant/obsidian_mcp/source_note_graph.py` (new),
  `scripts/obsidian_source_note_apply_graph.py` (new),
  `tests/test_obsidian_source_note_graph.py` (new), this safe summary. No existing module edited.

## Phase 10B prerequisite
Verified local 10B `ef2a820b`; three-dot diff vs current main was the narrow 6-file appender scope
(no schedule/sensitive/unrelated); clean 3-way merge (no obsidian overlap); merged via PR #236 →
`origin/main` `2cef8c86`; appender + source_local_summary confirmed present.

## Runtime preconditions + live-vault preflight
Port 8000 clear; ACTUAL runtime frozen flags false + capability true; queue 0/0; generated 25 /
not_generated 67 / stale 0; Work md 26; 25 cards each with exactly one local-summary block (all
`status="generated"` from the 10B pilot) and one `# Source Card:` identity; all `card_version
phase10a-v1`; vault_root matches; runtime JSON unmodified.

## Design (advisory-only model; deterministic writes)
- Relationship enums (16) with an APPLY subset (excludes reject/weak_context_only/potential_duplicate);
  controlled tag taxonomy (content-type / disposition / related / review). Qwen may pick ONLY from the
  related/review enum; content-type + disposition tags are deterministic.
- Deterministic candidate retrieval requires ≥1 STRONG content signal (same project / vendor /
  document_number / same-date-same-project); ≥2 for template/reference/metadata/spreadsheet cards.
  Shared-title-phrase is medium (never sufficient alone); path/folder similarity is never a signal.
  Caps: max-notes, max-candidates-per-note, max-relationships.
- Qwen vetting via local `generate_json` (schema-validated: approved bool, enum relationship_type,
  confidence ≥ threshold, reason ≤200, approved-enum tags only; invalid/unknown/below-threshold →
  reject, no write).
- Deterministic writers: controlled frontmatter tag append (block-style only, preserve/dedup, ≤8 new,
  skip non-block frontmatter); single managed related-notes block per card under the best Related
  section; vault-relative disambiguated wiki links (never absolute home paths); reciprocal pair
  writes — both notes or neither; batch backup + write + rollback-on-failure; DB fingerprint
  before/after proves zero DB mutation.

## Dry-run (production, no `--vet`)
- notes_selected 25, candidate_pairs **0**, ollama_called false.
- Cause (count-only): 0/25 cards carry project_number, vendor, or document_number (the indexer does not
  derive these for the synthetic-source files); doc-types heterogeneous (template_form 7, bid_package 7,
  schedule 2, …). With no strong content commonality, the conservative gate correctly yields 0 pairs
  (title/path similarity alone is intentionally insufficient — no weak links invented).

## Pilot apply (Ollama available, qwen2.5:14b installed) — clean no-op
- notes_selected 25, candidate_pairs 0, vetted_pairs 0, approved_pairs 0, relationships_applied 0,
  notes_modified 0, reciprocal_links_applied 0, tags_added 0, created 0, deleted 0, queue_delta 0,
  db_mutations 0, ollama_called true (real model probe succeeded).
- post-apply: Work md 26; 0 managed related-notes blocks; 25 local-summary blocks still `generated`;
  DB generated 25 / not_generated 67 / stale 0; queue 0/0. No production card modified.

## Tests / lint
- new `test_obsidian_source_note_graph.py`: 23 tests (cover the 40 SOW cases — strong-commonality
  gating, schema-bound vetting, approved-enum-only tags, reciprocal two-way links, one-side-fail-
  writes-neither, byte-preservation outside managed/tag regions, no source read / index / scan /
  queue, no DB/runtime mutation, dry-run-no-`--vet` zero Ollama, apply confirm/backend/queue/frozen
  refusals, disambiguated links, safe-evidence redaction). Passed.
- focused obsidian source-card suites (appender/notes/rerender/phase10a/value/spreadsheet/first-
  indexing/domain-routing/self-index/taxonomy/skip-codes): passed. Slow watch_ownership + mcp_backend:
  passed (0 failures). `ruff check` (changed files): clean.

## Confirmations
- production notes modified: **none** (0 candidates → 0 writes) · DB rows changed: no · runtime JSON
  changed: no · source files read: no · source-root scan: no · queue enqueue/drain: no · cloud model:
  no (local Ollama only) · one-way links: none (reciprocal-or-neither by construction) · absolute/
  absolute home paths written: none · local-sensitive backups/details untracked · only count-only safe
  evidence committed.

## Remaining risks / note
The note graph has nothing to link until source cards carry richer deterministic entity metadata
(project/company/person/cost-code/schedule identifiers). The conservative gate is working as designed.

## Recommended next phase
Phase 10D — entity-metadata enrichment (populate project/company/person/cost/schedule identifiers on
source cards so the graph has signal) + a review report (pending/accepted/weak candidates, tag
coverage, isolated/high-value notes, backlink-integrity).
