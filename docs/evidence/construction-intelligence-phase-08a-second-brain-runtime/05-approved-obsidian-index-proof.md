# Phase 08A · Synthesized Prompt 05 — Approved Obsidian Indexing — Proof

Indexes only system-generated/approved, marker-bounded Obsidian notes into the V26
`obsidian_index_manifests` + `obsidian_index_entries` tables (metadata only).
Read-only over the vault; no source-note mutation, no raw content, no raw vault
browsing, no new tables. Schema stays V26 / 141. Package baseline `c2656e1` stale;
actual HEAD at start was `33b6eb8`.

## Repo-truth preflight (before edits)

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `33b6eb8af533a053c35bf10d9195dcb68a15607b` |
| `git status --short` | clean except untracked `.claude/`, `.code-graph/` |
| `construction-agent validate --json` | `schema_version=26` |
| `data-quality table-inventory --json` | `contract_table_count=141` |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |

## Files changed

Created:
- `src/hb_assistant/resources/json/obsidian_index_manifest_contract.json` (from package).
- `resources/config/phase_08a_obsidian_index_policy.seed.yaml` (from package).
- `src/hb_assistant/construction/second_brain/obsidian_index/__init__.py`, `models.py`, `policy.py`, `indexer.py`.
- `tests/test_obsidian_index.py`, `tests/test_second_brain_index_cli.py`.
- `docs/architecture/62-phase-08a-approved-obsidian-indexing.md`.
- `docs/evidence/.../approved-obsidian-index-proof.json`, `05-approved-obsidian-index-proof.md`.

Modified:
- `src/hb_assistant/construction/second_brain/contracts.py` (registered manifest contract).
- `src/hb_assistant/construction/second_brain/__init__.py` (re-export obsidian_index API).
- `src/hb_assistant/construction/second_brain/retrieval/readers.py` (`read_approved_obsidian` + registry).
- `src/hb_assistant/cli/second_brain.py` (`index` sub-group + `index obsidian`).
- `tests/test_phase_08a_contracts.py` (required-key map for the manifest contract).

## Validation commands and exit codes

| Command | Result |
| --- | --- |
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! (exit 0) |
| `mypy src` | Success: no issues found in 209 source files (exit 0)* |
| `pytest tests/test_obsidian_index.py tests/test_second_brain_index_cli.py` | 12 passed |
| `pytest -m "not live and not integration and not manual"` | 2376 passed, 4 skipped, 1 deselected (exit 0) — +14 new tests |
| `second-brain index obsidian --dry-run --json` | exit 0, `mode=dry_run`, 4 approved roots |
| `construction-agent validate --json` | `schema_version=26` (unchanged) |
| `data-quality table-inventory --json` | `contract_table_count=141` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` (unchanged) |

\* pre-existing benign note about an unused `hb_assistant.retrieval.context` override; no errors.

## Evidence proof

`approved-obsidian-index-proof.json` — `proof_passed: true`; contract required
fields present on the index record; `no_raw_content: true`;
`only_managed_notes_indexed: true`; `source_notes_mutated: false`;
`guardrails.raw_vault_browsing: false`; 4 approved roots; policy version
`phase_08a_obsidian_index_policy_v2`.

## Guardrail proof points (tests)

- **Only managed notes indexed** — a note with an `<!-- HB-...:START -->` marker is
  indexed; an unmanaged note is counted in `excluded_count`, never indexed
  (`test_scan_indexes_only_managed_notes`).
- **No raw content** — the section text is hashed, never stored; entry serialization
  excludes the body and any URL (`test_entry_carries_no_raw_content`).
- **Source notes not mutated** — note bytes identical before/after index
  (`test_source_notes_not_mutated`).
- **dry-run + apply persist manifests** with the matching `mode`; all 10
  `CHECK(col=0)` guard columns at 0 (`test_apply_persists_*`, `test_dry_run_*`).
- **Graceful when vault absent** — 0 entries, 0 excluded (`test_missing_vault_degrades`).
- **Retrieval integration** — broker now reads approved Obsidian outputs via
  `read_approved_obsidian` (previously a coverage warning).

## Reconciliations / known limitations

- The V26 `obsidian_index_entries` table lacks `review_tier` / `approved_root_label`
  / `source_ref_count` columns; these contract fields are carried in the entry's
  `source_refs_json` metadata blob. No schema change.
- Approved generated outputs default to review_tier 1 / auto_advisory / high
  confidence; per-note frontmatter overrides are a future enhancement.
- `project_key` derived from a simple frontmatter probe; null when absent.

## Env var names (no values)
`HB_SECOND_BRAIN_OBSIDIAN_INDEX_POLICY`.

## Next prompt readiness
The approved-Obsidian index feeds the retrieval broker. Next: research-packet agent +
orchestrator/query/daily-brief wiring (Prompts 06/10/13); HTML/delivery (Phase 08B);
V27 receipt tables + 08A no-writeback proof arm (owning prompts).
