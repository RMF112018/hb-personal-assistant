# 04 Target CLI Command Surface

## Minimum required commands

```bash
hb-assistant second-brain review list --status pending --limit 25 --json
hb-assistant second-brain review show --candidate-id <candidate_id> --json
hb-assistant second-brain review accept --candidate-id <candidate_id> --json
hb-assistant second-brain review ignore --candidate-id <candidate_id> --reason "not actionable" --json
hb-assistant second-brain review reject --candidate-id <candidate_id> --reason "incorrect extraction" --json
hb-assistant second-brain review summary --json
```

## Optional but recommended commands

```bash
hb-assistant second-brain review snooze --candidate-id <candidate_id> --until 2026-06-12T09:00:00-04:00 --json
hb-assistant second-brain review edit --candidate-id <candidate_id> --title "..." --assignee user --waiting-state waiting_on_me --due-at 2026-06-12T17:00:00-04:00 --json
hb-assistant second-brain review export --status pending --format json --out /tmp/phase10a_review_queue.json --json
```

## Batch commands

```bash
hb-assistant second-brain review accept --candidate-id-file /tmp/ids.txt --max-actions 25 --dry-run --json
hb-assistant second-brain review accept --candidate-id-file /tmp/ids.txt --max-actions 25 --apply --json
hb-assistant second-brain review ignore --candidate-id-file /tmp/ids.txt --reason "not actionable" --max-actions 25 --apply --json
```

## Common options

- `--db <path>`
- `--json`
- `--candidate-id <id>`
- `--candidate-type task|commitment` where disambiguation is needed

## List filters

- `--status pending|accepted|rejected|snoozed|suppressed|ignored|all`
- `--type task|commitment|all`
- `--safety-category normal|contract|legal|financial|payment|claim|entitlement|schedule|safety`
- `--assignee user|other|unknown`
- `--waiting-state waiting_on_me|waiting_on_others|unknown|not_applicable`
- `--urgency low|normal|high|critical`
- `--model-profile default_extract`
- `--source-family email_thread_raw_context`
- `--created-from YYYY-MM-DD`
- `--created-to YYYY-MM-DD`
- `--sort newest|urgency|confidence|high-stakes`
- `--limit 25`

## Default list behavior

Default list should mean actionable pending queue:

- includes `review_status = pending`;
- excludes candidates with future `snoozed_until_utc` if V43 is present;
- sorts newest first unless another sort is specified;
- emits redacted fields only.
