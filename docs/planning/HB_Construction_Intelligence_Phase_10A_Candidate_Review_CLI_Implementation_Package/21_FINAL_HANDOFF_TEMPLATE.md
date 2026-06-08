# 21 Final Handoff Template

Use this structure after implementation.

## Summary

Implemented Phase 10A candidate review CLI for local task/commitment candidates.

## Changed files

- `<file>` — `<summary>`

## Commands now available

```bash
hb-assistant second-brain review summary --json
hb-assistant second-brain review list --status pending --limit 25 --json
hb-assistant second-brain review show --candidate-id <candidate_id> --json
hb-assistant second-brain review accept --candidate-id <candidate_id> --json
hb-assistant second-brain review ignore --candidate-id <candidate_id> --reason "not actionable" --json
hb-assistant second-brain review reject --candidate-id <candidate_id> --reason "incorrect extraction" --json
```

## Safety result

- No raw prompt/body/response persisted or emitted.
- No external writeback performed.
- Guard columns remain zero.

## Next recommended command

```bash
hb-assistant second-brain review summary --db "$DB" --json
```
