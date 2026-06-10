# 06 — Validation and evidence

## Objective

Run targeted validation proving the implementation works, does not leak payload bodies, and does not mutate production DB.

## Install

```bash
cd /Users/bobbyfetting/hb-personal-assistant
python -m pip install -e .
```

## Tests

Adjust paths based on actual files added.

```bash
PYTHONPATH="$PWD/src" python -m pytest \
  tests/test_procore_structured_analytics_foundation.py \
  tests/test_procore_full_raw_payload_ingestion.py \
  -q
```

## Ruff

```bash
PYTHONPATH="$PWD/src" python -m ruff check \
  src/hb_assistant/procore \
  src/hb_assistant/cli/procore.py \
  src/hb_assistant/store/migrator.py \
  tests/test_procore_structured_analytics_foundation.py \
  tests/test_procore_full_raw_payload_ingestion.py
```

## DB-copy validation

Resolve production DB through `PathPolicy`, copy to `/tmp`, validate only on copy, and record production sha before/after if production is opened read-only.

Use:

`templates/full_raw_payload_validation_sql.sql`

Required proof:

- migration applies;
- full raw fixture rows write with `raw_procore_payload_persisted=1`;
- source quality is full/high fidelity;
- structured table rows populate from full payload;
- legacy replay does not overwrite full rows;
- no production mutation.

## Leak scan

```bash
git diff --name-only origin/main...HEAD

git grep -n -E "Bearer |access_token|refresh_token|client_secret|X-Amz-|SharedAccessSignature|private_url|https://.*\\?.*(token|sig|signature)" -- \
  src tests docs/evidence/procore_full_raw_payload_ingestion || true

find docs/evidence/procore_full_raw_payload_ingestion -type f \
  \( -name "*.json" -o -name "*.db" -o -name "*.sqlite" -o -name "*.payload" \) -print
```

Classify detector literals separately from real leaks.

## Evidence files

Create the evidence bundle named in the README. Keep it scrubbed. No raw payload values.
