# 233 — Phase 10 Relationship Candidate Engine (Follow-On)

Status: experimental (branch `experiment/local-agent-family-proof`). Scope: the highest-ROI
follow-on **after** the daily pipeline pilot — a deterministic-first, local-only **relationship
candidate engine** that links already-ingested email and calendar context into reviewable,
source-linked candidates and surfaces them conservatively in the daily brief. Authoritative truth
is repo code + tests + the evidence bundle at
`docs/evidence/phase-10-local-agent-family/relationship-candidate-engine-proof.md`.

## Purpose & relationship to the daily pipeline

The daily pipeline ([232](232-phase-10-local-agent-family.md)) already converges email, Procore, and
calendar signals into `daily_brief_action_candidates`. It delivers *rows*. The next gap is
*intelligence density*: the system can tell Bobby about emails and meetings, but it does not yet
operationalize the **relationships across those sources**. This engine closes that loop — it does
**not** replace the pipeline. It runs after the brief substrate exists and makes the brief smarter by
connecting related context rather than adding another disconnected surface.

It reuses the existing deterministic substrate from
[213](213-phase-10a-bounded-purposeful-packets-and-relationship-scoring.md): the email↔calendar
`relationship_scoring` layer decides relatedness. A local model is **never** consulted for
relatedness; there is no model call in the correctness path.

## CLI surface

```
second-brain relationship-candidates scan \
  --db <path> --as-of <iso> --project-key <k> --limit <n> \
  --scan-threads <n> --scan-events <n> --min-confidence <f> \
  --dry-run|--apply --max-persist <n> --summary --json
```

- **Dry-run is the default** (zero writes). `--apply` **fails closed** (exit 2,
  `error=apply_requires_max_persist`) without `--max-persist`. A negative cap or out-of-range
  `--min-confidence` also fail closed (exit 2). Runtime errors → exit 1; success → exit 0.
- `--json` is machine-readable; `--summary` adds the per-candidate list (hashed refs + reason codes
  only — never raw refs/content). Default output is counts + class histogram + guardrails.
- The pre-existing read-only `phase-10 relationship-candidates` command (pure scorer emitter) is
  preserved unchanged; this is an additive sibling surface.

> Note (repo truth): `second-brain` is a top-level CLI group, so the live invocation is
> `hb-assistant second-brain relationship-candidates scan …` (not under `construction …`).

## Behavior & contract

| Aspect | Decision |
|--------|----------|
| Relationship types | `email_calendar` only. `email_procore` / `calendar_procore` are **deferred** — the deterministic scorer is email↔calendar only and no safe Procore source-linking read-model exists yet (documented, not invented). |
| Determinism | Relatedness = `find_email_calendar_relationships` (deterministic, no clock, no model). Weak relations excluded by `--min-confidence` (default `0.55`, the moderate floor). |
| Persistence | `phase10_relationship_candidates` (V41; schema head V43). No migration. |
| Identity / idempotency | `relationship_candidate_id = sha256(type \| from_family \| from_ref_hash \| to_family \| to_ref_hash)[:32]`. Source refs hashed via the repo-standard `hash_value` (sha256, no salt → stable across runs and DB copies). Insert is `ON CONFLICT DO NOTHING` → re-run yields `skipped_existing`, never duplicates. |
| Stored fields | families, **hashed** ref pair, type, project_key, confidence, `confidence_class` (=relationship_class), `deterministic=1`, `model_proposed=0`, `review_status='pending'`, `reason_redacted` (comma-joined safe reason codes). All 13 guard `CHECK(=0)` columns left to DEFAULT 0. |
| Review state | moderate (and any private-sensitive) → review required; strong is surfaced more prominently but stays advisory. |
| Ordering | confidence DESC, then `relationship_candidate_id` ASC — in the store list helper, CLI JSON, and brief enrichment. |

### Store helpers (`construction/store/repositories.py`)

`insert_phase10_relationship_candidate` (guard cols omitted → DEFAULT 0),
`list_phase10_relationship_candidate_ids` (idempotency set),
`list_phase10_relationship_candidates` (safe fields, deterministic order),
`count_phase10_relationship_candidates`.

## Daily-brief integration

Render-time enrichment (no persistence bridge): `daily_brief_render.render_daily_brief` reads
`phase10_relationship_candidates` (bounded by `relationship_limit`, default 10; respects
`--project-key`) and adds a `relationships` array + a **"Related Context"** markdown section. The
section appears **only when rows exist**, so the brief is byte-identical for dates/DBs without
relationship candidates. Render stays read-only (no mutation; guard columns untouched). Each item
answers: what is related (hashed refs + source families), why (reason codes), confidence + class,
recommended next action (`prepare_packet` for strong, `review` otherwise), and review-required — with
no raw subjects/bodies/addresses/URLs/payloads.

## How candidates reach the brief in normal operation

Two operable paths (handoff states the canonical one):

1. **Standalone pre-render step (canonical):** run
   `relationship-candidates scan --apply --max-persist N` to persist rows, then `daily-brief render`
   surfaces them. This is the documented daily-operation path.
2. **Opt-in pipeline stage:** `pipeline run --include-relationship-candidates` (default **off**)
   inserts a `relationship_candidates` stage **just before** `daily_brief_render`, so freshly
   persisted rows feed the same render. The stage is **not** in the default `STAGE_ORDER`; the
   default daily run is byte-unchanged and regression-tested.

## Guardrails

Deterministic-first (no model in correctness path); dry-run default + fail-closed apply; capped,
idempotent, source-linked persistence; hashed refs + safe reason codes only; all 13 guard
`CHECK(=0)` columns stay zero; no email/calendar/Procore/Graph/external writeback; source tables
never mutated; no raw content / URL / address / HTML / token / prompt / response in repo, evidence,
docs, tests, or logs. Live proof runs on a DB **copy** only.

## Validation summary (see evidence bundle)

- Full package test set (156 tests) green; new `tests/test_phase_10_relationship_candidates.py`
  (30 tests: core + CLI + pipeline + brief enrichment) green. `ruff check` + `mypy` clean on the
  `local_ai` package (32 files). `ruff format` drift in untouched pre-existing files is documented,
  not introduced.
- Live DB-copy proof (Dev DB, V43, 1148 threads / 500 events): dry-run zero-write; apply cap=5 →
  5 rows + 45 skipped_capped; canonical idempotency (apply 50 → re-run persisted 0,
  skipped_existing 50, rows stable, distinct ids = rows); guard-sum 0; source tables immutable
  (1148/500 unchanged); redaction scan clean over CLI JSON + persisted rows + rendered brief; default
  pipeline excludes the stage, opt-in includes it before render.
- Known pre-existing failure (branch-independent, reproduced at base commit `581f0ee6`):
  `test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table`.

## Rollback

Additive and independently revertible: revert the brief-enrichment commit, then the CLI/pipeline
commit, then the core commit. No schema change to undo. If a DB-copy apply produced wrong rows,
discard the copy and fix code before re-applying.
