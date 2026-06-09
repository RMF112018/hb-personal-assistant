# 02 — Schema Migration and Repository Changes

## Objective

Implement the schema and repository/storage changes required to persist modified-by metadata for Graph SharePoint/OneDrive drive items as raw local operational metadata.

## Required design principles

- Store raw operational metadata locally because Bobby explicitly requires it.
- Do not commit raw values in tests/docs/evidence.
- Prefer first-class columns for fields that must be queried:
  - modified-by display name;
  - modified-by user ID;
  - modified-by email/UPN if available and intentionally allowed;
  - modified-by application display name if available.
- Preserve a raw JSON field only if useful for future-proofing and safe to keep local.
- Make migration backward-compatible.
- Existing DBs must migrate cleanly.
- Fresh DBs must create the new columns.

## Recommended schema fields

Add to the canonical drive item table, using actual repo table naming discovered in prompts 00–01.

Recommended names:

```text
last_modified_by_display_name
last_modified_by_user_id
last_modified_by_email
last_modified_by_application_display_name
last_modified_by_json
```

If repo naming conventions prefer `modified_by_*`, use the repo convention, but be consistent.

## Migration requirements

- Add a new schema migration.
- Update fresh schema creation if separate from migrations.
- Update any dataclasses/models/row mappings.
- Update upsert/insert/list repository methods.
- Ensure old rows remain valid with NULL values.
- Ensure repeated indexing updates these columns idempotently.
- Ensure indexes are added only if needed.

## Repository behavior

The repository layer must support:

- inserting new drive item rows with modified-by metadata;
- updating existing rows when modified-by metadata changes;
- returning modified-by metadata in read models where appropriate;
- not exposing raw names/emails in default evidence/diagnostic output unless explicitly local/operator-facing.

## Tests required

Add migration/repository tests:

1. fresh DB includes new fields;
2. migrated DB includes new fields;
3. upsert persists modified-by display name;
4. upsert persists modified-by user ID;
5. upsert persists modified-by email/UPN when present;
6. upsert persists application display name when present;
7. missing `lastModifiedBy` stores NULLs gracefully;
8. repeated upsert is idempotent;
9. update changes modified-by values when Graph payload changes;
10. no raw values appear in committed evidence fixture output.

Use fake names like `Test User Alpha`, not real names.

## Validation commands

Run targeted tests after implementation:

```bash
python -m pytest tests -q -k "drive_item or graph_file or source_location or migration"
ruff check <changed paths>
ruff format --check <changed paths>
mypy <changed modules>
```

## Commit behavior

Commit only coherent schema/repository changes and tests from this prompt.

Suggested commit message:

```text
feat(graph-files): persist drive item modified-by metadata
```

Final response should include:

- migration file;
- schema version;
- changed files;
- tests run;
- known limitations.
