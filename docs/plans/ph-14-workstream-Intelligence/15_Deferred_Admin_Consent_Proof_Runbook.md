# 15 — Deferred Admin Consent Proof Runbook

## Objective

Provide the exact closeout process once Microsoft tenant/admin consent is granted.

## Preconditions

- Admin consent granted for required delegated read scopes.
- Local repo is clean or all local changes are committed.
- Application Support paths are writable.
- No stale token cache state should be trusted.

## Commands

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -20

.venv/bin/hb-assistant auth clear-cache --json
.venv/bin/hb-assistant auth login --json
.venv/bin/hb-assistant auth status --json
.venv/bin/hb-assistant diagnostics graph --safe --json
.venv/bin/hb-assistant diagnostics proof delegated-graph --json
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
```

## Expected Success

- Delegated login succeeds.
- Token classification is delegated.
- Effective MSAL scopes exclude `openid`, `profile`, and `offline_access`.
- `/me` probe succeeds.
- Mail metadata proof succeeds.
- Bounded body retrieval succeeds without persistence of raw body.
- Calendar proof succeeds.
- Attachment metadata proof succeeds.
- Drive/file metadata proof succeeds.
- Controlled eligible file download proof succeeds only if allowed by current safety gates.
- App-only runtime use remains rejected/non-used.
- Sensitive scan remains clean.

## If A Failure Occurs

Use `04_Blocker_Taxonomy_And_Admin_Consent_Closeout_Plan.md` to classify the failure. Do not guess.

## Evidence To Commit

Recommended path:

```text
docs/evidence/delegated-graph-proof-closeout/
```

Required files:

- `auth-login.json` or redacted summary;
- `auth-status.json`;
- `diagnostics-graph-safe.json`;
- `delegated-graph-proof.json`;
- `sensitive-scan.json`;
- `summary.md`;
- updated README/architecture acceptance status.

## Final Classification

If all proof criteria pass:

```text
ACCEPTED_WITH_DELEGATED_GRAPH_PROOF_COMPLETE
```

If admin consent is still missing:

```text
CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER
```
