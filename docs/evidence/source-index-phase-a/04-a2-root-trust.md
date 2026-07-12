# A2 — Root-specific client trust (fail-closed only)

**Checkpoint:** A2 (fourth sub-phase of Phase A). **Parent commit:** A3 corrective `073a3a71`.
**Branch state after this checkpoint:** GREEN (all new tests pass; only disclosed pre-existing baseline
defects fail). **No push / PR / merge / force.** Posture: **fail-closed only** — no advisory retrieval.

## Defect addressed (A2 hypothesis, verified on `origin/main` `9c27839b`)

Serving paths gated on root-key **existence only**, never readiness: `search`/`list`/`metadata` returned
indexed items for any existing root regardless of policy certification, reconciliation, or freshness;
`source_file_metadata` had no root gate at all (`del config`); `read_status="live_readable"` was set from
indexed metadata with **no live probe**; the health aggregate `safe_for_client_answering = any(...)` let one
safe root imply universal safety; configless roots defaulted `enabled=True, sensitive=False` (fail-open); and
`SourceWatcher.start()` gated only on the config bit + lease. The rich per-root trust vocabulary existed in
health but was reporting-only.

## Design implemented

**One shared trust authority; every client operation consumes it; serving fails closed.**

1. **Shared authority** — new `src/hb_assistant/obsidian_mcp/source_root_trust.py`:
   - `evaluate_root_trust(RootTrustInputs) -> RootTrustDecision` is a **pure** function reproducing health's
     policy/index/completeness computation verbatim, then layering A2 authorization + structure-readiness +
     trust-state gating. Health builds inputs from its batch loads; serving/watcher use `load_root_trust(...)`
     (single-root gather → same pure evaluate) so all reach **byte-identical verdicts from one authority**.
     `load_root_trust` fails **closed** on any exception (returns a blocked decision, never raises).
   - **`RootTrustDecision` contract:** `root_key`, `trust_state ∈ safe|blocked|unverified|denied`,
     `authorization_state ∈ authorized|unverified|denied`, `enabled`, `sensitive`, `sensitivity_known`,
     `safe_for_path_lookup`, `safe_for_live_read`, `safe_for_content_answering ∈ none|partial|complete`,
     `policy_verification ∈ current|stale|uncertified|unavailable`, `generation_status`,
     `reconciliation_complete`, `structure_mapping_resolved`, `structure_key`, `structure_ready`,
     `index_only_available`, `freshness_status`, `metadata_completeness_state`, `content_completeness_state`,
     `watcher_ready`, `reason_codes[]`. No `advisory` state.
   - **Reason codes:** `root_disabled`, `authorization_unverified`, `policy_uncertified`, `policy_stale`,
     `policy_unavailable`, `index_layers_unready`, `freshness_unknown`, `sensitive_root`,
     `structure_data_unready`, `structure_mapping_unavailable`, `unknown_root`.
   - **`trust_state` precedence (fail-closed):** `denied` (configured+disabled) → `unverified`
     (configless) → `blocked` (freshness unknown / policy not current / index layers unready) → `safe`.
     `safe_for_client_answering == (trust_state == safe)` — a resolved mapping alone never makes a root safe.

2. **Mapping-resolved vs structure-ready (binding clarification honored).** `structure_mapping_resolved` is
   the A3 fact (canonical resolver produced a key). `structure_ready` is now **operational**: mapping
   resolved **AND** structure backend available **AND** folder ingestion exists **AND** watcher/run-state
   ready. The A3 health field `structure_ready` was retained as the operational field and
   `structure_mapping_resolved` added as the compatibility field carrying the old meaning (two A3 tests
   updated to assert `structure_mapping_resolved`).

3. **Serving wired (fail-closed)** — `source_connector_service.py`:
   - **search/list** gate on `decision.safe_for_client_answering`. An explicitly requested unsafe root →
     `blocked_root_unready` envelope (`items:[]`, `authoritative:false`, embedded `root_readiness`); an
     unknown root → `unknown_root` envelope; a safe root → `ok` with `authoritative:true` + `root_readiness`.
     **Unscoped** search restricts to safe roots, filters items to `safe_root_keys`, and discloses
     `excluded_root_keys` + sanitized `excluded_root_readiness` (one safe root never implies universal safety;
     all-unsafe → `blocked_root_unready`).
   - **metadata** blocked for an unsafe root — a minimal readiness envelope only, **no** advisory item
     metadata (`del config` removed; now gates on the source's root).
   - **read** (`source_content_provider.py`) evaluates root trust **before any filesystem access**; an
     untrusted or sensitive root falls back to the bounded indexed excerpt (`reason:"root_not_trusted"` +
     `root_readiness`); the bounded excerpt (`max_chars`) is unchanged (no complete-file retrieval).
   - **configless roots** now emit `authorization_state:"unverified"`, `sensitivity_known:false`,
     `sensitive:null`, `authoritative:false` — never `enabled=true, sensitive=false`.

4. **`read_status` semantics corrected** — `source_project_number.py`: the non-probed default
   `"live_readable"` becomes the capability label `"read_capability_known"`, plus canonical fields
   `live_readability:"unverified"` and `live_read_performed:false`. Statically-unsupported formats keep
   `read_status:"unsupported_metadata_only"` (the sole internal ranking consumer keys off this value) with
   `live_readability:"unsupported"`. **Inventory (complete):** the only load-bearing coupling is entirely
   inside `obsidian_mcp` (producer `match_explanation_for_row` → ranking `rank_boost` + client serialization
   `source_connector_service`); no routing/gateway/manifest consumer, no test, and no fixture pins the
   `"live_readable"` string — so no contradictory legacy value survives.

5. **Health aggregate redefined** — `source_health_service.py`: the canonical routing signal
   `safe_for_client_answering` is now **`all_enabled_roots_safe`** = `bool(enabled_authorized_roots) and
   all(r.safe for enabled_authorized_roots)` — **non-vacuous** (zero enabled+authorized roots is NOT
   client-safe). Added `any_root_safe` (demoted, never routing), `all_enabled_roots_safe`,
   `zero_authorized_roots_is_not_client_safe`, `safe_root_keys`, `unsafe_root_keys`. Per-root health now
   consumes the shared authority (no independent trust logic) and additionally emits `trust_state`,
   `authorization_state`, `sensitivity_known`, `safe_for_live_read`, `trust_reason_codes`.

6. **Watcher startup enforcement** — `source_watch.py`: `SourceWatcher.start()` independently calls the
   shared authority so the `external_source_watch_enabled` bit + lease alone can no longer start the drain.
   **CORRECTED (A2 corrective #2):** the watcher now activates a root ONLY when it is
   `safe_for_watcher_activation` (bootstrapped + certified + reconciled + structure-data-ready). It fails
   closed (degraded, sanitized reason, no host paths) on trust unevaluable (`watcher_trust_unevaluable`),
   no authorized roots (`watcher_no_authorized_roots`), and — new — a required root that is not ready
   (`watcher_root_not_bootstrapped` / `watcher_policy_stale` / `watcher_reconciliation_incomplete` /
   `watcher_structure_data_unready`). This is **non-circular** because bootstrap is a separate,
   watcher-independent operation. Covered by the six watcher lifecycle tests; see
   `13-watcher-bootstrap-noncircular.md`. *(The prior claim that un-bootstrapped roots do not block startup is
   superseded.)*

7. **Client-visible read contract corrected + manifest re-frozen** — the `assistant_get_source` docstring
   overstatement was fixed in corrective #1, but the load-bearing defect was the canonical **manifest
   `purpose`** of `assistant_source_file_read`, which read the generic family fallback
   `"Indexed NAS source-file discovery."`. **CORRECTED (A2 corrective #2):** `tool_entry_manifest.py` now
   carries a proper `assistant_source_file_read` entry disclosing the real contract (bounded excerpt; no
   complete-file retrieval; safe root required; truncation / indexed fallback). The frozen manifest is a
   **SQLite row** recomputed from the live surface via the official generation path
   (`bootstrap_persisted_manifest` / `seed_frozen_schema_index`) — **no stored checksum was hand-edited**; the
   freshness guard compares live-rebuilt to stored dynamically (no hard-coded baseline). Freshness + parity +
   exposure-bridge tests pass (direct==gateway). **Regeneration diff (expected):** `semantic_surface_checksum`
   moves from `sha256:3eb81b4d…c4bf09fc` (origin/main) to `sha256:16af53d3…a53b72` — the change is confined to
   the one corrected `read` purpose; no other tool purpose drifted. See `11-manifest-semantic-diff.md` and the
   probe artifacts (`manifest_probe.py`, `manifest-checksum-{originmain,a2corrective2}.txt`).

## Files changed

| File | Change |
|---|---|
| `obsidian_mcp/source_root_trust.py` | **new** — shared `RootTrustDecision` authority + pure evaluate + single-root loader + readiness envelope |
| `obsidian_mcp/source_connector_service.py` | +168/−9 — search/list/metadata trust gates, unscoped safe-root filter, configless unverified, fail-closed envelopes |
| `obsidian_mcp/source_content_provider.py` | +13 — pre-FS root-trust gate on read |
| `obsidian_mcp/source_project_number.py` | +15/−2 — `read_status` capability semantics + `live_readability`/`live_read_performed` |
| `obsidian_mcp/source_health_service.py` | consumes shared authority; non-vacuous aggregate + new aggregate/per-root trust fields |
| `obsidian_mcp/source_watch.py` | +51 — independent watcher-startup trust enforcement |
| `nas_mcp/tool_registration.py` | +3/−2 — corrected `assistant_get_source` help (docstring-only) |
| `tests/test_source_root_trust.py` | **new** — 36 A2 tests (35 at the A2 checkpoint + 1 bootstrap↔watcher non-circularity regression added by the A2 corrective) |
| `tests/test_source_connector_service.py`, `tests/test_nas_mcp_source_connector.py` | positive paths now seed a certified-safe root; unknown-root tests assert the new envelopes |
| `tests/test_source_root_mapping.py` | 2 A3 assertions updated to `structure_mapping_resolved` (A2 semantics) |
| `docs/evidence/source-index-phase-a/` | `04-…`, `08-…`, `09-…`, `10-baseline-reconciliation-matrix.md`, `11-manifest-semantic-diff.md`, `12-phase-a-regression-evidence.md`, `13-watcher-bootstrap-noncircular.md`, `a2-prove-red.txt`, `a2-validation-{client-surface,cross-checkpoint,broad-source-index}.txt` |

`source_connector_service.py`/`source_content_provider.py`/`source_project_number.py`/`source_watch.py` are
NOT ruff-formatted on origin/main; their diffs are additive with no reformat churn. `source_root_trust.py`
(new) and `source_health_service.py` (formatted on origin) pass `ruff format --check`.

## Prove-red → prove-green
- **Prove-red** (`a2-prove-red.txt`): with A2 src reverted to the parent, `tests/test_source_root_trust.py`
  fails to import (`No module named source_root_trust`); the modified existing suites encode the new envelope
  contract and fail against parent code.
- **Prove-green** — three correctly-scoped artifacts (superseding the withdrawn, mislabeled
  `a2-validation-{focused,superset}.txt`; see the A2 corrective follow-up in `09-commit-lineage.md`). Totals
  below include this corrective's +1 non-circularity regression test:
  - **Cross-checkpoint** (`a2-validation-cross-checkpoint.txt`): **114 tests, 114 passed, 0 failed** — every
    test Phase A introduced through A2 (A1 19 + A3 25 + A2 36 + serving/parity). This is the authoritative
    "all Phase A tests introduced through A2 pass" run.
  - **Client-surface** (`a2-validation-client-surface.txt`): **153 tests, 152 passed, 1 failed** — the sole
    failure is the pre-existing `test_output_aliases_defined` baseline defect (`11 vs 10`).
  - **Broad source-index** (`a2-validation-broad-source-index.txt`): **261 tests, 256 passed, 5 failed** — all
    five are disclosed pre-existing baseline defects (v119/v120/v122, structure-cli, disambiguating-descriptions).
  - All 6 baseline failures are reconciled in `10-baseline-reconciliation-matrix.md` and reproduce on pristine
    origin/main (`a2-baseline-recon-originmain.txt`).

## Required-invariant coverage (selected A2 tests)
- Explicit unsafe root → `blocked_root_unready` (`items:[]`, `authoritative:false`, `root_readiness`):
  `test_explicit_unsafe_root_search_blocked`, `test_list_unsafe_root_blocked`, `test_metadata_unsafe_root_blocked`.
- Unscoped restricts + discloses: `test_unscoped_search_restricts_to_safe_and_discloses_excluded`,
  `test_unscoped_search_all_unsafe_returns_blocked`.
- Non-vacuous aggregate: `test_health_aggregate_all_safe_not_any_safe`, `test_zero_authorized_roots_is_not_client_safe`.
- Structure dependency: `test_mapping_resolved_is_not_structure_ready`.
- Read semantics: `test_read_status_no_live_claim_without_probe`, `test_read_checks_trust_before_fs_for_unsafe_root`,
  `test_read_sensitive_root_never_live`.
- Watcher startup fail-closed (A2 corrective #2 — the watcher itself enforces
  `safe_for_watcher_activation`): `test_watcher_start_before_bootstrap_fails_closed`,
  `test_watcher_start_blocks_policy_stale`, `test_watcher_start_blocks_reconciliation_incomplete`,
  `test_watcher_start_blocks_structure_data_unready`, `test_watcher_degrades_when_all_roots_disabled`,
  `test_watcher_degrades_on_unevaluable_trust`.
- Bootstrap is watcher-independent (non-circular, real `bootstrap()`): `test_bootstrap_succeeds_without_watcher`,
  `test_watcher_start_after_bootstrap_succeeds` — see `13-watcher-bootstrap-noncircular.md`.
- No absolute-path leak: `test_health_no_absolute_path_leak`, `test_unscoped_search_..._discloses_excluded`.
- Running corrective gen doesn't reopen trust: `test_running_corrective_generation_does_not_reopen_trust`.
- Direct == gateway: `test_direct_and_gateway_trust_agree` (single connector-service authority behind both).

## Static checks
`ruff check` all-passed on changed src + tests; `ruff format --check` clean on the formatted files; `mypy`
**Success: no issues found** on all 6 changed modules.

## Scope / safety
No source-file write or delete API added. No production mutation. No new remote/MCP write surface (tool NAMES
preserved; only a docstring corrected). No advisory retrieval. A4 not begun.
