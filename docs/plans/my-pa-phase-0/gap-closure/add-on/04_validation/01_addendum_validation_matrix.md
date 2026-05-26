# Addendum Validation Matrix

## Required Final Commands

```bash
git status --short
git rev-parse HEAD
python -m pytest
ruff check .
mypy src
hb-assistant --version
hb-assistant auth status --json
hb-assistant diagnostics env --json
hb-assistant diagnostics paths --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics automation --json
hb-assistant diagnostics scan-sensitive --repo . --json
hb-assistant files sample --json
hb-assistant files ingest --dry-run --json
hb-assistant run morning --dry-run --json
```

## Gate Classifications

| Gate | Required for ACCEPTED | Notes |
|---|---:|---|
| pytest | Yes | No unmarked failures. |
| ruff | Yes | Must be exit 0. |
| mypy | Yes | Must be exit 0 under configured scope. |
| auth status | Yes | May report no token only if structured and path-ready. |
| diagnostics paths | Yes | Must identify writable/readiness state. |
| graph safe | Yes | Must not fail due local path issue. |
| delegated proof | Yes or external blocker | External blocker must be Microsoft/auth specific, not local path. |
| automation diagnostics | Yes | launchd may be not installed, but readiness must be truthful. |
| sensitive scan | Yes | No secret values emitted. |
| files ingest dry-run | Yes | Must not traceback; no candidates is acceptable. |
| run morning dry-run | Yes | Must not traceback; skipped stages acceptable if structured. |

## Accepted Status Values

### ACCEPTED

All gates pass and delegated proof passes.

### CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_BLOCKER

All local gates pass. Delegated proof reaches Graph/auth state but is blocked only by Microsoft permission/admin/login condition.

### NOT_ACCEPTED

Any local code, path, lint, DB, or command-shape failure remains.
