# 17 — Session Handoff Template

Use this at the end of every local-agent session.

```md
# Session Handoff — HB Personal Assistant Phase 14

## Branch / Commit
- Repository:
- Branch:
- Starting HEAD:
- Ending HEAD:
- Working tree status:

## Objective Executed
- Prompt number/title:
- Scope completed:
- Scope intentionally deferred:

## Files Changed
- Added:
- Modified:
- Deleted:

## Validation Run
| Command | Exit | Result / Notes |
|---|---:|---|
| `.venv/bin/python -m pytest` | | |
| `.venv/bin/ruff check .` | | |
| `mypy src` | | |
| `hb-assistant diagnostics scan-sensitive --repo . --json` | | |

## Evidence Created
- Evidence directory:
- Summary files:
- Sensitive scan file:

## Current Blockers
- Admin consent:
- Local path/DB:
- Code/test:
- Other:

## Acceptance Classification
- Current classification:
- Rationale:

## Next Recommended Prompt
- Prompt:
- Why:
- Notes for next agent:

## Safety Confirmation
- No Microsoft 365 writeback added:
- No full email bodies persisted:
- No full file contents persisted:
- No secrets/tokens/PEMs committed:
```
