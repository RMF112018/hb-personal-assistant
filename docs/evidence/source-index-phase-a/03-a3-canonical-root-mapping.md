# A3 — Canonical structure-root mapping authority

**Checkpoint:** A3 (third sub-phase of Phase A). **Parent commit:** A1 follow-up (`1d58d123`).
**Branch state after this checkpoint:** GREEN (all new tests pass; only the disclosed pre-existing baseline
defects fail). **No push / PR / merge / force.**

## Defect addressed (A3 hypothesis, verified on `origin/main` `9c27839b`)

Bootstrap and watcher shared the canonical `resolve_structure_key`
(`source_bootstrap.py`: explicit-map → exact-key → None), but **health reimplemented FUZZY matching**
(`source_health_service.py:183-191`): a `key.replace("syn-", "")` prefix strip, a bidirectional substring
loop (`sk in key or key in sk`), and first-row-wins. So the same file root resolved to *different* structure
roots depending on the caller — maximal divergence for colliding keys like `work` / `syn-work` /
`work-backup`. The explicit map was also **not persisted** (only the CLI flag `--structure-root-map-json`),
so normal operation was exact-only (bootstrap/watcher) versus fuzzy (health). No test covered the divergence.

## Design implemented

One canonical resolver, one durable authority, one normalizer — health's fuzzy path removed.

1. **New canonical resolver** — `src/hb_assistant/obsidian_mcp/source_root_mapping.py` (new, 151 lines):
   - `resolve_structure_mapping(file_key, structure_keys, *, config_map=None, cli_override=None)` returns a
     frozen `StructureRootMapping(file_key, structure_key, reason)`. **Deterministic precedence:**
     `cli_override` → `config_map` (explicit) → exact NORMALIZED key match → `unmapped`. Reason/provenance
     codes: `cli_override`, `explicit_map`, `exact_match`, `unmapped`, `invalid_explicit_map`,
     `ambiguous_configuration`.
   - **No** substring / prefix / suffix / case / first-row fallback anywhere.
   - **Fail-closed:** never raises on degenerate input; an invalid explicit target (target not in the
     structure namespace) → `invalid_explicit_map` (unmapped); a source key that normalizes-collides with a
     conflicting target → `ambiguous_configuration` (unmapped). A CLI-vs-config *difference* is resolved by
     precedence and is **not** flagged ambiguous (it carries `cli_override` provenance).
   - **Many-to-one is allowed** (several file roots → one structure root); verified not prohibited by the
     structure repository, so it is preserved.
   - `normalize_root_key` is the **one shared normalizer** (NFC + strip, deliberately no case folding),
     applied before duplicate detection and by config validation, lookup, and health serialization alike.
   - `validate_structure_root_map(config_map, structure_keys)` surfaces operator-facing config errors
     (`ambiguous_configuration`, `invalid_explicit_map`); many-to-one never reported.

2. **Durable authority (sole)** — `SourceStructureConfig.structure_root_map: dict[str,str]`
   (`config/models.py`), a validated application-config field available to bootstrap, health, watcher, and
   CLI. A `@field_validator` rejects normalized-key collisions with conflicting targets at config-load time.
   The CLI `--structure-root-map-json` flag is demoted to a **one-operation higher-precedence override**, not
   a competing authority.

3. **Ephemeral-override durability guard** — `source_bootstrap.resolve_run_state` now computes the
   **canonical** mapping from config (`scan_roots` + `structure_root_map`); if a CLI override is supplied and
   its resolved `structure_key` **differs** from canonical, watcher readiness fails closed with the new
   `RUN_STATE_MAPPING_OVERRIDE_NOT_PERSISTED`. A bootstrap performed under an ephemeral override can never
   later appear healthy under a different configured map. `resolve_structure_key` is now a thin wrapper
   delegating to the canonical resolver (existing `str | None` callers unchanged).

4. **Health fuzzy removed** — `source_health_service.py:183-191` (the `syn-` strip + substring loop +
   first-row-wins) is **deleted**. Per-root resolution now calls `resolve_structure_mapping` against a
   structure-key namespace (config `scan_roots`, falling back to ingested structure-repo keys so identity
   mappings still resolve when app config was not threaded in), sourcing `structure_root_map` from the config
   authority. New per-root output fields: `folder_count` (alias), `structure_mapping_reason`, `structure_key`.
   `source_index_health` gains an `app_config` param (loaded internally, fail-open to empty, if not injected).

5. **Shared run-state** — the duplicate health `_run_state` and the tail of `resolve_run_state` both now
   delegate to one shared `source_bootstrap.project_run_state(enabled, ready, backend)`, so health and the CLI
   can never disagree on the DISABLED / NOT_BOOTSTRAPPED / BACKEND_UNAVAILABLE / RUNNING label.

6. **No path leaks** — the resolver deals only in neutral root keys; `map_roots`' absolute `path` is never
   routed to a serialized surface. A test asserts no absolute path appears in serialized health output.

## Files changed

| File | Change | Notes |
|---|---|---|
| `src/hb_assistant/obsidian_mcp/source_root_mapping.py` | **new** (151 lines) | canonical resolver + normalizer + validator |
| `src/hb_assistant/config/models.py` | +22 | `structure_root_map` field + collision validator |
| `src/hb_assistant/obsidian_mcp/source_bootstrap.py` | +66 / −36 mixed | `project_run_state`, override guard, resolver delegation |
| `src/hb_assistant/obsidian_mcp/source_health_service.py` | +58 mixed | fuzzy removed; canonical resolver; shared run-state; new fields |
| `tests/test_source_root_mapping.py` | **new** (21 tests) | adversarial corpus + integration |
| `docs/evidence/source-index-phase-a/{a3-prove-red,a3-validation}.txt` | **new** | evidence captures |
| `docs/evidence/source-index-phase-a/{03-…,08-…}.md` | new/updated | this doc + baseline-failure #4 |

`source_bootstrap.py` is **not** ruff-formatted on `origin/main`; its diff is confirmed **logic-only** (no
reformat churn). The three formatted modules pass `ruff format --check`.

## Prove-red → prove-green

- **Prove-red** (`a3-prove-red.txt`): the new `tests/test_source_root_mapping.py` run against the A1 parent
  fails for exactly the right pre-implementation reasons — `ImportError` (resolver module absent),
  `TypeError` (`source_index_health` has no `app_config` kwarg), `ValueError` (`SourceStructureConfig` has no
  `structure_root_map` field). Not environment errors.
- **Prove-green** (`a3-validation.txt`): after implementation, all 21 A3 tests pass, and the A3 validation set
  is green apart from the disclosed baseline defects. Authoritative JUnit totals for the focused A3 set
  (`test_source_root_mapping` + watcher-automated-refresh + metadata-first-bootstrap +
  structure-repository-service + health-readonly-conn + structure-cli): **131 tests, 129 passed, 2 failed,
  0 errors** — both failures pre-existing baseline defects (below).

### Adversarial corpus proven (21 tests)
Exact match; valid explicit map (with provenance); invalid explicit map fails closed; `work` ≠ `syn-work`,
`work` ≠ `work-backup`, `home` ≠ `home-work`; full corpus no cross-collision without an explicit map; CLI
override precedence + provenance; many-to-one allowed; duplicate normalized source keys rejected; shared
deterministic normalizer; resolver never raises on degenerate input; health does not fuzzy-match; health
explicit map resolves a `syn-`-prefixed root; **health and watcher readiness agree** on the same mapping;
ephemeral override does not certify durable readiness (`mapping_override_not_persisted`); no absolute path in
serialized health; config validator rejects ambiguous map; `validate_structure_root_map` error surfacing.

## Static checks
- `ruff check` — **all checks passed** on all changed modules + new test.
- `ruff format --check` — 4 formatted files already formatted (`source_bootstrap.py` intentionally excluded;
  logic-only diff verified).
- `mypy` (via `python -m mypy`) — **Success: no issues found** on the 4 changed source modules.

## Disclosed pre-existing baseline failures (NOT A3 regressions)
Recorded in `08-baseline-vs-feature-failures.md`. Neither is caused by Phase A; neither is absorbed into the
A3 prove-red set:
1. `test_source_index_metadata_first_bootstrap.py::test_v119_migration_idempotent_and_additive` — stale
   `== 123`; migrator correctly returns 124.
2. `test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots` — stale hard-coded MCP
   tool-surface count `78`; actual exposed count is `80`. **Confirmed identical (`assert 80 == 78`) on a
   throwaway pristine `origin/main` (`9c27839b`) worktree with zero Phase A code present.** Phase A adds no
   MCP tools. This suite was outside the A0 18-suite baseline set and surfaced during A3 validation.

## Scope / safety
No source-file write or delete API added. No production mutation. No new remote/MCP surface (the CLI override
is diagnostic/one-operation only). A2 and A4 not begun. A1 behavior unchanged.
