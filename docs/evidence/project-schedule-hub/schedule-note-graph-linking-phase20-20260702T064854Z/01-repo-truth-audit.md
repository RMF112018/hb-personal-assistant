# Phase 20 Repo-Truth Audit — Schedule Note Graph Linking

## Objective

Add schedule-specific graph linking for Phase 19 `schedule_comparison` notes via a separate
`hb-schedule-graph` managed block inserted after `hb-schedule-note:end`.

## Reuse (pattern only)

| Module | Reused pattern |
|--------|----------------|
| `schedule_obsidian_note_writer.py` | Managed-block upsert, vault bounding, dry-run default |
| `schedule_review_note_generator.py` | `hb-schedule-note` block boundaries (read-only for graph placement) |
| `source_note_graph.py` | Candidate confidence line format inspiration only |
| `obsidian_source_graph_review.py` | Safe JSON/Markdown report shape |

## Explicit non-routes (user amendments)

- No `gc-graph-links` blocks
- No `obsidian_source_note_apply_graph.py` apply path
- No source indexing or source-card mutation
- No frontmatter tag rewrite
- LLM suggestions report-only; never applied to vault

## New surfaces

| File | Role |
|------|------|
| `schedule_note_graph.py` | Discovery, deterministic candidates, path QA |
| `schedule_note_graph_writer.py` | `hb-schedule-graph` managed block apply |
| `schedule_note_graph_review.py` | Safe review JSON/Markdown |
| `schedule_note_graph_llm_validation.py` | Qwen suggestion validation (report-only) |
| `scripts/obsidian_schedule_note_graph.py` | CLI: dry-run default, fixture apply gates |

## Apply gates

- Default: dry-run (`notes_modified=0`, `write_attempts=0`)
- Fixture apply: `--apply-links --confirm-graph-apply` on evidence `fixture-vault/` or `--evidence-dir`
- Live vault apply: blocked unless `--allow-live-vault --confirm-live-vault-apply` (out of scope for evidence)

## Graph block contract

```
<!-- hb-schedule-note:end managed -->

<!-- hb-schedule-graph:begin managed -->
## Schedule Graph Links

- [[vault/relative/path|PM-safe label]] — relationship_type · deterministic · confidence 0.90
<!-- hb-schedule-graph:end managed -->
```

Phase 19 reruns replace only `hb-schedule-note`; graph block and manual tail are preserved.
