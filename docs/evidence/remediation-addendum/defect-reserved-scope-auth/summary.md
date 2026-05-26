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
