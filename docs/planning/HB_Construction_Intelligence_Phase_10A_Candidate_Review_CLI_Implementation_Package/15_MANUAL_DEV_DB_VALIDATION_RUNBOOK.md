# 15 Manual Dev DB Validation Runbook

## Environment

```bash
export HB_PA_CONFIG=/tmp/hb-pa-dev-live.yml
export DB="$HOME/Library/Application Support/HB Personal Assistant (Dev)/db/hb-personal-assistant.sqlite"
```

## Confirm candidate counts

```bash
sqlite3 "$DB" "SELECT review_status, COUNT(*) FROM task_candidates GROUP BY review_status;"
sqlite3 "$DB" "SELECT review_status, COUNT(*) FROM commitment_candidates GROUP BY review_status;"
```

## Review summary and list

```bash
hb-assistant second-brain review summary --db "$DB" --json | tee /tmp/phase10a-review-summary.json
hb-assistant second-brain review list --status pending --limit 10 --db "$DB" --json | tee /tmp/phase10a-review-list.json
```

## Show, accept, and ignore

```bash
CID=<candidate_id>
hb-assistant second-brain review show --candidate-id "$CID" --db "$DB" --json | tee /tmp/phase10a-review-show.json
hb-assistant second-brain review accept --candidate-id "$CID" --db "$DB" --json | tee /tmp/phase10a-review-accept.json

CID2=<candidate_id>
hb-assistant second-brain review ignore --candidate-id "$CID2" --reason "not actionable" --db "$DB" --json | tee /tmp/phase10a-review-ignore.json
```

## Guardrail SQL

Run the guardrail SUM queries in the attached objective prompt and confirm all values are zero or NULL where no rows exist.
