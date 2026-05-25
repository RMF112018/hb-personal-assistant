# Addendum Prompt 02 Known Issues

## Remaining runtime blockers observed in this run

1. `hb-assistant auth status --json` exited 1 due network name resolution to Microsoft login endpoint in this environment.
2. `hb-assistant diagnostics graph --safe --json` exited 1 due the same network name resolution issue.

These are not `Operation not permitted` Application Support permission crashes; both commands emitted valid JSON and no traceback.
