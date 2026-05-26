# Defect Fix: Reserved Scopes in Delegated MSAL Login

**Date**: 2026-05-26
**Root cause identified**: `offline_access` (and `openid`/`profile`) were included in scopes passed to MSAL `PublicClientApplication` for delegated login. MSAL explicitly rejects these reserved scopes.

**Fix**: Central `sanitize_delegated_scopes()` + `AuthScopePolicy` (scope_policy.py) + wiring in DelegatedAuthProvider. Diagnostics now expose configured vs effective vs removed.

**Impact on prior classification**:
- Previous P04/P06 evidence classified the blocker as "DNS/network".
- This is superseded. The reserved-scope defect was the actual (and now fixed) cause preventing `auth login` and subsequent delegated Graph proof steps.

**New acceptance** (per user_query rules):
`NOT_ACCEPTED_FOR_DELEGATED_GRAPH_PROOF — RESERVED_SCOPE_AUTH_DEFECT`

This label remains until:
- `hb-assistant auth login --json` succeeds (or returns specific MS auth error), **and**
- `diagnostics proof delegated-graph --json` reaches real Graph responses and either passes or shows only permission gaps.

**Validation performed**: See command-results/ in this dir + terminal runs of the full matrix from the Prompt 06 spec.

---

## State Update (Post-Scope-Fix Verification)

**Date of update**: 2026-05-26

After the reserved scope sanitizer was implemented and committed:

- Delegated auth flow **now reaches** Microsoft consent/permission enforcement (confirmed via `diagnostics graph --safe --json` and proof output).
- `auth status --json` now correctly surfaces:
  - `configured_scopes`
  - `effective_msal_scopes` (reserved scopes stripped)
  - `removed_reserved_scopes`
- All local gates remain green:
  - Application Support paths: fully writable
  - DB readiness: no errors
  - Static validation (ruff, mypy): clean
  - Dry-run commands: structured output

**Current Blocker Classification**:
This is now an **external tenant/admin-consent blocker**, not a local implementation defect.

The reserved-scope code defect has been resolved. The remaining step is admin approval of the required delegated Microsoft Graph permissions (Mail.Read, Calendars.Read, Files.Read.All, etc.) in the tenant (0e834bd7-628b-42c8-b9ec-ecebc9719be4).

### TODO Next Commands After Admin Approval

Once delegated permissions are approved:

```bash
source .venv/bin/activate

hb-assistant auth login --json
hb-assistant auth status --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics scan-sensitive --repo . --json
```

Commit when complete.
