# 00 — Repo truth and branch guard

## Objective

Create the branch and prove the exact redacted replay boundary before editing.

## Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git fetch origin
git checkout main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
git log --oneline -8

git checkout -b fix/procore-full-raw-payload-ingestion
```

Stop if the worktree is dirty.

## Required inspection

```bash
grep -R "canonical_json_redacted" -n src/hb_assistant/procore src/hb_assistant/store tests | head -80
grep -R "procore_endpoint_raw_payloads" -n src/hb_assistant tests docs | head -120
grep -R "raw_procore_payload_persisted" -n src/hb_assistant tests docs | head -120
grep -R "def run_live_sync" -n src/hb_assistant/procore/live_sync.py
grep -R "def backfill_from_live_records" -n src/hb_assistant/procore/structured_analytics.py
grep -R "LATEST_SCHEMA_VERSION" -n src/hb_assistant/store/migrator.py
```

## Required scratch report

Write `/tmp/procore_full_raw_repo_truth.md` with:

- base commit;
- schema head;
- functions reading `canonical_json_redacted`;
- function inserting `procore_endpoint_raw_payloads`;
- function creating structured values;
- live sync location where raw endpoint item objects exist before normalization;
- current tests covering V46 structured analytics;
- no-leak tools available.

Do not commit the scratch report.

## Continue only if

- current reprocess uses redacted legacy payloads;
- live sync has access to full item payloads;
- implementation can be validated on `/tmp` DB copies and fixtures;
- production DB is not needed for implementation validation.
