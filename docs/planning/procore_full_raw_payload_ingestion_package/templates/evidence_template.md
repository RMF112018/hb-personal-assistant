# Evidence template — Procore full raw payload ingestion

## Verdict

- Status:
- Branch:
- Commit:
- Schema version:
- Production DB touched during validation: No

## Repo truth

- redacted replay path:
- live full payload boundary:
- source-quality precedence:

## Full raw fixture proof

| endpoint | raw rows | structured table | structured rows | source_quality | raw_procore_payload_persisted | verdict |
|---|---:|---|---:|---|---:|---|

## Null-rate proof

| table | endpoint | source_quality | rows | fields checked | before null pct | after null pct | verdict |
|---|---|---|---:|---|---:|---:|---|

## Idempotency and precedence

| operation | raw rows | structured rows | source-quality distribution | downgrade count | verdict |
|---|---:|---:|---|---:|---|

## No-leak proof

- Commands:
- Findings:
- Classification:

## Validation

- pytest:
- ruff:
- DB-copy:
- production sha before/after:
