# Phase 04B — Prompt 11 — Obsidian Registration

**Date:** 2026-05-29
**Branch:** main
**Scope:** Register Phase 04B enriched Procore memory into source-linked Obsidian
views without raw sensitive payload persistence.

## Scope decisions

- **Read-only / local.** No Procore call. Reads the V7 enrichment tables via the
  store readers; writes one marker-bounded note gated by `--apply` (dry-run
  default), mirroring the existing `procore obsidian preview` confirm/apply gate.
- **No migration / V7 change** (migration 7); **endpoint count stays 27**.
- **Single consolidated note** (`01_Projects/<project>.procore-memory-register.md`)
  with one outer managed block (`HB-PROCORE-ENRICHED-REGISTER`) containing eight
  `##` sections — so apply writes exactly one file and re-runs are idempotent while
  preserving user notes outside the block.
- **Safe by construction:** output uses only already-redacted columns
  (`title_redacted`, `summary_redacted`, hashes, PII-masked `excerpt_redacted`),
  source `record_key` / `procore_record_id`, reason codes, and keyword action
  candidates — never raw bodies, signed URLs, or tokens.

## Files

### Created
- `src/hb_assistant/procore/obsidian_register.py` — `build_enriched_registers()` /
  `apply_enriched_register()`.
- `tests/test_procore_obsidian_enriched_register.py` — 7 tests.

### Modified
- `src/hb_assistant/store/procore_enrichment.py` — read-only
  `get_procore_text_intelligence()` (+ `__all__`).
- `src/hb_assistant/cli/procore.py` — `procore obsidian enriched` command.
- `docs/operations/procore-operator-runbook.md` — Prompt 11 command section.

## Eight register views → sources

| Section | Source (read-only) |
| --- | --- |
| Open Actions | `get_procore_action_signals(status="open")` |
| Last 48h Changes | `get_procore_changes` filtered `detected_at_utc >= since` |
| Inspection Unanswered Items | action signals `inspection_has_unanswered_items` / `inspection_item_unanswered` |
| Safety / Compliance Queue | action signals `observation_open_safety` / `inspection_open_safety` |
| Meeting Decisions / Actions | `get_procore_text_intelligence(with_action_candidates=True)` for meeting endpoints |
| RFI Response Changes | changes where `endpoint_id ∈ {rfis, rfi-responses}` |
| Submittal Workflow Changes | changes where `endpoint_id ∈ {submittals, submittal-responses, submittal-approvers}` |
| Schedule Risk Signals | action signals `signal_type` startswith `activity_` |

All signals/changes are fetched once and partitioned in Python. Each section
renders a markdown table + an `_Query: \`hb-assistant procore live …\`_` reference
and an empty-state placeholder. Every row includes the source `record_key`
(pipes markdown-escaped) and `procore_record_id`.

## File path + frontmatter + markers

```
01_Projects/<project_key>.procore-memory-register.md
```
```yaml
---
type: procore_enriched_register
project_key: <project>
source: procore_second_brain_sqlite
review_sensitive: false
generated_utc: <iso>
---
```
Managed block: `<!-- HB-PROCORE-ENRICHED-REGISTER:START -->` …
`<!-- HB-PROCORE-ENRICHED-REGISTER:END -->` (written via the existing
`_write_procore_artifact` marker-bounded atomic write; vault root resolved via
`ConstructionVaultWriter`, same as the other `procore-*` artifacts). Footer carries
the standard `PROCORE_GUARDRAILS` block.

## CLI

`procore obsidian enriched --project <key> [--since "48 hours ago"] [--dry-run |
--apply --confirm] [--json]`. Dry-run returns the rendered note + per-section
counts with `written_paths: []`; apply writes the single file. Fail-closed reason
codes: `since_unparseable`, `vault_root_unconfigured`.

## Tests / guarantees

- **dry-run preview:** 8 sections, `written_paths == []`, no file on disk.
- **apply:** writes exactly one `…procore-memory-register.md`; frontmatter + outer
  markers + populated sections; idempotent (re-run → still one file, one marker pair).
- **no raw signed URLs / tokens / payloads:** seeded a URL+email+token in source
  text → rendered output has no `https://`, `token=secret`, `?sig=`, `Bearer`, or
  `access_token`; email masked in the excerpt; only the safe action-candidate
  tokens surface.
- **source links included:** `record_key` (escaped) + `procore_record_id` + the
  `hb-assistant procore live …` query references present.
- CLI dry-run + apply exercised via `CliRunner`.

## Validation

- `python -m pytest -q tests/test_procore_obsidian_enriched_register.py` → **7 passed**.
- `python -m pytest -q --no-header` → full suite **green** (endpoint count 27, migration version 7 unchanged).
- `ruff check .` → **All checks passed**; `mypy .` → **Success (207 source files)**; `compileall` → **OK**.
- Manual local dry-run: `hb-assistant procore obsidian enriched --project tropical --dry-run --json` → `ok=true`, `mode=dry_run`, 8 sections, `written_paths=[]`.
- `hb-assistant diagnostics scan-sensitive --repo . --json` → **0 findings** in the new/edited files.
