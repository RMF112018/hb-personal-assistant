# A3 — Canonical structure-root mapping authority

**Checkpoint:** A3 (third sub-phase of Phase A). **Parent commit:** A1 follow-up
`1d58d123a3b58463eecb270609d6afba69ed4609` (documented in `09-commit-lineage.md`).
**Branch state after this checkpoint:** GREEN (all new tests pass; only the disclosed pre-existing baseline
defects fail). **No push / PR / merge / force.**

> **A3 corrective follow-up (this revision).** Applied after review-hold on A2. Four items: (1) health
> configuration loading is now **fail-closed** on load/validation failure (§ Design item 4); (2) four
> fail-closed regression tests added; (3) the A3 validation evidence is split into distinct focused/superset
> artifacts (§ Prove-red → prove-green); (4) the intervening A1 follow-up commit is fully documented in
> `09-commit-lineage.md`, and the complete A1 suite was re-run (75/75 green). No architectural change.

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

4. **Health fuzzy removed + fail-closed config loading** — `source_health_service.py:183-191` (the `syn-`
   strip + substring loop + first-row-wins) is **deleted**. Per-root resolution now calls
   `resolve_structure_mapping` against a structure-key namespace (config `scan_roots`, falling back to
   ingested structure-repo keys only for a **valid** config that declared no `scan_roots`), sourcing
   `structure_root_map` from the config authority. New per-root output fields: `folder_count` (alias),
   `structure_mapping_reason`, `structure_key`, `structure_ready`; new top-level field
   `structure_mapping_config_available`. `source_index_health` gains an `app_config` param.

   **Fail-closed configuration loading (A3 corrective follow-up).** The application configuration is the
   mapping authority, so a configuration that **fails to load or fails validation** must NOT be read as an
   empty valid configuration — otherwise health could call a root structure-ready without knowing the
   canonical mapping. An explicitly injected **valid** config (even an empty one) is trusted and still permits
   exact identity matching; a **failed/invalid internal load** is distinguishable:
   ```
   configuration loaded successfully   -> evaluate CLI/config/exact mapping normally
   configuration unavailable OR invalid -> mapping result = mapping_configuration_unavailable
                                           structure_ready = false ; no identity fallback
                                           structure_mapping_config_available = false
   ```
   New reason code `mapping_configuration_unavailable`. `structure_ready` is `structure_key is not None`, so a
   config failure can never report a root structure-ready. Covered by four corrective tests:
   `health_config_load_failure_fails_closed`, `health_invalid_mapping_config_fails_closed`,
   `valid_empty_config_still_allows_exact_identity_match`, `config_failure_cannot_report_structure_ready`.

5. **Shared run-state** — the duplicate health `_run_state` and the tail of `resolve_run_state` both now
   delegate to one shared `source_bootstrap.project_run_state(enabled, ready, backend)`, so health and the CLI
   can never disagree on the DISABLED / NOT_BOOTSTRAPPED / BACKEND_UNAVAILABLE / RUNNING label.

6. **No path leaks** — the resolver deals only in neutral root keys; `map_roots`' absolute `path` is never
   routed to a serialized surface. A test asserts no absolute path appears in serialized health output.

## Files changed

| File | Change | Notes |
|---|---|---|
| `src/hb_assistant/obsidian_mcp/source_root_mapping.py` | **new** (~156 lines) | canonical resolver + normalizer + validator + `mapping_configuration_unavailable` |
| `src/hb_assistant/config/models.py` | +22 | `structure_root_map` field + collision validator |
| `src/hb_assistant/obsidian_mcp/source_bootstrap.py` | +66 / −36 mixed | `project_run_state`, override guard, resolver delegation |
| `src/hb_assistant/obsidian_mcp/source_health_service.py` | mixed | fuzzy removed; canonical resolver; shared run-state; **fail-closed config loading**; new fields |
| `tests/test_source_root_mapping.py` | **new** (25 tests) | adversarial corpus + integration + 4 fail-closed |
| `docs/evidence/source-index-phase-a/a3-prove-red.txt` | **new** | prove-red capture |
| `docs/evidence/source-index-phase-a/a3-validation-focused.txt` | **new** | focused prove-green (135/133/2) |
| `docs/evidence/source-index-phase-a/a3-validation-superset.txt` | **new** | superset sweep (314/310/4) |
| `docs/evidence/source-index-phase-a/{03-…,08-…,09-…}.md` | new/updated | this doc + baseline-failure #4 + commit lineage |

`source_bootstrap.py` is **not** ruff-formatted on `origin/main`; its diff is confirmed **logic-only** (no
reformat churn). The three formatted modules pass `ruff format --check`.

## Prove-red → prove-green

- **Prove-red** (`a3-prove-red.txt`): the new `tests/test_source_root_mapping.py` run against the A1 parent
  fails for exactly the right pre-implementation reasons — `ImportError` (resolver module absent),
  `TypeError` (`source_index_health` has no `app_config` kwarg), `ValueError` (`SourceStructureConfig` has no
  `structure_root_map` field). Not environment errors.
- **Prove-green** — two **separate** artifacts (each documents one execution; a JUnit summary from one run is
  never combined with terminal output from another):
  - **Focused** (`a3-validation-focused.txt`): the primary A3 validation set (`test_source_root_mapping` +
    watcher-automated-refresh + metadata-first-bootstrap + structure-repository-service + health-readonly-conn
    + structure-cli). **135 tests: 133 passed, 2 failed, 0 errors** — the two failures are baseline defects
    (`test_v119_migration_idempotent_and_additive`; `test_export_evidence_emits_gate_off_and_on_snapshots`).
  - **Superset** (`a3-validation-superset.txt`): a broader 16-suite source-index regression sweep. **314
    tests: 310 passed, 4 failed, 0 errors** — the four failures are the baseline defects (`v119`, `v120`,
    `v122` stale `== 123`; structure-cli `78` vs `80`).
  - All 25 tests in `test_source_root_mapping.py` (21 original + 4 fail-closed corrective) pass GREEN in both.

### Adversarial corpus proven (25 tests)
Exact match; valid explicit map (with provenance); invalid explicit map fails closed; `work` ≠ `syn-work`,
`work` ≠ `work-backup`, `home` ≠ `home-work`; full corpus no cross-collision without an explicit map; CLI
override precedence + provenance; many-to-one allowed; duplicate normalized source keys rejected; shared
deterministic normalizer; resolver never raises on degenerate input; health does not fuzzy-match; health
explicit map resolves a `syn-`-prefixed root; **health and watcher readiness agree** on the same mapping;
ephemeral override does not certify durable readiness (`mapping_override_not_persisted`); no absolute path in
serialized health; config validator rejects ambiguous map; `validate_structure_root_map` error surfacing.
**Plus 4 fail-closed corrective tests:** `health_config_load_failure_fails_closed`,
`health_invalid_mapping_config_fails_closed`, `valid_empty_config_still_allows_exact_identity_match`,
`config_failure_cannot_report_structure_ready`.

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
