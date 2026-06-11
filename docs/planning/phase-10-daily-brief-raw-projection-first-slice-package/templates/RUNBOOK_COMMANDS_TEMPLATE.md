# Runbook Commands Template

Replace placeholders after implementation with exact command names/flags.

## Projection

```bash
.venv/bin/hb-assistant email-calendar raw status --db "$DB_COPY" --json
.venv/bin/hb-assistant email-calendar raw projection-coverage --db "$DB_COPY" --json
.venv/bin/hb-assistant email-calendar raw projection-reprocess --db "$DB_COPY" --json
.venv/bin/hb-assistant email-calendar raw projection-reprocess --db "$DB_COPY" --apply --no-dry-run --json
```

## Calendar candidates

```bash
# Fill in exact implemented command
.venv/bin/hb-assistant second-brain calendar-prep build --db "$DB_COPY" --dry-run --json
.venv/bin/hb-assistant second-brain calendar-prep build --db "$DB_COPY" --apply --max-persist 25 --json
```

## Procore candidates

```bash
# Fill in exact implemented command
.venv/bin/hb-assistant second-brain procore-digest build --db "$DB_COPY" --dry-run --json
.venv/bin/hb-assistant second-brain procore-digest build --db "$DB_COPY" --apply --max-persist 25 --json
```

## Daily run copy proof

```bash
# Fill in exact implemented command if supported
.venv/bin/hb-assistant second-brain daily-run run --db "$DB_COPY" --apply --json
```

## Leak scan

```bash
.venv/bin/hb-assistant email-calendar raw no-raw-leak-scan \
  --path docs/evidence/phase-10-daily-brief-raw-projection-first-slice \
  --json
```

## Tests

```bash
python -m pytest <targeted tests> -q
python -m compileall src/hb_assistant
python -m ruff check src tests
```
