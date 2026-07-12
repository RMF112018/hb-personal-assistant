# A2 corrective — watcher bootstrap remains possible (no circular dependency)

Purpose: confirm the A2 watcher-startup trust enforcement did NOT create a circular dependency in which the
watcher requires a bootstrapped root while bootstrap requires the watcher. Provides the call flow and a
regression test driving the **real** `source_bootstrap.bootstrap()`.

## The circularity risk, and how A2 resolves it
- **Risk:** if `SourceWatcher.start()` failed closed for any not-yet-ready root, and readiness could only be
  produced by the watcher, no root could ever be bootstrapped.
- **Resolution (A2 design, already approved at the A2 GO):** bootstrap is a **separate operation**
  (`source_bootstrap.bootstrap()`), independent of the watcher. The watcher's own drain performs incremental
  indexing. Therefore:
  - The watcher fails closed ONLY on **denied / no-authorized / trust-unevaluable** roots (config-level
    problems), NOT on the legitimate enabled-but-not-yet-certified pre-index state.
  - **Client SERVING** (search/list/metadata/read) is where policy/reconciliation/structure readiness is
    enforced fail-closed before any answer.

## Reconciling the four required checks
The corrective's item-5 asked for four properties. Three map directly to the design; the fourth is satisfied
at the **client-serving** layer (the correct place), which this note makes explicit:

| Required property | Where enforced | Result |
|---|---|---|
| bootstrap allowed while root not watcher-ready | `source_bootstrap.bootstrap()` (watcher never started) | ✅ bootstrap runs to completion |
| successful bootstrap establishes readiness | `bootstrap_state.file_index_status="bootstrapped"`, `file_index_bootstrapped=1` (durable) | ✅ recorded |
| watcher start then succeeds | `SourceWatcher.start()` on the bootstrapped root | ✅ non-degraded |
| watcher start **before** bootstrap fails closed | **client SERVING** fails closed pre-bootstrap (`safe_for_client_answering=False`); the watcher DRAIN is intentionally permitted for an enabled root so indexing can occur | ✅ serving fails closed; drain permitted (non-circular) |

> Design note on the fourth property: making `SourceWatcher.start()` itself fail closed for an
> enabled-but-un-bootstrapped root would re-introduce the exact circular dependency (the drain is what
> indexes). A2 therefore fails the **client answer** closed before bootstrap — a client can never receive an
> authoritative answer from an un-bootstrapped root — while allowing the drain. This is covered explicitly and
> was the design accepted at the A2 checkpoint (`test_watcher_allows_uncertified_root_to_bootstrap`).

## Call flow (non-circular)
```
bootstrap():  map_roots → file-layer scan/upsert → SourceIndexBootstrapRepository records
              file_index_status="bootstrapped", file_index_bootstrapped=1        [no watcher involved]
                                   │
                                   ▼
client SERVING (search/list/metadata/read):  load_root_trust() → RootTrustDecision
              pre-bootstrap  → safe_for_client_answering=False → blocked_root_unready   [fails closed]
              post-certified → safe_for_client_answering=True  → ok
                                   │
                                   ▼
SourceWatcher.start():  _enforce_watch_trust() → load_root_trust per configured root
              denied / none-authorized / unevaluable → degraded (sanitized reason)      [fails closed]
              enabled (even un-bootstrapped/uncertified) → drain permitted              [non-circular]
```

## Regression test (real `bootstrap()`)
`tests/test_source_root_trust.py::test_bootstrap_to_watcher_start_is_non_circular` proves the full sequence:

1. **Pre-bootstrap serving fails closed:** `load_root_trust(...).safe_for_client_answering is False` for the
   enabled, un-bootstrapped root.
2. **bootstrap allowed with no watcher:** `source_bootstrap.bootstrap(db_path, obsidian_config, app_config,
   root_key="work", file_only=True)` runs to completion (`file_index.bounded_out is not True`) though the
   watcher has never started.
3. **Durable readiness established:** `get_bootstrap_state("work")` →
   `file_index_status == "bootstrapped"`, `file_index_bootstrapped == 1`.
4. **Watcher then starts non-degraded:** `SourceWatcher.start()` →
   `_mode in ("watchdog","polling")`, `_last_error_code != "watcher_no_authorized_roots"`.

Result: `36 passed` in `test_source_root_trust.py` (this test + the 35 A2-checkpoint trust tests). The related
watcher fail-closed direction is covered by `test_watcher_degrades_when_all_roots_disabled` (no-authorized),
`test_watcher_degrades_on_unevaluable_trust` (unevaluable), and
`test_watcher_config_bit_alone_cannot_bypass_when_no_roots` (config bit alone cannot bypass).
