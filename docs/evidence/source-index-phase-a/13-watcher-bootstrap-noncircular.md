# A2 — watcher startup enforces the authorized trust boundary (fail closed, non-circular)

Purpose: prove `SourceWatcher.start()` **itself** fails closed for a required root that is not fully ready,
while bootstrap remains an independent operation — so there is no circular dependency.

## Correction over the prior pass
A2 corrective #1 relocated the required fail-closed behavior to client serving and let the watcher drain an
enabled-but-uncertified root. That did **not** satisfy the A2 contract. This pass makes the watcher enforce the
boundary directly: it activates a root ONLY when the shared authority reports
`safe_for_watcher_activation == True`.

## New canonical field (shared authority — no ad-hoc watcher policy)
`RootTrustDecision.safe_for_watcher_activation` (in `source_root_trust.py`) is derived from the same decision:

```
safe_for_watcher_activation == (
    trust_state == "safe"          # authorized + enabled + policy current + freshness known + index layers ready
    and reconciliation_complete    # generation reconciliation finished
    and structure_ready            # structure mapping resolved + backend up + folder map exists + run-state ready
)
```

`RootTrustDecision.watcher_activation_block_reason` maps every not-ready state to one sanitized code:
`watcher_root_not_bootstrapped` (no/failed generation, freshness unknown, index layers unready),
`watcher_reconciliation_incomplete` (running/partial/reconcile_pending generation),
`watcher_policy_stale` (completed generation whose policy fingerprint drifted),
`watcher_structure_data_unready` (safe file layer but no structure data), `watcher_root_denied`.

`SourceWatcher.start() → _enforce_watch_trust()` now requires EVERY configured+enabled root to be
`safe_for_watcher_activation`; otherwise it degrades (no drain thread) with the decision's block reason.
Existing fail-closed conditions are retained: `watcher_no_authorized_roots`, `watcher_trust_unevaluable`,
`watcher_lease_error`/`watcher_not_owner`. The watcher takes an injected `app_config` so its trust evaluation
is deterministic and identical to the health projection.

## No circular dependency (the key argument)
Bootstrap is a SEPARATE, watcher-independent operation. A full `source_bootstrap.bootstrap()` writes a
`completed` scan generation (matching the policy fingerprint) AND structure data — establishing durable
readiness — with the watcher never running. So:

```
SourceWatcher.start() before bootstrap  → degraded (watcher_root_not_bootstrapped)   [fails closed]
source_bootstrap.bootstrap()            → runs WITHOUT the watcher                    [independent]
                                        → writes completed generation + structure     [durable readiness]
SourceWatcher.start() after bootstrap   → activates (watchdog/polling)                [non-circular]
```

Blocking the watcher pre-bootstrap cannot deadlock, because the thing that makes a root ready is bootstrap,
which does not need the watcher.

## Regression tests (real `source_bootstrap.bootstrap()`), in `test_source_root_trust.py`
| Test | Proves |
|---|---|
| `test_watcher_start_before_bootstrap_fails_closed` | watcher degrades with `watcher_root_not_bootstrapped` for an enabled, un-bootstrapped root |
| `test_bootstrap_succeeds_without_watcher` | a REAL bootstrap runs with no watcher, writes a `completed` generation, and only then is `safe_for_watcher_activation` True (reframed from the former "allows uncertified to bootstrap") |
| `test_watcher_start_after_bootstrap_succeeds` | after a full bootstrap the watcher activates non-degraded |
| `test_watcher_start_blocks_policy_stale` | a certified root whose fingerprint later drifts degrades with `watcher_policy_stale` |
| `test_watcher_start_blocks_reconciliation_incomplete` | a generation regressed to `reconcile_pending` degrades with `watcher_reconciliation_incomplete` |
| `test_watcher_start_blocks_structure_data_unready` | a file-only-bootstrapped root (trust safe, no structure data) degrades with `watcher_structure_data_unready` |

Retained: `test_watcher_degrades_when_all_roots_disabled` (`watcher_no_authorized_roots`),
`test_watcher_degrades_on_unevaluable_trust` (`watcher_trust_unevaluable`),
`test_watcher_config_bit_alone_cannot_bypass_when_no_roots`. Trust suite: **40 passed**.

## Blast radius on existing watcher suites (aligned, not bypassed)
The stricter gate means drain-mechanics tests must run on a READY root. Four existing tests that start the
drain on an unseeded root now seed real readiness (a full `bootstrap()` + injected `app_config`) instead of
starting on a pre-index root:
`test_obsidian_source_watch.py::{test_polling_fallback_when_watchdog_unavailable, test_watchdog_indexes_on_create}`,
`test_obsidian_source_watch_ownership.py::{test_second_watcher_runs_degraded, test_owner_released_on_stop_lets_next_acquire}`.
Contention/lease/redaction tests are unchanged (they fail closed earlier, at the lease step). Combined watcher
lifecycle + ownership + automated-refresh: **79 passed**.
