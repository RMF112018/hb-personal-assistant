# Addendum Prompt 05 Known Issues

**Scope note**: This file only reflects the scope of Addendum Prompt 05 (body mention beyond preview + prerequisite env diagnostics for truthful classification). Unrelated items from prior remediation or gap-closure/ are intentionally excluded.

## Phase 0 Update (2026-05-26)
- **Paths resolved (green)**: In this session run, `hb-assistant diagnostics paths --json` (07 + 23) shows **all paths writable: true**, chmod_ok true, no failures. This differs from P04 evidence (EPERM). No manual sudo repair steps from the runbook were needed; state was already (or became) good. `ensure_dirs` behavior validated.
- **DNS remains hard blocker**: Confirmed via 12-17 (scutil/dig/nslookup/curl/ping all fail for login.microsoftonline.com and tenant endpoint). Auth status (18), graph (21), proof (22) all hit network resolution before token or any Graph response.
- **Classification impact**: With paths now green but network preventing Graph steps, delegated proof `blocked_no_token` is truthfully **external network/DNS infra** (not "missing Mail.Read delegated permission"). Meets the "path-ready + no Graph responses reached" criteria for external label. Still cannot claim "permission gap" without reaching MS responses.

## Open (carried)
- Delegated auth/Graph blocked at DNS resolution for login.microsoftonline.com (NameResolutionError). Prevents token acquisition and any Graph step responses in proof.
- Therefore delegated-graph proof remains `blocked_no_token` (cannot yet be classified as pure MS permission blocker — correctly labeled external infra given path green).

## Classification Rules (re-stated for this prompt)
Per P04/P06 spec: External/manual blocker label **only** after:
- path readiness green (writable true for auth/db/etc.), **AND**
- token usable (or login succeeds), **AND**
- proof runner reaches Graph and receives actual Graph HTTP status responses.

If DNS or path prevents reaching Graph: classify as network/env infra (still external, but distinct from "missing delegated Mail.Read consent").

## To Be Updated Live
- Any new issues discovered during env repair attempts or P05 implementation (e.g., HTML stripper edge cases, schema migration impact on existing tests, etc.).
- Root cause of EPERM (ACLs? chflags? volume policy? org profile?) once `ls -lde` + `stat` + repair outputs analyzed.

**Status**: Prompt 05 COMPLETE. Body mention beyond-preview capability delivered + validated. No new code-level blockers introduced. DNS remains the only external blocker for full delegated proof (documented).