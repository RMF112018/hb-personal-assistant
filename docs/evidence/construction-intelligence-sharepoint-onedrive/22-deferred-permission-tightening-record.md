# 22 — Deferred Permission-Tightening Record (Graph Files)

**Status:** OPEN — DEFERRED. **Do not resolve in Phase 06 (SharePoint/OneDrive File Intelligence).**
**Owner decision:** User explicitly instructed that over-broad Graph file permissions remain
deferred for this phase; remediation is documented, not performed.

This is the standing record for the deferred over-broad Microsoft Graph file/site permission posture.
It is referenced from `00-repo-truth-baseline.md` §4, `01-official-graph-files-research.md` §7, and
`02-graph-auth-permission-posture-deferred.md`.

---

## 1. The Deferred Risk

The tenant has consented, and runtime config requests, **write/management-capable** Graph file and
site scopes that exceed the read-only behavior this phase requires:

- **Runtime configured (delegated):** `Files.ReadWrite.All` (`config/models.py`);
  resolver also requests `Sites.Read.All` + `Files.ReadWrite.All`
  (`construction/graph/resolver.py`).
- **Tenant-consented (app registration), observed Prompt 00:** `AllSites.FullControl`,
  `Files.ReadWrite.All`, `Sites.FullControl.All`, `Sites.Manage.All`, `Sites.ReadWrite.All`,
  `Sites.Selected`, `Group.ReadWrite.All`.

If these scopes were exercised for writes, they would permit upload, metadata edit, delete, move,
copy, sharing-link creation, permission changes, checkout/checkin, and retention/sensitivity
labeling across SharePoint and OneDrive.

## 2. Why It Is Deferred

Per the package (`12_DECISION_REGISTER.md` → Deferred Decisions): *"Tighten broad Graph file
permissions → Later security phase — User explicitly instructed that over-broad permissions remain
deferred."* The phase therefore separates **behavior-level production readiness** (in scope) from
**tenant/application permission minimization** (deferred).

## 3. Compensating Controls (active now — independent of granted scopes)

The system is **behaviorally read-only** regardless of the broad grant, proven by
`graph files no-writeback-proof` and enforced at multiple layers:

- `SourceLocation.read_only: Literal[True]` + `DefaultPolicies` (no vault copy / no full text).
- SQLite `CHECK(read_only = 1)` and writeback-forbidding CHECK constraints.
- `graph/files_endpoint_guard.py` refuses any non-GET / mutation endpoint before HTTP.
- `tests/test_mutation_lockout.py` (extended) + files endpoint-contract/guard tests.
- `AppConfig.security.microsoft_365_writeback_enabled == False`.
- No `@microsoft.graph.downloadUrl` / token / raw-delta-link persistence.

## 4. Future Remediation (NOT performed in this phase)

When the later security phase takes this up, the intended target is **least-privilege read-only**:

| Current (deferred) | Target (future) |
| --- | --- |
| `Files.ReadWrite.All` | `Files.Read.All` (or `Files.Read.Selected`) |
| `Sites.ReadWrite.All` / `Sites.Manage.All` / `Sites.FullControl.All` / `AllSites.FullControl` | `Sites.Read.All` (or `Sites.Selected` read-only) |
| `Group.ReadWrite.All` | remove if unused, else `Group.Read.All` |

Remediation steps (future): update the Entra app registration consented scopes → narrow
`config/models.py` `delegated_scopes` and resolver scopes → re-run the delegated Graph capability
proof → update `test_mutation_lockout` scope-expectation assertions → re-attest.

## 5. Acceptance / Closeout Constraint

This phase **must not** be closed by attempting permission tightening, and **must not** claim the
permission risk resolved. It is resolved only when a future security-phase remediation lands with its
own evidence. Until then this record stays **OPEN — DEFERRED**.
