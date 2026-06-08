# Phase 10A Candidate Review CLI Runbook

## Environment

```bash
export HB_PA_CONFIG=/tmp/hb-pa-dev-live.yml
export DB="$HOME/Library/Application Support/HB Personal Assistant (Dev)/db/hb-personal-assistant.sqlite"
```

## Inspect queue

```bash
hb-assistant second-brain review summary --db "$DB" --json
hb-assistant second-brain review list --status pending --limit 25 --db "$DB" --json
```

## Show candidate

```bash
hb-assistant second-brain review show --candidate-id <candidate_id> --db "$DB" --json
```

## Triage candidate

```bash
hb-assistant second-brain review accept --candidate-id <candidate_id> --db "$DB" --json
hb-assistant second-brain review ignore --candidate-id <candidate_id> --reason "not actionable" --db "$DB" --json
hb-assistant second-brain review reject --candidate-id <candidate_id> --reason "incorrect extraction" --db "$DB" --json
```

Review commands are local-only state transitions. They do not send or update anything externally.
