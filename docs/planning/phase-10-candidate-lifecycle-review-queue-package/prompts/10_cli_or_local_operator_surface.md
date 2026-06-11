# Prompt 10 — CLI / Local Operator Surface

## Objective

Expose the unified lifecycle safely through local CLI commands.

## Audit first

Inspect existing CLI structure. Do not break existing `second-brain review` verbs.

## Preferred additive surface

```bash
hb-assistant second-brain candidates review --db <copy> --json
hb-assistant second-brain candidates show <subject-id> --subject-type <type> --db <copy> --json
hb-assistant second-brain candidates accept <subject-id> --subject-type <type> --db <copy> --json
hb-assistant second-brain candidates reject <subject-id> --subject-type <type> --reason <code> --db <copy> --json
hb-assistant second-brain candidates snooze <subject-id> --subject-type <type> --until YYYY-MM-DD --db <copy> --json
hb-assistant second-brain candidates merge <source-id> <target-id> --source-type <type> --target-type <type> --db <copy> --json
hb-assistant second-brain candidates close <subject-id> --subject-type <type> --db <copy> --json
hb-assistant second-brain candidates reopen <subject-id> --subject-type <type> --db <copy> --json
hb-assistant second-brain candidates suppress <subject-id-or-group-key> --scope candidate|group --reason <code> --db <copy> --json
hb-assistant second-brain candidates feedback --db <copy> --json
```

## Rules

- Commands must operate only on the DB path passed in validation.
- JSON output raw-safe.
- Mutating batch/file operations default dry-run.
- Single-item operations may apply immediately only if consistent with existing operator posture.
- Exit codes documented.
- `--include-hidden` available for review output.
- `--as-of YYYY-MM-DD` or `--now-utc` available for snooze/daily-brief tests.

## Tests

Create `tests/test_phase_10_candidate_lifecycle_cli.py`.

Assertions:

- read commands work against temp DB
- mutate commands affect only passed DB
- dry-run does not write
- batch apply requires `--apply`
- no raw forbidden keys in JSON

