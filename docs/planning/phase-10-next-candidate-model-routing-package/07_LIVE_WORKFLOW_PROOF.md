# 07 — Live Workflow Proof

## Objective

Prove actual workflow behavior on a safe DB copy and temp output paths. The goal is not just unit tests; prove the local agent behavior produces useful, source-linked, safe output.

## Scope boundaries

- Use DB copy only unless Bobby explicitly approves live DB mutation.
- Use temp output paths outside repo.
- No raw evidence committed.
- No cloud LLM.
- No external writes.

Hard constraints:
- Do not modify `main`. Work only on the approved experiment branch for this package.
- Do not merge, rebase main, or imply a merge.
- No cloud LLM submission unless Bobby separately approves it.
- No automatic email send.
- No calendar mutation.
- No Procore writeback.
- No Graph writeback.
- No external writeback.
- No MCP raw exposure.
- No production DB mutation unless explicitly approved.
- No destructive migration unless explicitly approved.
- No credential/auth changes unless explicitly approved.
- No raw email/calendar/Procore/document body content committed to repo.
- No raw prompts, raw model responses, signed URLs, download URLs, join URLs, access tokens, refresh tokens, secrets, credential material, or unsafe HTML committed to repo, evidence, docs, tests, or logs.
- Raw local content may be used only for local operator consumption where explicitly allowed and must never be persisted to guarded candidate/evidence tables.
- Default persisted rows and repo evidence must remain redacted/guarded.
- Any apply/persist behavior must be capped, bounded, idempotent, source-linked, and review-safe.


## Required workflow proof

1. Create DB copy:
```bash
cp "<resolved local dev db path>" /tmp/hb_model_routing_brief_quality.sqlite
```

2. Run model eval:
```bash
.venv/bin/hb-assistant second-brain local-model eval \
  --suite daily-brief \
  --models auto \
  --db /tmp/hb_model_routing_brief_quality.sqlite \
  --json | tee /tmp/hb_model_eval_daily_brief.json
```

3. Run route proof:
```bash
.venv/bin/hb-assistant second-brain local-model route \
  --task-family daily_brief_synthesis_quality \
  --json | tee /tmp/hb_model_route_daily_brief.json
```

4. Run deterministic brief baseline:
```bash
.venv/bin/hb-assistant second-brain daily-run run \
  --db /tmp/hb_model_routing_brief_quality.sqlite \
  --dry-run \
  --no-open-browser \
  --json | tee /tmp/hb_daily_run_baseline.json
```

5. Run intelligence-enabled dry-run:
```bash
.venv/bin/hb-assistant second-brain daily-run run \
  --db /tmp/hb_model_routing_brief_quality.sqlite \
  --dry-run \
  --with-intelligence \
  --no-open-browser \
  --json | tee /tmp/hb_daily_run_intelligence.json
```

6. If apply/write exists for intelligence sidecar, use conservative cap and temp output only:
```bash
.venv/bin/hb-assistant second-brain daily-run run \
  --db /tmp/hb_model_routing_brief_quality.sqlite \
  --apply \
  --max-persist-per-stage 5 \
  --max-total-persist 10 \
  --with-intelligence \
  --output-root /tmp/hb_daily_brief_model_routing_outputs \
  --no-open-browser \
  --json | tee /tmp/hb_daily_run_intelligence_apply.json
```

Adjust commands to actual implementation.

## Required proof checks

- Eval metrics generated.
- Router selected a local-only profile.
- Deterministic fallback works when the selected model is disabled/missing.
- Intelligence output has source candidate IDs.
- No raw prompt/response in JSON.
- Redaction scans pass.
- Guard columns remain zero.
- DB source tables unchanged.
- Apply is capped/idempotent where applicable.
- Daily-run status remains accurate.

## Operator usefulness proof

Provide redacted metrics:
- Number of bullets generated.
- Source-link coverage.
- Number of generic/filler bullets rejected.
- Number of high-priority items surfaced.
- Number of meetings with prep notes.
- Waiting-on-me / waiting-on-others counts if available.
- Latency per model/profile.

## Evidence commit

Commit only redacted evidence:
- `docs/evidence/<new-folder>/README.md`
- machine-readable redacted metrics if repo convention allows.
- No raw prompts/responses.

Suggested evidence folder:
`docs/evidence/phase-10-local-model-routing/`

## Stop conditions

- Any raw prompt/response would need to be committed.
- Source-link coverage is below an acceptable threshold and cannot be fixed.
- Model output fails JSON/schema reliability below useful threshold.
- Redaction scan fails.
- Daily-run baseline regresses.

## Commit behavior

Commit evidence:

```bash
git add docs/evidence/phase-10-local-model-routing
git commit -m "docs(evidence): prove local model routing brief quality"
```

## Final response format

Return:
- Workflow commands run.
- DB copy path.
- Metrics.
- Guardrail proof.
- Usefulness proof.
- Evidence path.
