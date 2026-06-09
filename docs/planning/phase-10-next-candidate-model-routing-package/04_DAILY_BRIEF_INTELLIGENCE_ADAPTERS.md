# 04 — Daily-Brief Intelligence Adapters

## Objective

Use the model router to add optional local-only advisory daily-brief intelligence that improves operator usefulness without replacing deterministic candidate generation.

## Scope boundaries

- Advisory enrichment only.
- Deterministic candidates remain authoritative.
- No external writeback.
- No raw prompts/responses persisted.
- Default behavior must remain safe if local model is unavailable.

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


## Implementation instructions

Add a module such as:

- `src/hb_assistant/local_ai/daily_brief_intelligence.py`

Required behavior:
- Input is the already-built daily brief candidate set plus approved safe/raw-local-only consumption fields when explicitly enabled.
- Output is structured JSON with:
  - executive catch-up paragraph(s).
  - top priorities.
  - open loops.
  - waiting-on-me / waiting-on-others breakdown.
  - meeting prep highlights.
  - Procore/project risk highlights.
  - source candidate IDs for every generated bullet.
  - confidence and reason codes.
- Every generated item must be source-linked to candidate IDs or rejected.
- Must include usefulness rubric fields for evaluation.
- Must be optional via CLI flag and config; default deterministic brief still works.
- If model fails, JSON invalid, schema invalid, source links missing, or redaction scan fails, enrichment is withheld and the pipeline falls back to deterministic brief.

Raw local content boundary:
- `--raw` may improve local operator consumption output only if existing raw output boundaries allow it.
- Do not write raw enriched content to repo evidence.
- Do not persist raw prompt/response to DB.
- Do not insert raw model text into guarded candidate tables unless redaction guard and schema explicitly allow a safe summary row.

Recommended integration:
- Add an optional stage after deterministic synthesis and before render/daily-run output.
- It may produce a local-only sidecar JSON/Markdown section for browser/Obsidian consumption, or a safe redacted advisory row, depending on repo truth.
- Prefer sidecar/read-only consumption over schema changes unless schema is clearly justified.

## Required tests

- Model success with synthetic fixtures.
- Model invalid JSON -> fallback deterministic.
- Missing source links -> reject/withhold.
- Redaction failure -> reject/withhold.
- Local model unavailable -> deterministic fallback.
- `--raw` boundary tests.
- No DB mutation by default.
- If apply/persist exists, cap/idempotency/guard columns zero.

## Live validation required

On a DB copy or safe temp path:

```bash
.venv/bin/hb-assistant second-brain daily-brief intelligence --date YYYY-MM-DD --dry-run --json
.venv/bin/hb-assistant second-brain daily-run run --dry-run --with-intelligence --json
```

Use final command names chosen by implementation.

## Agent-output validation

Evaluate at least:
- Does it identify what changed since the prior business day?
- Does it separate "waiting on me" from "waiting on others"?
- Does every bullet have source candidate IDs?
- Does it avoid generic filler?
- Does it highlight meetings and preparation items clearly?
- Does it avoid unsafe raw egress?

## Evidence required

- Redacted before/after structure comparison.
- Metrics, no raw content.
- Source-link coverage percentage.
- Fallback proof.
- Usefulness rubric output.

## Stop conditions

- Enrichment requires raw prompt/response persistence.
- Enrichment cannot guarantee source links.
- Enrichment degrades deterministic daily-run success.
- Output cannot pass redaction scan.

## Commit behavior

Commit required:

```bash
git add ...
git commit -m "feat(daily-brief): add local model intelligence enrichment"
```

## Final response format

Return:
- Integration point.
- CLI flags.
- Fallback behavior.
- Tests.
- Live DB-copy proof.
- Guardrail proof.
