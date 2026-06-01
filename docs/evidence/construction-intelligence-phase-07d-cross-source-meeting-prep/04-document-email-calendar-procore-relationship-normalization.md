# Phase 07D · Prompt 04 — Document/Email/Calendar/Procore/Source-Record-Map Relationship Normalization

**Generated (UTC):** 2026-06-01
**Validation HEAD (pre-commit):** `7340c7c892582c44a51c75bd935139427192b387` (Prompt 03 closeout)
**Package version:** `1.3.0` · **Schema version:** `25` (no migration — normalization + promotion only)
**Verdict:** All five source arms now normalize into the substrate. The **first live `--apply`**
populated `cross_source_relationship_candidates` (**1,880**) + `source_evidence_trails` (**1,880**),
and policy-gated promotion landed **1,671** deterministic Procore edges into
`cross_source_relationships` (209 non-deterministic correctly skipped, 0 sensitive/review
promoted). Both no-writeback proofs pass over the populated tables. **Prompt 05 (meeting-prep
prerequisite gates) may proceed.**

Additive, read-only against all external systems. No migration; `--apply` writes only local
SQLite candidates / evidence trails / promoted relationships.

---

## 1. Repo-truth preflight

| Item | Value |
| --- | --- |
| `git rev-parse HEAD` | `7340c7c892582c44a51c75bd935139427192b387` |
| `git status --short` | clean (only untracked `.claude/`) at start |
| `python --version` | `Python 3.12.11` |
| `hb-assistant --version` | `hb-assistant 1.3.0` |
| Schema version | `25` (unchanged) |
| Package version | `1.3.0` |

**Ancestry:** 07A `3cf1652…` → 07B `748ed7e…` → 07C `733ffed…` all ancestors of HEAD. No
branch/worktree. **Live source rows (read-only preflight):** `procore_record_edges` = 1,671;
`source_system_record_map` = 0; `relationship_resolution_queue` = 0; email 69 / meeting-email
117 / document 23; substrate tables = 0 (Prompt 03 left them empty).

---

## 2. What changed (additive)

### 2.1 Store — `construction/store/repositories.py`
Three read-only methods (none existed): `list_procore_record_edges` (safe fields; no
`metadata_json`), `list_relationship_resolution_queue` (safe fields; no `evidence_redacted`;
carries `confidence_class` verbatim), `resolve_source_record_project_key(source_system,
source_primary_key)` (single `source_system_record_map` lookup → `project_key` or None).

### 2.2 Engine — `construction/relationships/cross_source_substrate.py`
- `NormalizedEdge.confidence_class_override` (backward-compatible) + `_confidence_class` honors a
  valid override before recomputing.
- Two new adapters appended to `_ADAPTERS`: `_procore_edges` (deterministic record→record /
  record→entity; `to_entity_key` → `procore_entity` target family) and `_resolution_queue_edges`
  (canonical→canonical; `confidence_class` carried via override).
- **project_key alignment** in `build()`: edges with no `project_key` are backfilled from
  `source_system_record_map` before filtering (counted as `project_key_aligned`); alignment does
  not change `candidate_id` (the hash excludes project_key) so dedup is unaffected.
- **`promote(dry_run, project_filter)`** + `relationships promote` CLI: per
  `cross_source_relationship_policy.seed.yaml` (`deterministic.allow_local_promotion=true`,
  `require_sensitive_high_impact_absent=true`), promotes only `deterministic` AND not
  `sensitive_high_impact` AND not `review_required` candidates into `cross_source_relationships`
  (`promoted_by='deterministic'`, `relationship_id=hash("rel|"+candidate_id)` → idempotent).
  Never mutates candidate rows; never promotes weak/strong/model/sensitive.

### 2.3 CLI — `cli/construction.py`
`construction-agent relationships promote` (`--apply` default dry-run, `--project`, `--json`).

---

## 3. First live `--apply` (local SQLite only)

| Step | Result |
| --- | --- |
| `relationships build --apply` | edges_considered **1,880**; candidates_written **1,880**; evidence_trails_written **1,880**; review_required **159**; project_key_aligned **0** (source-record map empty). by_source_family `{calendar:117, document:23, email:69, procore:1671}`; by_confidence_class `{deterministic:1671, strong_heuristic:51, weak_heuristic:158}`; by_target_family `{email:117, procore:749, procore_entity:952, project:62}` |
| `relationships promote --apply` | candidates_considered **1,880**; promoted **1,671** (all deterministic Procore edges); skipped_not_deterministic **209**; skipped_sensitive_high_impact **0**; skipped_review_required **0**; total_promoted_relationships **1,671** |
| `relationships status` | candidates **1,880**, evidence_trails **1,880**, promoted_relationships **1,671**, review_required **159** |

The 209 non-Procore edges (calendar/email/document, all strong/weak heuristic) are **not**
promoted — they remain advisory candidates, correctly review-routed where applicable.

---

## 4. Validation commands (all exit 0)

| Command | Exit | Key result |
| --- | --- | --- |
| `python -m compileall src tests` | 0 | clean |
| `ruff check .` | 0 | All checks passed |
| `mypy src` | 0 | no issues in **178** source files |
| `pytest -m "not live and not integration and not manual"` | 0 | **2150 passed**, 1 deselected |
| `pytest tests/test_cross_source_substrate.py` | 0 | 15 passed |
| `construction-agent validate --json` | 0 | 4/4, schema V25 |
| `procore validate --json` | 0 | pass |
| `graph files status / no-writeback-proof --json` | 0 | proof `ok=true` |
| `graph calendar status / mail status --json` | 0 | pass |
| `construction-agent data-quality gates --json` | 0 | `meeting_prep_readiness.ready=true`, `auto_readiness_allowed=false` (unchanged) |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true`, schema 25 — **scans the now-populated substrate** |
| `construction-agent data-quality table-inventory --json` | 0 | schema 25, 120 contract tables (no new tables) |
| `construction-agent relationships build / promote / status --json` | 0 | as §3 |

New tests added: `tests/test_cross_source_substrate.py` (Procore-edge normalization;
resolution-queue `confidence_class` override preserved; project_key alignment backfill;
promotion deterministic-only + dry-run + idempotency; promotion no-raw; CLI promote subprocess).
`pytest` delta `2145 → 2150`.

---

## 5. Guardrails honored

- **Read-only / no writeback.** Only local SQLite writes (candidates, evidence trails, promoted
  relationships). Both no-writeback proofs `ok/proof_passed=true` **after** the live apply — the
  `data-quality no-writeback-proof` scans the populated substrate and finds no raw content.
- **No raw content.** Refs are local IDs / existing hashes (Procore record/entity keys, canonical
  IDs); `metadata_json` / `evidence_redacted` free-text are never read into substrate rows;
  JSON fields carry hashes/enums/booleans; the eight guard CHECK columns stay 0 (test-scanned).
- **Promotion is deterministic-only.** 1,671 deterministic promoted; 209 non-deterministic and
  0 sensitive/review-required promoted; weak/strong/model/sensitive never auto-promoted.
- **Readiness not overstated.** `meeting_prep_readiness` unchanged (still gated on the Prompt-01
  prerequisites; substrate population alone does not flip it).

---

## 6. Handoff

**Prompt 05 (meeting-prep prerequisite gates) may proceed.** The substrate is populated and the
relationship layer (candidates + evidence trails + deterministic promoted relationships) is
queryable via `relationships status`. project_key alignment machinery is wired (a no-op now —
`source_system_record_map` is empty; it will backfill once Prompt 07A's source-record map is
populated). Remaining 07D work: meeting-prep gates (05) + brief materialization (06), issue
history (07), risk digest (08), aging/exposure (09), correspondence context (10), Obsidian (11),
07D gates wiring (12).
