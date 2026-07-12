# A0 — Repo-Truth Baseline & Delta Audit (Phase A)

**Status:** `A0_COMMITTED_BRANCH_STATE=GREEN` —
`PROVE_RED_TESTS_ARE_INTRODUCED_PER_SUBPHASE_AND_RUN_BEFORE_THE_CORRESPONDING_FIX`.
A0 commits the audit + baseline record + test-design matrix only. **No executable future-failing tests are
committed at A0.** Each sub-phase (A1, A3, A2, A4) introduces its own prove-red tests, runs them against its
parent commit (capturing prove-red evidence), then implements and commits green.

## Repository state
| Item | Value |
|---|---|
| origin/main SHA (audited base, precondition enforced) | `9c27839b48fdab0e882fa475a6ace81dc93762fd` (PR #303 merge) |
| Branch | `fix/source-index-phase-a-correctness-trust` |
| Worktree | isolated, created from `origin/main`; clean at HEAD `9c27839b` |
| Schema version | `LATEST_SCHEMA_VERSION = 124` (`src/hb_assistant/store/migrator.py:17`) |
| CI workflows present | `.github/workflows/{claude.yml, claude-code-review.yml, forecasting-semantic-gates.yml}` — **no source-index gate** |
| Test runner | `PYTHONPATH="src:subrepos/construction-financial-review/src" .venv/bin/python -m pytest` (Python 3.14.5, pytest 9.0.3) |

Pre-existing local work (the divergent `fix/source-index-vault-streaming-walk` branch, ~24k lines ahead, and
100+ sibling worktrees) is **untouched**; Phase A branches cleanly from `origin/main`.

## Confirmed findings (repo-truth, all four hypotheses hold on origin/main)

### A1 — Unsafe vault deletion reconciliation (audit IDX-001) — CONFIRMED
- `src/hb_assistant/obsidian_mcp/source_indexer.py:scan_vault_notes:917-961`.
- Caps at `max_files = int(getattr(config,"external_source_scan_max_files",5000))` (`:925`); on
  `report.scanned > max_files` sets `report.truncated = True` and `break` (`:939-941`).
- Builds `seen` set (`:926,:942`); then **unconditionally** at `:958-960`:
  `for gone in repo.active_rel_paths(_VAULT_ROOT_KEY) - seen: repo.mark_deleted("obsidian_note", gone)`.
- Passes **no `error_sink`** to the fail-open `walk_source_tree` (`:930`) — an unreadable subtree is silently
  skipped and its paths are mass-deleted. Per-file exceptions are swallowed into `report.errors` (`:953-955`)
  but do not stop reconciliation. Only root guard is `is_dir()` (`:920`); **no empty-root blast-radius guard**
  (the external path has `empty_root_guard` + `source_index_empty_root_delete_threshold` default 50 at `:1851-1876`).
- **Current behavior:** deletion runs after truncated / error-bearing / empty traversals.
- **Production failure mode:** valid vault-note rows beyond the 5000 cap, or under an unreadable subtree, are
  marked deleted; FTS rows removed; generated cards staled — while the source note still exists.
- `mark_deleted` (`src/hb_assistant/obsidian_mcp/source_index_repository.py:758-798`) is DB-only: FTS row
  DELETE + `deleted=1/active=0` + `_mark_generated_notes_stale`. **No source file is removed.** Already
  streaming (`walk_source_tree` is `os.scandir` DFS, not `rglob`).
- Live callers: `source_watch.py:276` (`_poll_once`), `source_indexer.py:2191` (rebuild drain).
- **Corrective behavior:** gate the delete-reconcile on a certified-complete, error-free, untruncated,
  uninterrupted traversal; empty-root blast-radius guard with one-shot operator recovery; transactional
  confirmed delete. (See plan A1.)

### A3 — Split root-mapping authority (audit IDX-006) — CONFIRMED
- Bootstrap + watcher share the canonical `resolve_structure_key` (`source_bootstrap.py:46-59`; watcher via
  `resolve_run_state:599-668` at `:656`; CLI `cli/source_watch.py:181,186,259`) — explicit-map(exact) →
  exact-key → None; no fuzzy.
- **Health reimplements FUZZY matching** (`source_health_service.py:183-191`): `key.replace("syn-","")`
  prefix-strip + bidirectional substring (`sk in key or key in sk`) + first-row-wins. Health also duplicates
  run-state (`_run_state:30-38`).
- The explicit map is **not persisted** — only the CLI flag `--structure-root-map-json`
  (`cli/source_watch.py:79-80`), so normal operation is exact-only (bootstrap/watcher) vs fuzzy (health):
  maximal divergence for `work` / `syn-work` / `work-backup`.
- `map_roots` carries absolute `path` at `source_bootstrap.py:76` (in-process only; must never reach a client
  surface). Health is already path-safe.
- **Production failure mode:** health certifies a root structurally ready off the wrong structure row while
  watcher/bootstrap reject it (or the reverse) — inconsistent source trust to clients/operators.
- **Corrective behavior:** one canonical config-backed mapping authority + shared resolver with reason codes;
  delete health's fuzzy path. (See plan A3.)

### A2 — Search/read does not enforce root readiness (audit IDX-002/003/011/018) — CONFIRMED
- `search_source_files:110` gates only `invalid_root` existence (`:115`), hardcodes
  `freshness_basis:indexed_rows` (`:173`); `list_source_files:187` same; `source_file_metadata:231` has
  `del config` (no readiness). None consult health/policy/generation/reconciliation/structure.
- `read_status="live_readable"` is set from ext/extraction only, **no live probe**
  (`source_project_number.py:match_explanation_for_row:179`). The real live `is_file()` probe is only in
  `source_content_provider.py:read:91` (`file_absent` at `:151`), at read time.
- Health top-level `safe_for_client_answering = any(...)` (**ANY-root**, `source_health_service.py:518`).
- Configless roots default `enabled=True, sensitive=False` (`list_source_roots:85-86`, fail-open).
- `SourceWatcher.start:82` gates config bit (`:88`) + lease (`:106`) only — no readiness.
- The full per-root trust vocabulary already exists in health (`:242-374`: `policy_verification`,
  `metadata_completeness_state`, `safe_for_path_lookup`, `safe_for_content_answering`, `derive_watcher_ready`,
  `index_only_available`, `safe`) but is reporting-only — no serving path imports it.
- Tool docstrings overstate: `nas_mcp/tool_registration.py:388,408` ("for full file content"); the read tool
  is bounded to `max_chars` default 4000. Editing a source-tool docstring changes `semantic_surface_checksum`
  (`client_tool_manifest.build_manifest:258` ← `live_tool_surface.py:121-130`), asserted by
  `tests/test_tool_manifest_freshness_guard.py`, re-frozen via `seed_frozen_schema_index`. Direct/gateway
  parity funnels through `broker.py:1424` → same service.
- **Corrective behavior:** shared `RootTrustDecision` consumed by search/list/metadata/read/health/watcher;
  fail-closed; additive read/health fields with legacy contradictions corrected. (See plan A2.)

### A4 — Poison file pins a generation forever (audit IDX-009) — CONFIRMED
- On per-file stat/upsert failure the cursor **holds before** the poison file (`source_indexer._flush:1555-1677`;
  `last_cursor` assigned only after a committed observation `:1658-1661`); generation suspended
  `partial`/`metadata_walk_error` (`:1787-1809`) and retried **forever**.
- `partial` is outside `_NO_PROGRESS_ERROR_CODES` (`{directory_fanout_limit, generation_ceiling,
  empty_root_guard}`, `source_index_scan_generations_repository.py:53-55`) — never blocked/surfaced.
- Generation states: `running, partial, reconcile_pending, completed, failed, abandoned`
  (`source_index_scan_generations_tables.py:53-63`). **No quarantine/retry/attempt state anywhere;** schema has
  no per-path column → new additive **V125** migration required (version-guarded + parity-guarded pattern
  `migrator.py:9138-9166`; bump `LATEST_SCHEMA_VERSION` `:17`).
- `tests/test_source_index_generation_hardening.py:test_per_file_error_holds_cursor_then_retries:524` locks in
  the current forever-retry behavior (A4 updates it to "retry to threshold, then quarantine + advance").
- **Corrective behavior:** bounded retry → durable quarantine ledger → cursor advance → non-authoritative
  generation until resolved, with no-forward-progress suspension and retention invariants. (See plan A4.)

## Findings no longer applicable / already partially corrected
- **Streaming vault walk (audit note re PR #300):** origin/main `scan_vault_notes` is **already streaming**
  via `walk_source_tree` (`os.scandir`, not `rglob`). Constraint "do not reintroduce `sorted(rglob(...))`" is
  already satisfied; A1 is purely the deletion-safety gate, not the memory rewrite.
- **V123/V124 already landed** (multi-root relpath uniqueness; FTS join index) — confirmed present in
  `migrator.py` V123/V124 blocks; not re-litigated by Phase A.

## Additional findings discovered during A0
- Health maintains a **second** duplicate authority `_run_state:30-38` (docstring: "mirrors
  source_bootstrap.resolve_run_state") — folded into A3 consolidation.
- The existing hardened lightweight-reconcile tests (`test_r8_lightweight_reconcile_*` in
  `test_source_index_watcher_automated_refresh.py`) prove the *folder/structure* path is fail-closed — direct
  templates for A1's vault prove-red tests; they highlight by contrast that `scan_vault_notes` is not gated.
- `tests/test_obsidian_vault_quarantine_reset.py` concerns a **different** (encryption/vault) quarantine
  concept — not scan poison-file quarantine; A4 introduces a new, separate ledger.

## Migration requirement
- **A1/A3/A2:** no schema change.
- **A4:** one additive migration **V125** (new `source_index_scan_quarantine` table; `generation_id` nullable +
  `origin_generation_id` audit; no `ON DELETE CASCADE` for unresolved records). Bump `LATEST_SCHEMA_VERSION=125`.

## Manifest / tool-surface impact
- **A2 only.** Correct overstated help (`tool_registration.py:388,408`) + `assistant_source_file_read` help;
  additive read/health fields. Requires official-path manifest regeneration + re-freeze of
  `semantic_surface_checksum`, gateway/direct parity fixtures, and `test_tool_manifest_freshness_guard.py`
  baseline updates. Tool **names preserved**.

## Files expected to change
See plan "Files expected to change". A1: `source_indexer.py`, `source_index_repository.py`, local CLI +
op-ownership support, new vault-deletion-safety tests. A3: `source_bootstrap.py`, `source_health_service.py`,
config (`structure_root_map`), new mapping tests. A2: new `source_root_trust.py` + serving/health/watcher/
manifest wiring + tests. A4: `migrator.py` (V125), new quarantine tables/repository, `source_indexer.py`,
`source_scan_runner.py`, `cli/source_watch.py`, new quarantine tests.

## Risk & rollback
Each checkpoint is an isolated green local commit and can be reverted independently. A1 fails safe (a genuinely
absent note simply isn't reaped when a scan is uncertain; operator recovery handles legitimate emptying). A2's
main regression surface is manifest/checksum churn (gated by re-freeze + parity fixtures). A4's V125 is
additive/idempotent (rollback = restore prior DB + prior image; older code ignores the new table).

## Baseline test record
See `baseline-source-index.txt` (raw pytest output) and `../08-baseline-vs-feature-failures.md` for the
green/failing split. Any test failing at baseline is a pre-existing defect, disclosed separately, and is never
absorbed into a Phase-A prove-red set.
