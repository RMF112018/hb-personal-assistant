# 11 — Risk & rollback

Per-checkpoint residual risk and how to revert. Every checkpoint is an isolated local commit on
`fix/source-index-phase-a-correctness-trust`; any one can be reverted independently.

## Residual risks (classified)

| # | Risk | Severity | Mitigation | Residual |
|---|---|---|---|---|
| R1 | **A1** false-negative deletion: a genuinely-absent note is not reaped when a scan is uncertain | Low (intended safe failure) | Deletion reconciles only on a certified-complete traversal; operator has a one-shot `vault-reconcile --allow-confirmed-empty --confirm` recovery | Stale index rows persist until a clean scan; never data loss |
| R2 | **A2** manifest/checksum churn breaks a consumer | Low | Checksum regenerated canonically; direct/gateway parity fixtures + freshness guard gate it | A consumer pinning the old checksum must re-freeze |
| R3 | **A2** over-blocking a safe root (false "unsafe") | Low | Trust reuses health's proven computation verbatim; `safe_for_client_answering` is the same predicate health already reported | A misconfigured root fails closed (blocked), never fails open |
| R4 | **A4** V125 migration risk | Very low | Additive, idempotent, upgrade-safe, integrity-checked (`06`); no FK/cascade | None observed |
| R5 | **A4** a poison file wrongly quarantined (transient misclassified as permanent) | Low | Bounded retry threshold (default 3, configurable ≥1); `resolve_observed` clears a below-threshold retry on any clean observation (F-03 preserved) | A transient that persists ≥ threshold quarantines; operator retry resolves it |
| R6 | **A4** quarantine never resolves → root permanently unsafe | Medium (by design — fail closed) | Operator `quarantine-retry` (bounded, confirmed) resolves on a trustworthy observation; policy-fingerprint change or explicit restart also lift the block | Intended: an unresolved poison file keeps the root non-authoritative until operator action |
| R7 | Test-file schema-assertion edit (the three `== 123` → `== LATEST_SCHEMA_VERSION`) touches non-Phase-A files | Low | Isolated, drift-proof change; justified by the CI-gate requirement (`08`, `10`); no production code affected | None |

## Rollback procedures

- **A1** — revert `e1a333ec` / `1d58d123`: the deletion gate is removed; indexing behavior is otherwise
  unaffected (reconciliation returns to its prior authority). No schema change to undo.
- **A3** — revert `80d089ee` / `073a3a71`: health returns to its prior (fuzzy) mapping. No schema change.
- **A2** — revert `554c4b90` / `351c7e4c` / `3c5d7738`: serving/watcher return to prior behavior; re-run the
  manifest freeze to restore the old checksum. No schema change.
- **A4** — revert `73e4e2fb`: the quarantine wiring is removed. **V125 is additive** — an older image simply
  ignores the `source_index_scan_quarantine` table (demonstrated in `06`, rollback coexistence). No downgrade
  migration is needed or provided; the dormant table can be left in place.
- **CI gate** — delete `.github/workflows/source-index-gate.yml` + `scripts/ci_source_index_gate.sh`; no
  runtime effect.

## Rollback safety notes

- No schema **downgrade** is implemented or claimed. V125 rollback safety rests solely on the additive
  table being ignored by older code (tested in `06`).
- No production mutation was performed at any checkpoint: no deploy/rebuild/restart, no prod DB/MCP snapshot
  write, no watcher/bootstrap/reconcile enablement against a live root, no write to any configured NAS root or
  the live vault. All validation used scratch SQLite + temp roots + mocked FS failures.
- No source-file write or delete capability exists anywhere in the branch (independent audit, `15`): "delete"
  is always index-state only.
