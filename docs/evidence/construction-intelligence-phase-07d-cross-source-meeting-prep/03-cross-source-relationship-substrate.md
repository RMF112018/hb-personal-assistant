# Phase 07D · Prompt 03 — Cross-Source Relationship Substrate

**Generated (UTC):** 2026-06-01
**Validation HEAD (pre-commit):** `237b89f8ef0e5943c0dcfe172877b71592c1f2aa` (Prompt 02 closeout)
**Package version:** `1.3.0` · **Schema version:** `25` (no migration — substrate machinery only)
**Verdict:** The unified cross-source relationship substrate is live. New store methods + a
normalization engine seed `cross_source_relationship_candidates` + `source_evidence_trails`
from the three existing edge-shaped candidate tables, with deterministic idempotent IDs and
policy-driven review routing. `cross_source_relationships` stays empty (no auto-promotion).
Both no-writeback proofs pass. **Prompt 04 (document/email/calendar/Procore/source-record-map
normalization + project_key alignment + promotion) may proceed.**

This prompt is additive and read-only against all external systems. No migration (Prompt 02
created the V25 tables). `build --apply` writes only local SQLite candidates + evidence trails.

---

## 1. Repo-truth preflight

| Item | Value |
| --- | --- |
| `git rev-parse HEAD` | `237b89f8ef0e5943c0dcfe172877b71592c1f2aa` |
| `git status --short` | clean (only untracked `.claude/`) at start |
| `python --version` | `Python 3.12.11` |
| `hb-assistant --version` | `hb-assistant 1.3.0` |
| Schema version | `25` (`LATEST_SCHEMA_VERSION`; unchanged) |
| Package version | `1.3.0` |

**Ancestry (all confirmed ancestors of HEAD):** 07A `3cf1652…` → 07B `748ed7e…` → 07C
`733ffed…` (and Prompt 02 `237b89f`). No branch/worktree created.

---

## 2. What changed (additive)

### 2.1 Store — `construction/store/repositories.py`
- `list_document_relationship_candidates_full()` — safe richer read (adds `target_record_key_hash`,
  `relationship_type`, decoded `source_reference_json`) for the normalizer; the existing
  summary `list_document_relationship_candidates()` is untouched.
- `upsert_cross_source_relationship_candidate(...)` / `count_*` / `list_*` (filters: project,
  review_required) — V25 candidates.
- `upsert_source_evidence_trail(...)` / `count_*` / `list_*` — V25 evidence trails.
- `upsert_cross_source_relationship(...)` / `count_*` — V25 promoted edges (ships for Prompt 04;
  **not called by build**).
All upserts mirror the existing `upsert_document_relationship_candidate` pattern (INSERT…ON
CONFLICT, `transaction()`, bools→0/1, `_utc_now()`); the eight guard CHECK columns are never
written (defaults 0 hold).

### 2.2 Engine — `construction/relationships/cross_source_substrate.py` (new)
- `NormalizedEdge` (`extra="forbid"`) + three adapters reading the existing tables:
  document→record (V24), calendar↔email (V23), email→project/procore/calendar (V11).
- `CrossSourceRelationshipSubstrateBuilder.build(dry_run, project_filter, max_edges)` →
  report dict; `relationship_substrate_status(...)` → coverage report.
- **Confidence-class mapping** (source → unified V25 enum): `model_proposed` flag →
  `model_proposed`; else `deterministic` flag → `deterministic`; else score ≥ 0.8 →
  `strong_heuristic`; else `weak_heuristic`.
- **Review routing** from `review_required_relationship_rules.seed.yaml`: any of
  {`weak_heuristic`, `model_proposed`, `stale_or_unresolved`} OR `sensitive_high_impact` OR the
  source's own review flag → `review_required`. `sensitive_high_impact` = source flag OR a
  sensitive-category keyword (legal/contractual/claim/safety/personnel/financial) hit.
- **Idempotency**: `candidate_id = hash("{source_family}|{source_record_ref}|{target_family}|{target_record_ref}|{relationship_type}")`
  (matches the table UNIQUE edge key); `evidence_trail_id = hash("evt|"+candidate_id)`.
- **No auto-promotion**: every written row is `promotion_status='candidate'`; the builder never
  touches `cross_source_relationships`. Validates the relationship contract at init.
- Refs are local IDs / existing hashes; `source_reference_json` / `signals_json` /
  `source_refs_json` carry hashes/enums/booleans only — no raw content.

### 2.3 CLI — `cli/construction.py`
New `construction-agent relationships` sub-app:
- `relationships build` — `--apply` (default dry-run), `--project`, `--json`.
- `relationships status` — `--project`, `--json`.
Matches the command name declared in `phase_07d_validation_matrix.json`.

---

## 3. Validation commands (all exit 0)

| Command | Exit | Key result |
| --- | --- | --- |
| `python -m compileall src tests` | 0 | clean |
| `ruff check .` | 0 | All checks passed |
| `mypy src` | 0 | no issues in **178** source files |
| `pytest -m "not live and not integration and not manual"` | 0 | **2145 passed**, 1 deselected |
| `pytest tests/test_cross_source_substrate.py` | 0 | 10 passed |
| `construction-agent validate --json` | 0 | 4/4, schema V25 |
| `procore validate --json` | 0 | pass |
| `graph files status / no-writeback-proof --json` | 0 | proof `ok=true` |
| `graph calendar status / mail status --json` | 0 | pass |
| `construction-agent data-quality gates --json` | 0 | `meeting_prep_readiness.ready=true`, `auto_readiness_allowed=false` (unchanged from Prompt 01) |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true`, schema 25 |
| `construction-agent data-quality table-inventory --json` | 0 | schema 25, **120** contract tables (no new tables this prompt) |
| `construction-agent relationships build --json` | 0 | dry_run; **209 edges planned** (calendar 117 / email 69 / document 23), 0 written |
| `construction-agent relationships status --json` | 0 | live substrate empty (candidates=0, promoted=0) |

New tests added to the suite: `tests/test_cross_source_substrate.py` (apply writes 4+4;
dry-run writes nothing; idempotent re-apply; review/sensitive routing; never writes promoted
relationships; no-raw-content + guard-column scan; empty sources OK; status coverage; project
filter; CLI build/status subprocess exit-0). `pytest` delta `2135 → 2145`.

---

## 4. SQLite truth

- `build --apply` was validated end-to-end on **temporary databases** (the test suite): 4
  representative source edges → 4 candidates + 4 evidence trails, idempotent on re-run, all
  eight guard columns 0, no leak-pattern values, `cross_source_relationships` count 0.
- The **live** local DB substrate is left **empty by design** this prompt — `relationships
  build` was run **dry-run only** (no `--apply`), which plans 209 candidates from the real
  local candidate tables (calendar 117 / email 69 / document 23) and writes nothing.
  `relationships status` confirms `candidates=0`, `promoted_relationships=0`. Populating the
  live substrate is deferred so Prompt 04 owns the first apply alongside project_key alignment.
- `table-inventory` unchanged at schema 25 / 120 contract tables (Prompt 03 added no tables).

---

## 5. Guardrails honored

- **Read-only / no writeback.** Only local SQLite candidate + evidence writes; both
  no-writeback proofs `ok/proof_passed=true` post-change.
- **No raw content.** Refs are local IDs / existing hashes; JSON fields are hashes/enums/booleans;
  leak scan + guard-column scan pass.
- **No auto-promotion.** All rows `promotion_status='candidate'`; weak/model/sensitive →
  `review_required`; `cross_source_relationships` untouched (count 0).
- **Readiness not overstated.** Substrate machinery shipped + validated on temp DBs; live
  substrate intentionally empty; `meeting_prep_readiness` unchanged.

---

## 6. Handoff

**Prompt 04 may proceed.** The substrate store layer, normalization engine, and `relationships
build`/`status` CLI are in place and tested. Prompt 04 will: add the Procore-native edge and
`source_system_record_map` / `relationship_resolution_queue` arms, perform cross-family
`project_key` backfill/alignment and dedup, run the first live `--apply`, and implement the
policy-gated promotion into `cross_source_relationships` (deterministic/human only; never
weak/model/sensitive). The `upsert_cross_source_relationship` store method is ready for it.
