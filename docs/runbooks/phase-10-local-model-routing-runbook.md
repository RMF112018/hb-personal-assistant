# Runbook — Local Model Evaluation + Routing + Daily-Brief Intelligence (Phase 10)

Local-only. No cloud LLM, no external writeback. All commands default to dry-run / read-only.
Run inside the venv (`source .venv/bin/activate`) or prefix with `.venv/bin/`.

## 1. Check installed local models

```bash
hb-assistant second-brain local-model status --json
```

`daemon_reachable`, `ready`, `present_models`, and per-profile availability. If a model is missing,
the JSON lists the `ollama pull …` command to run. `--mock` shows the offline shape.

## 2. View routing (which profile serves a task)

```bash
hb-assistant second-brain local-model profiles --json          # all profiles + served task families
hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json
```

`route` returns the `selected_profile`, `fallback_chain`, `available`, and `reason_code`. Exit codes:
`0` routed, `1` fail-closed (daemon unreachable / no available model), `2` unknown task family.

## 3. Run the evaluation harness

```bash
# Offline, deterministic (CI-safe) — decisive recommendation per task family:
hb-assistant second-brain local-model eval --suite daily-brief --models auto --synthetic --json

# Live (real models; daemon required) — measure schema/redaction/latency reliability:
hb-assistant second-brain local-model eval --task-family daily_brief_synthesis_quality \
  --models mistral-nemo:12b --live --json
```

Read `recommendations[]` (recommended profile / blocked / reason) and `use_next_run` (the
task→profile map to adopt). `--models auto` = all enabled non-heavy profiles. Opt-in raw fixtures:
`--raw-fixtures-dir <DIR-OUTSIDE-REPO>` (a repo-contained path is refused, exit 2).

## 4. Run a daily brief with intelligence

```bash
# Standalone advisory intelligence for a date (dry-run; reads candidates, no DB write):
hb-assistant second-brain daily-brief intelligence --date 2026-06-09 --dry-run --json

# Integrated into the daily run (opt-in flag; advisory block attached to the run payload):
hb-assistant second-brain daily-run run --date 2026-06-09 --dry-run --with-intelligence \
  --no-open-browser --json
```

Check `enriched`, `metrics.bullets_kept`, `metrics.source_link_coverage` (1.0 by construction),
`metrics.usefulness_score`, and the `waiting_on_me` / `waiting_on_others` split.

## 5. Disable intelligence

It is **off by default**. Omit `--with-intelligence` on `daily-run run`, or simply don't call
`daily-brief intelligence`. The deterministic brief and the existing `--synthesize` path are
unaffected.

## 6. Interpret failure / fallback

`enriched=false` with a `withheld_reason` is **normal and safe** — the deterministic brief is
preserved. Common reasons: `daemon_unreachable` (start Ollama), `model_unavailable` (pull/enable the
model), `schema_invalid` (model output didn't validate after retries — re-run, or route to a more
reliable profile), `no_source_linked_bullets` (model cited nothing real), `redaction_failed:<cats>`
(output contained a forbidden token — withheld). The command still exits `0`.

## 7. Where outputs go

- Eval / route / intelligence: JSON on stdout only (no file written by default).
- `daily-run run` outputs (browser HTML, status, Obsidian) go to the app-support / governed paths it
  already uses — **outside the repo**.
- Live DB proof uses a **copy** of the working DB under `/tmp` (never the live DB for mutation).

## 8. How to avoid committing raw local outputs

- Never `git add` the `/tmp/*.json` receipts — they may contain model bullet text derived from local
  data. Evidence in `docs/evidence/phase-10-local-model-routing/` is **metrics-only**.
- Raw operator fixtures must live **outside** the repo; the loader refuses repo-contained paths.
- The redaction scanner runs on every surfaced payload; a hit withholds enrichment.

## 9. Intelligence daily-brief manual run + diagnostics (2026-06-09 remediation)

End-to-end manual run against a **copy** of the working DB (never the live DB):

```bash
# 1. Copy the (Dev) working DB to /tmp (candidates live there; production may be empty)
cp "$HOME/Library/Application Support/HB Personal Assistant (Dev)/db/hb-personal-assistant.sqlite" \
   /tmp/hb_daily_brief_intelligence_test.sqlite

# 2. Confirm the route (expect brief_synthesis / mistral-nemo:12b / selected_routed)
hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json

# 3. Standalone advisory intelligence (read-only; enriches already-persisted candidates)
hb-assistant second-brain daily-brief intelligence --date <YYYY-MM-DD> \
  --db /tmp/hb_daily_brief_intelligence_test.sqlite --dry-run --json

# 4. Integrated run (generate + advisory intelligence), suppressing browser/vault, apply on the copy
hb-assistant second-brain daily-run run --db /tmp/hb_daily_brief_intelligence_test.sqlite \
  --date <YYYY-MM-DD> --apply --max-persist-per-stage 10 --max-total-persist 30 \
  --with-intelligence --no-open-browser --no-generate-browser --json
```

### Reading the new diagnostics

- **Route vs terminal profile:** `route_selected_profile` is what the router chose (should be
  `brief_synthesis`); `terminal_profile_id` / `profile_id` is what actually generated. If they differ,
  `fallback_used=true` and `warnings` include `terminal_profile_differs_from_route`. The standalone
  `selected_profile` field now equals the route-selected profile.
- **Source linking:** the model cites short aliases (`c1, c2, …`) mapped back to canonical candidate
  ids. On success `metrics.source_link_coverage=1.0` and `metrics.alias_mapping_used=true`. Dropped
  cites show as `metrics.unknown_source_ids_count`.
- **Candidate availability:** `candidate_count`, `candidate_freshness`, and `candidate_availability`
  explain whether intelligence is operating on freshly applied vs pre-existing candidates. Standalone
  intelligence reads **already-persisted** candidates only — a dry-run daily-run discovers but does not
  persist, so fresh candidates require `--apply` (warnings:
  `requires_daily_run_apply_to_generate_candidates`, `dry_run_did_not_persist_new_candidates`).
- **Fail-closed:** `enriched=false` + a `withheld_reason` is safe (deterministic brief preserved).
  `metrics.schema_error_category` / `attempts` / `repair_attempted` explain a `schema_invalid` withhold
  without leaking raw model text. The command still exits `0`.
- **Synthetic vs live eval:** `eval --synthetic` reports `eval_mode=synthetic_offline_contract`
  (harness/contract proof, not model quality); `--live` reports `eval_mode=live_local_model`.

Metrics-only evidence for this remediation:
`docs/evidence/phase-10-intelligence-daily-brief-remediation/`.
