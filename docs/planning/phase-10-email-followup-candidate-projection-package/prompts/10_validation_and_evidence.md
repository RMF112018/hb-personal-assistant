You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-email-followup-candidate-projection-package/`

Before doing anything else:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git status --short
git branch --show-current
git rev-parse HEAD
```

Stop if you are on `main` or if unexplained dirty files are present.

Hard safety constraints:

- Do not mutate the production DB.
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Use `/tmp` DB copies for apply validation.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, full recipient arrays, unbounded subjects, model prompts, or model responses.

# 10 — Validation and Evidence

## Objective

Run full validation on code and `/tmp` DB copies only. Produce raw-free evidence and a usefulness scorecard.

## DB Copy Setup

Use:

```bash
TS="$(date +%Y%m%d-%H%M%S)"
AUDIT_ROOT="/tmp/hb-phase10-email-followup-candidate-projection-$TS"
mkdir -p "$AUDIT_ROOT"

PROD_DB="/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
COPY_DB="$AUDIT_ROOT/audit-copy.sqlite"

cp "$PROD_DB" "$COPY_DB"
```

Never run apply-mode validation against `PROD_DB`.

## Safe Baseline SQL

Run:

```bash
sqlite3 "$COPY_DB" < docs/planning/phase-10-email-followup-candidate-projection-package/templates/raw_safe_sql_checks.sql \
  | tee "$AUDIT_ROOT/raw-safe-baseline.txt"
```

Do not print raw values.

## Apply Replay

Use the current CLI shape from repo truth. Expected pattern:

```bash
.venv/bin/hb-assistant second-brain local-ai daily-run \
  --db "$COPY_DB" \
  --apply \
  --json \
  2>&1 | tee "$AUDIT_ROOT/daily-run-apply-1.json"

.venv/bin/hb-assistant second-brain local-ai daily-run \
  --db "$COPY_DB" \
  --apply \
  --json \
  2>&1 | tee "$AUDIT_ROOT/daily-run-apply-2.json"
```

If command names differ, use the current repo CLI.

## Required Validation Commands

Run targeted tests:

```bash
.venv/bin/python3.12 -m pytest -p no:cacheprovider \
  tests/test_phase_10_email_followup_candidate_projection.py \
  tests/test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table \
  tests/test_phase_10_first_slice_projection_activation.py \
  tests/test_email_calendar_consumer_read_models.py \
  tests/test_phase_10_daily_brief_source_ref_gate.py \
  tests/test_phase_10_usefulness_gate.py \
  -q
```

Run affected daily run / pipeline tests:

```bash
.venv/bin/python3.12 -m pytest -p no:cacheprovider \
  tests/test_phase_10_pipeline.py \
  tests/test_phase_10_daily_run.py \
  tests/test_daily_brief_context.py \
  -q
```

Run static checks on changed files:

```bash
git diff --name-only main...HEAD | rg '\.py$' > "$AUDIT_ROOT/changed-python-files.txt" || true
if [ -s "$AUDIT_ROOT/changed-python-files.txt" ]; then
  .venv/bin/ruff check $(cat "$AUDIT_ROOT/changed-python-files.txt")
  .venv/bin/python3.12 -m compileall $(cat "$AUDIT_ROOT/changed-python-files.txt")
fi
```

Run no-leak scan:

```bash
.venv/bin/hb-assistant email-calendar raw no-raw-leak-scan \
  --path docs/evidence/phase-10-email-followup-candidate-projection \
  --json \
  2>&1 | tee "$AUDIT_ROOT/no-raw-leak-evidence.json"
```

## Evidence Outputs

Write:

- `docs/evidence/phase-10-email-followup-candidate-projection/10-db-copy-validation.md`
- `docs/evidence/phase-10-email-followup-candidate-projection/11-idempotency-replay.md`
- `docs/evidence/phase-10-email-followup-candidate-projection/12-guard-column-proof.json`
- `docs/evidence/phase-10-email-followup-candidate-projection/13-usefulness-scorecard.md`

## Merge Gates

Block merge if:

- any test fails without documented quarantine
- no-raw-leak scan finds any unsafe output
- source-ref coverage for email-derived daily-brief candidates is below 100%
- idempotency replay duplicates candidates
- production DB was mutated
- status/usefulness can report success after email follow-up projection failure
