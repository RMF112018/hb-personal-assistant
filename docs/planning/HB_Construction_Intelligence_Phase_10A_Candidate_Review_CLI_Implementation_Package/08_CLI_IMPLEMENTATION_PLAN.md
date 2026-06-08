# 08 CLI Implementation Plan

## Likely target file

`src/hb_assistant/cli/second_brain.py`

Reconfirm current command organization before editing.

## Review app handling

A top-level `review_app` already exists. Add candidate review commands to it only after confirming no naming collision with existing commands.

## Required commands

- `review list`
- `review show`
- `review accept`
- `review ignore`
- `review reject`
- `review summary`

## Recommended commands

- `review snooze`
- `review edit`
- `review export`

## CLI output

For `--json`, emit stable JSON with:

- `command`
- `ok`
- action-specific payload
- `guardrails`
- `warnings`
- `db_path` if existing CLI convention permits it

For non-JSON, keep output concise and redacted. Do not print raw source material.

## Error behavior

Unknown candidate ID:

- exit nonzero;
- emit safe JSON when `--json` is set;
- do not print SQL or stack traces unless existing debug conventions explicitly allow it.

Invalid enum:

- fail before DB update;
- show allowed values.

Ambiguous candidate ID found in both tables:

- require `--candidate-type`.

## DB path handling

All commands should support `--db <path>` consistent with `extract-packets`.
