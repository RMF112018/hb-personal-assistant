# 05 — CLI Operator and Reporting Surfaces

## Objective

Expose operator-friendly CLI surfaces for local model evaluation, routing, and daily-brief intelligence quality without adding a web UI.

## Scope boundaries

- CLI only unless repo truth shows an existing minimal status surface that should be extended.
- No scheduler changes except optional status visibility.
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


## CLI surfaces

Implement or finalize:

```bash
hb-assistant second-brain local-model profiles --json
hb-assistant second-brain local-model route --task-family <family> --json
hb-assistant second-brain local-model eval --suite daily-brief --models auto --json
hb-assistant second-brain daily-brief intelligence --date YYYY-MM-DD --dry-run --json
hb-assistant second-brain daily-run run --with-intelligence --dry-run --json
```

Adjust names to repo conventions, but keep the operator intent.

## JSON output requirements

Every command must emit:
- `ok`.
- `applied`.
- `dry_run`.
- `task_family` where applicable.
- `models_attempted` where applicable.
- `selected_profile`.
- `blockers`.
- `warnings`.
- `metrics`.
- `redaction_passed`.
- no raw prompts/responses.

## Required tests

- Typer CLI help.
- JSON output shape.
- Exit codes:
  - 0 success.
  - 1 runtime/eval failure with safe fallback not available.
  - 2 misuse/config/unsafe path.
- Dry-run default.
- Raw path refusal for repo-contained raw fixture/output locations.
- No raw leakage in stdout/stderr.

## Live validation required

Run:
```bash
.venv/bin/hb-assistant second-brain local-model profiles --json
.venv/bin/hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json
.venv/bin/hb-assistant second-brain local-model eval --suite daily-brief --models auto --json
.venv/bin/hb-assistant second-brain daily-brief intelligence --date YYYY-MM-DD --dry-run --json
```

## Evidence required

- Help text excerpts.
- JSON receipts.
- Exit code proof.
- No raw leakage proof.

## Stop conditions

- CLI cannot be made backward-compatible.
- Commands are too broad/ambiguous to be safe.
- JSON output includes raw prompt/response.

## Commit behavior

Commit required:

```bash
git add ...
git commit -m "feat(cli): expose local model routing and brief intelligence commands"
```

## Final response format

Return:
- CLI commands added.
- JSON shapes.
- Exit code behavior.
- Tests and live proof.
