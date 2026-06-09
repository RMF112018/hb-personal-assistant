# Phase 10 Graph Drive Raw File Metadata Package — Modified-By Capture

## Objective

Implement complete SharePoint/OneDrive raw operational metadata capture for Graph drive items, with special emphasis on:

- project reference;
- folder name/path;
- file name;
- modified date/time;
- modified-by user names.

The current repo-truth indicated that file name, path/folder metadata, project/source reference, and modified date/time are already partly or fully captured, but `lastModifiedBy` / modified-by user identity is not first-class in the schema, normalizer, indexer, read model, or tests.

This package instructs the local code agent to implement that gap end-to-end.

## How to use this package

Tell the local code agent:

```text
Execute the objective defined at {unzipped_package_path}/README.md
```

The local agent must then execute the prompt files in numeric order.

## Target repository

`RMF112018/hb-personal-assistant`

## Target branch

Use the active working branch requested by Bobby. If no branch is specified, create a focused implementation branch from the current safe base.

Recommended branch name:

```bash
experiment/graph-drive-raw-metadata-modified-by
```

If this work is being continued on `experiment/local-agent-family-proof`, the agent must verify that choice with Bobby before modifying files.

## Non-negotiable operating rules

- Repo truth is authoritative.
- DB truth is authoritative.
- Do not assume the prior audit is still current.
- Re-check branch, HEAD, dirty tree, and branch containment before and after each prompt.
- Do not modify `main` unless Bobby explicitly instructs it.
- Do not commit raw file names, raw paths, raw user names, URLs, client data, or private metadata in docs/evidence/tests.
- Local SQLite DB may store raw operational metadata because Bobby explicitly requires it for this use case.
- Committed evidence must use counts, schema facts, redacted samples, booleans, and safe column names only.
- No external writeback.
- No Graph mutation.
- No Procore mutation.
- No cloud LLM.
- No destructive migration without a clear backward-compatible migration and validation proof.
- Do not broaden into full document content extraction.
- This package is about SharePoint/OneDrive drive-item operational metadata only.

## Prompt sequence

| Order | Prompt file | Purpose | Commit expected |
|---:|---|---|---|
| 00 | `00_REPO_TRUTH_AND_SCOPE_LOCK.md` | Verify branch/repo/schema/files and lock scope | No |
| 01 | `01_SCHEMA_AND_CONTRACT_AUDIT.md` | Audit Graph drive item contract, schema, mapper, DB reality | No |
| 02 | `02_SCHEMA_MIGRATION_AND_REPOSITORY_CHANGES.md` | Add schema/storage/repository support for modified-by raw metadata | Yes |
| 03 | `03_GRAPH_DRIVE_ITEM_NORMALIZATION_AND_INDEXING.md` | Wire Graph `lastModifiedBy` through normalizer/indexer/upsert paths | Yes |
| 04 | `04_CLI_READ_MODELS_AND_SAFE_OUTPUTS.md` | Expose safe verification/read-model surfaces without leaking raw evidence | Yes, if code/docs changed |
| 05 | `05_TESTS_AND_VALIDATION.md` | Add/repair tests and run targeted validation | Yes, if fixes/docs changed |
| 06 | `06_LIVE_DB_PROOF_AND_BACKFILL.md` | Prove on DB copy, backfill/reindex plan, no raw leakage in evidence | Yes, docs/evidence only if applicable |
| 07 | `07_FINAL_AUDIT_AND_HANDOFF.md` | Final repo-truth audit and handoff | Usually docs/evidence commit only, if required |

## Definition of done

The implementation is complete only when all of the following are true:

1. The schema has first-class fields for modified-by metadata on Graph drive items or an explicitly justified equivalent raw metadata storage path.
2. The normalizer/indexer captures Graph `lastModifiedBy` from drive items when provided.
3. The DB persists:
   - project reference;
   - folder/path reference;
   - file name;
   - modified date/time;
   - modified-by display name;
   - stable modified-by user ID when available;
   - modified-by email/UPN only if safely available and intentionally allowed;
   - raw `lastModifiedBy` JSON or equivalent raw metadata when justified.
4. Missing `lastModifiedBy` is handled gracefully.
5. Existing rows can be backfilled by re-running the indexer, or a safe migration/backfill plan exists.
6. Tests prove capture, persistence, null handling, idempotency, and safe output behavior.
7. Live validation on a DB copy proves columns exist and populate from sample/live Graph drive item data.
8. Evidence and docs do not contain raw private file/user metadata.
9. No Graph writeback or external writeback exists.
10. Final handoff clearly states exactly what is captured and where.

## Required final handoff format

At the end, the local agent must report:

1. branch and HEAD;
2. changed files;
3. schema version and migration summary;
4. tables/columns added or modified;
5. Graph fields captured;
6. modified-by behavior;
7. project/folder/file/modified timestamp behavior;
8. tests added/updated and results;
9. live DB proof results using safe counts only;
10. safe evidence location;
11. guardrails/no-writeback proof;
12. known limitations;
13. rollback instructions;
14. whether the implementation is ready for audit.

## Stop conditions

Stop and report before proceeding if:

- the target branch is wrong and cannot be safely corrected;
- the schema path is ambiguous or conflicts with an active migration;
- Graph drive item samples do not include `lastModifiedBy` and no fixture or safe mock can validate the path;
- implementation would require Graph writeback;
- implementation would require committing raw private file names, paths, or user names;
- production DB mutation would be required without Bobby approval;
- a destructive migration is needed;
- the repo already implements the requirement in a different first-class way, in which case document it and ask whether to validate only.

## Validation philosophy

Every implementation prompt must validate at three levels:

1. Code-level:
   - unit tests;
   - migration tests;
   - repository/upsert tests;
   - CLI/read-model tests;
   - ruff/format/mypy.

2. Workflow-level:
   - safe DB copy;
   - indexer dry-run/apply if supported;
   - row-count proof;
   - idempotent re-run.

3. Output/evidence-level:
   - no raw private metadata in committed artifacts;
   - safe redacted evidence;
   - local DB contains required raw metadata fields.
