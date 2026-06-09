# 05 — Tests and Validation

## Objective

Ensure the implementation is comprehensively tested and all relevant regression suites pass.

## Required test categories

### Schema / migration

- fresh DB has new modified-by columns;
- migrated DB has new modified-by columns;
- old rows remain valid;
- fresh construction store auto-migrates.

### Normalization

- full user identity;
- app identity;
- missing identity;
- malformed identity;
- modified timestamp unchanged;
- file name/path/project reference unchanged.

### Repository/upsert

- insert persists fields;
- update changes fields;
- idempotent re-run does not duplicate;
- NULL handling;
- raw JSON field, if present, is valid JSON.

### CLI/read model

- safe counts;
- no raw values by default;
- JSON stable;
- failure mode clear.

### Regression

Run existing Graph files / drive item / source location / scheduler-independent suites.

## Suggested commands

Adapt paths to repo truth:

```bash
python -m pytest tests -q -k "drive_item or graph_file or graph_files or source_location or source_record"
python -m pytest tests/test_agent_registry.py tests/test_second_brain_agents_cli.py -q
ruff check <changed paths>
ruff format --check <changed paths>
mypy <changed modules>
```

If broad tests expose unrelated pre-existing failures, isolate and disclose them. Do not fix unrelated modules unless required by this implementation.

## Evidence discipline

Do not paste raw file names, raw folder paths, raw user names, raw emails, or URLs into docs/evidence.

Use safe summaries only:

```text
construction_drive_items|rows|1234
last_modified_datetime|nonempty|1234
last_modified_by_display_name|nonempty|981
raw_values_emitted|false
```

## Commit behavior

If this prompt requires test fixes or validation docs, commit them.

Suggested commit message:

```text
test(graph-files): prove modified-by drive metadata capture
```
