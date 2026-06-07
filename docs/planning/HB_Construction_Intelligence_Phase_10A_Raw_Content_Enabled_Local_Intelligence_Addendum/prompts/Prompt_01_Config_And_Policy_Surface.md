# Prompt 01 — Config and Policy Surface

## Objective

Add explicit raw-content policy config.

## Tasks

1. Add raw content config model fields.
2. Add YAML seed/defaults.
3. Add diagnostics output showing raw-content mode.
4. Support `email_calendar` mode first.
5. Keep external writeback disabled.

## Acceptance

- `hb-assistant diagnostics env --json` or new raw-content status shows raw mode.
- Config supports raw email and calendar content.
