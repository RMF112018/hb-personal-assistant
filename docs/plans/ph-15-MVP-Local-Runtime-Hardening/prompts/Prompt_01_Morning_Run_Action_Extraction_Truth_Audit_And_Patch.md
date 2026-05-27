# Prompt 01 — Morning Run Action Extraction Truth Audit and Patch

You are the local code agent operating in the `RMF112018/hb-personal-assistant` repository.

Do not work in `hb-intel`.

Do not re-read files that are still in your current context or memory. Use targeted greps and precise reads.

Prompt 9 / delegated Graph proof remains deferred pending Microsoft Graph admin consent. Do not work around that blocker with app-only runtime mail/calendar access.

Before modifying files, run the required starting checks and capture the actual repo state.

Expected starting HEAD for this phase:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`


## Objective

Verify that `hb-assistant run morning` actually invokes implemented action extraction and does not silently report an OK stage with zero work due to a method mismatch.

## Required Greps

```bash
grep -R "extract_candidates" -n src/hb_assistant/automation src/hb_assistant/actions tests || true
grep -R "ActionService" -n src/hb_assistant/automation src/hb_assistant/actions tests || true
grep -R "def extract" -n src/hb_assistant/actions || true
```

## Required Patch If Needed

If orchestrator calls a nonexistent or wrong `ActionService` method, patch it to call:

```python
actions = ActionService(store=self.store).extract(dry_run=dry_run)
```

The stage count must reflect actual candidates returned.

## Tests

Add or update tests proving:

- seeded bounded signals generate nonzero action candidates;
- `run morning --dry-run --json` action stage reports the correct count;
- Graph missing/consent pending does not prevent local action extraction;
- failures are isolated and truthfully reported.

## Evidence

Create:

```text
docs/evidence/mvp-local-runtime/01-morning-run-action-extraction-audit.md
docs/evidence/mvp-local-runtime/outputs/run-morning-action-stage.json
```

## Commit Message

```text
fix(mvp-runtime): ensure morning run invokes action extraction service
```
