# Prompt 08: Provenance Safe File Ingestion

## Objective

Ensure real file ingestion cannot proceed without valid source provenance and separate sample/demo paths from real paths.

## Required Starting Checks

Run and capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
python --version
```

Do not proceed if the working tree contains unrelated uncommitted changes unless you first document them and isolate your patch.

## Agent Rules

- Do not trust prior closeout claims.
- Do not re-read files already in current context unless changed or required by failing tests.
- Do not enable Microsoft 365 writeback.
- Do not log or commit tokens, private keys, PEM bodies, full email bodies, or full file contents.
- Keep the patch tightly scoped to this prompt.
- Create evidence under `docs/evidence/remediation/prompt-08-*/`.

## Tasks

1. Separate CLI commands:
   - `hb-assistant files sample --json`
   - `hb-assistant files ingest --dry-run --json`
2. `sample` may use synthetic records.
3. `ingest` must require real persisted source records.
4. Real download/parse must fail closed when:
   - `source_record_id` is missing;
   - source link cannot be created;
   - file exceeds approval thresholds;
   - Graph metadata is incomplete.
5. Remove or guard any `sid = 0` real-path behavior.
6. Add tests for missing provenance, dry-run no-download behavior, approved small-file persistence, and source links.

## Validation

```bash
python -m pytest tests/test_file_ingestion.py tests/test_files*.py
hb-assistant files sample --json
hb-assistant files ingest --dry-run --json
```

## Required Commit

```text
fix(files): require source provenance for file ingestion
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
