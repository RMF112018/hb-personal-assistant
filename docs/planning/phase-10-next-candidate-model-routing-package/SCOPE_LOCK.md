# Scope Lock — Local Model Evaluation + Routing for Daily-Brief Intelligence

Locked from live repo truth on branch
`experiment/local-model-routing-daily-brief-intelligence` (base HEAD `7815cfd2`).
Repo code/tests/DB/CLI are authoritative over the package's suggested paths.

## Selected candidate

Local model **evaluation + routing** family, with **daily-brief intelligence quality** as the
first consumer. The production-like daily-run pilot/runbook is excluded (already implemented:
`second-brain daily-run run` + `scheduler {install,status,uninstall}` verified present).

## Repo-truth anchors

- Real `local_ai` package path: `src/hb_assistant/construction/second_brain/local_ai/`
  (the package's `src/hb_assistant/local_ai/...` suggestions are remapped here).
- Existing reusable primitives:
  - `provider.py` — `build_local_model_status(...)`, `resolve_local_model_client(...)`,
    `OllamaProvider.probe_models()` (redacted category codes, `/api/tags` only), `MockProvider`.
  - `structured_output.py` — `StructuredOutputClient.run(...)` (3-try self-repair, single-hop
    fallback, hash-only receipt, heavy gate), `StaticOutputClient` (offline test backend),
    `StructuredOutputResult`.
  - `models.py` — `LocalModelProfile` / `LocalModelProfiles` (`extra="forbid"`, fallback +
    guardrail invariants); `ActionCandidate` (schema-enforced, ≥1 source_ref).
  - `contracts.py` — fail-closed seed loaders (`load_local_model_profiles()`), env overrides.
  - `schema.py` — 13 Phase 10 guard columns, V41 read-only schema proof.
- Profile seed exists: `resources/config/phase_10_local_model_profiles.seed.yaml`
  (6 profiles + `fallbacks` + `guardrails`; has `role`, **no `task_families`** mapping).
- daily-run already performs local-model executive synthesis (`--synthesize`,
  `--synthesis-profile`, default `brief_synthesis`). The new intelligence adapter is **additive
  and opt-in** (`--with-intelligence`), distinct from `--synthesize`.
- Migration head: **V44**. Convergence table `daily_brief_action_candidates`; guard columns
  `CHECK(=0)`; safe read model `list_daily_brief_action_candidates(...)`.
- mypy strict already covers `hb_assistant.construction.second_brain.*`; arch-doc next #235.

## Locked decisions

1. **No new DB migration / no schema change.** Eval + intelligence emit JSON, redacted evidence,
   and an optional **local-only sidecar** (temp/app-support, never repo). Reuse the existing
   hash-only `local_model_run_receipts` path only if a receipt is wanted; default no-persist.
2. **Separate routing seed** `resources/config/local_model_task_routing.seed.yaml`
   (`task_family → profile_id` + ordered fallbacks), loaded by a new loader, consumed by a new
   `model_router.py`. The proven `LocalModelProfiles` model is left untouched.
3. New modules under `.../local_ai/`: `model_eval.py`, `model_eval_fixtures.py`,
   `model_eval_metrics.py`, `model_router.py`, `daily_brief_intelligence.py`.
4. **Eval is operationally decisive**: per task family it reports the recommended profile,
   blocked/unsafe families, fallback route, reason codes, and the "use this next run" pick.
5. **Intelligence adapter stays narrow (v1)**: six advisory sections — executive catch-up, top
   priorities, open loops, waiting-on-me vs waiting-on-others, meeting prep, project/Procore risk
   — every bullet source-linked to existing `daily_brief_action_candidates` IDs or rejected. No
   ontology/ranking framework. Advisory only; deterministic candidates stay authoritative;
   fail-closed to the deterministic brief on any model/JSON/schema/source-link/redaction failure.

## CLI surfaces (final names)

- `second-brain local-model profiles --json`
- `second-brain local-model route --task-family <family> --json`
- `second-brain local-model eval --suite daily-brief --models auto --json`
- `second-brain daily-brief intelligence --date YYYY-MM-DD --dry-run --json`
- `second-brain daily-run run --with-intelligence ...` (opt-in flag; default off)

## Task families (eval)

`email_action_extraction_json`, `daily_brief_synthesis_quality`, `calendar_prep_summary`,
`procore_digest_summary`, `short_operator_catchup` (≥3 exercised by synthetic fixtures).

## Non-goals

No cloud LLM; no email send / calendar mutation / Procore / Graph / external writeback; no MCP
raw exposure; no new scheduler/browser/Obsidian workflow (integration only); no production-DB
mutation; no destructive migration; no credential/auth changes; no raw prompt/response or raw
private content persisted to DB / repo / evidence / docs / tests / logs.

## Tests / live proof / evidence

Offline unit + CLI suites via `StaticOutputClient` + `CliRunner`; guard-column-sum-zero
assertions. Live proof on a `/tmp` copy of the **(Dev)** working DB (eval, route, deterministic
baseline vs `--with-intelligence` dry-run, fallback-by-disabled-model). Redacted evidence under
`docs/evidence/phase-10-local-model-routing/`. Arch doc `docs/architecture/235-...`. Operator
runbook. Next recommended candidate after this: email follow-up / raw enrichment.
