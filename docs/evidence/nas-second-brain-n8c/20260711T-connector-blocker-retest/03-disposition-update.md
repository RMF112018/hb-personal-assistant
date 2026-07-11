# Connector re-test — disposition update after PR #301 deploy (fce2fe92)

The prior full-suite re-test scored **8.6/10 `CONNECTOR_VALIDATED_WITH_BLOCKERS`** against the
deployed runtime `eb9b9fdb`. PR #301 (merge commit **`fce2fe92`**) is now deployed and
live-verified. Evidence: `02-p1-deploy-verification.json`.

## Finding disposition (updated)

| Finding | Prior | Now |
| --- | --- | --- |
| Runtime/manifest commit mismatch | Resolved | Resolved (re-aligned at `fce2fe92`, manifest v11) |
| Promotion-bundle ID truncation | Resolved | Resolved |
| Negation disabling safe reads | Resolved | Resolved |
| Action-stage discovery sequence | Resolved | Resolved |
| Mixed NAS/vault retrieval | Resolved | Resolved |
| **Source-index health unavailable** | **Open — blocker** | **RESOLVED** — tool executes, returns structured health, agrees with source_status |
| **Manifest-freshness semantic routing** | **Open** | **RESOLVED** — routes to `manifest_freshness_check` |
| Stale 78-tool/13-group prose | Open | **RESOLVED** — dynamic counts (14 groups) |
| Execution-aware attestation absent | Open | **RESOLVED** — `pa_tool_surface_runtime_attestation`, 146/146 pass, 0 fail |
| AI-output authorization classification | Not re-proven | **RESOLVED** — `assistant_output_*` classify as `staged_write`; parity test added |
| Staged-output cancellation absent | Open | Deferred → Phase 3c (follow-on PR) |
| Source-search latency (~24 s) | New concern | Deferred → Phase 3b (missing `source_intelligence_metadata(fts_rowid)` index; follow-on PR + Deploy 2) |
| Empty-fixture families | Not fully testable | Deferred → Phase 3d (test-infra PR) |
| Nested-repo RO hardening | (adjacent) | Deferred → Phase 3a (follow-on PR) |

## Net

Both **release blockers are cleared live**, plus the catalog-prose, execution-attestation, and
AI-output-classification findings. Remaining items are **non-blocking quality follow-ons**
(latency, cancellation/void lifecycle, fixtures, RO hardening), tracked for Phase 3 with their
own PRs; the search-latency and any status/cancellation-tool changes require a second deploy.
