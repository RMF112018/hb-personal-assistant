# Runbook — Daily Brief Raw Projection First Slice

Operator commands for running and validating the slice. All apply/validation work uses a `/tmp` DB
copy; never `--apply` against the production DB during validation.

## 0. Copy the production DB (validation target)

```bash
DB_SRC="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
ROLL="/tmp/hb-first-slice-$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$ROLL"
cp -p "$DB_SRC" "$ROLL/copy.sqlite"
COPY="$ROLL/copy.sqlite"
```

> If a `graph mail index` backfill or scheduler is writing the production DB, the copy is a
> last-checkpoint snapshot (run `PRAGMA quick_check` on it). Validation is unaffected; a literal
> production before==after hash is not meaningful while a writer runs.

## 1. Projection status / coverage / activation

```bash
# Counts only (raw + structured per family, source-quality distribution)
hb-assistant email-calendar raw status --db "$COPY" --json

# Completeness (exit 3 on any unmapped business field)
hb-assistant email-calendar raw projection-coverage --db "$COPY" --json

# Dry-run (no writes)
hb-assistant email-calendar raw projection-reprocess --db "$COPY" --json

# Apply on the copy (requires all three: --apply --no-dry-run --db)
hb-assistant email-calendar raw projection-reprocess --db "$COPY" --apply --no-dry-run --json
```

## 2. Calendar candidate projection

```bash
# Dry-run (would-persist + project resolution + substrate split)
hb-assistant second-brain calendar-prep build --db "$COPY" --dry-run --lookahead-days 21 --json

# Apply on the copy (capped, idempotent, source-linked)
hb-assistant second-brain calendar-prep build --db "$COPY" --apply --max-persist 25 --json
```

## 3. Procore ranked candidate projection

```bash
hb-assistant second-brain procore-digest build --db "$COPY" --dry-run --json
hb-assistant second-brain procore-digest build --db "$COPY" --apply --max-persist 25 --json
```

## 4. Integrated daily run (status + first-slice gates)

The daily run sequences: projection → follow-up → procore → calendar → synthesis → render, then the
source-ref + usefulness/contradiction gates. The `--json` output carries the `first_slice` block
(projection, candidate counts, source-ref/project-key coverage, calendar, procore, email/follow-up,
data_gaps, usefulness_verdict, degraded_reasons).

```bash
hb-assistant second-brain daily-run run --db "$COPY" --json            # dry-run preview
# (apply on the copy is exercised in tests / evidence; the scheduled production apply path is the
#  intentional apply pathway — do not hand-run apply against production.)
```

## 5. Raw-leak scan over any generated evidence

```bash
hb-assistant email-calendar raw no-raw-leak-scan --path docs/evidence/phase-10-daily-brief-raw-projection-first-slice --json
```

## 6. Project identity first pass (deterministic, on copy)

```bash
python -c "from hb_assistant.construction.store.repositories import ConstructionStore; \
from hb_assistant.construction.data_quality.project_identity import backfill_project_identity; \
import json; print(json.dumps(backfill_project_identity(store=ConstructionStore(db_path='$COPY'), dry_run=False)['populated_identities'] if False else 'run dry_run first', default=str))"
```

## Production rollout notes

- The projection apply + candidate persistence run inside the **scheduled** daily-run apply pathway
  (the intentional production apply path). Do not hand-run `--apply` against production outside that
  path (a scheduler/orchestrator run uses real config and can live-sync/migrate).
- Projection apply is idempotent and source-quality-precedence-safe; re-running converges structured
  rows toward the current raw substrate.
- Guard columns must stay 0 and the egress scan must stay clean on every apply.
