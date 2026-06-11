You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-daily-brief-effectiveness-ranking-policy-telemetry-package/`

Before doing anything else:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git status --short
git branch --show-current
git rev-parse HEAD
```

Stop if you are on `main` or if unexplained dirty files are present.

Hard safety constraints:

- Do not mutate the production DB.
- Use `/tmp` DB copies for apply validation.
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Do not mutate lifecycle state or source refs from telemetry.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, local paths, raw Procore payloads, model prompts, or model responses.
- Telemetry is observational only.

# 00 — Repo Truth Audit

## Objective

Conduct a fresh repo-truth audit before coding. This prompt is read-only and must produce raw-free evidence.

## Commands

```bash
rg -n "LATEST_SCHEMA_VERSION|V51|V52|daily_brief_ranking_runs|daily_brief_ranked_candidates|candidate_similarity_edges|daily_brief_assembly_runs|daily_brief_assembly_sections|ranking_run_id|assembly_run_id|model_layer_status|deterministic_fallback_used|feedback_digest_hash|candidate_set_hash" src tests docs

rg -n "candidate_lifecycle|review_queue|feedback|accepted|rejected|snoozed|merged|suppressed|closed|reopened|stale|review_required|review-required|ignored|outcome|read_model" src tests docs

rg -n "daily brief|daily_brief|render|markdown|html|browser|preview|assembly|section|status_block|rank-candidates|brief_date|daily-run|daily_run" src tests docs

rg -n "deterministic_score|feedback_score|model_advisory_score|final_score|rank_position|section_key|group_key|duplicate_cluster_id|model_profile_id|model_name|model_receipt_id|model_status|degraded_reason|withheld|timeout|receipt|local_model_run_receipts|StructuredOutputClient|StaticOutputClient" src tests docs

rg -n "scan_text_for_forbidden|no-raw|raw leak|leak scan|forbidden|jwt|bearer|private_key|url|email|token|signed URL|full body|raw_content|include-raw-content|receipt_hash|prompt_hash|output_hash|evidence" src tests docs

rg -n "Typer|typer.Option|typer.Exit|# noqa: B008|daily-brief|rank-candidates|local-model status|--dry-run|--apply|--json|--db|--max-persist|_redact_db_indicator" src tests docs

find tests -maxdepth 2 -type f | sort | sed -n '1,260p'
```

## Evidence

Write:

`docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/00-repo-truth-audit.md`

Include branch, HEAD, schema head, ranking/assembly symbols found/missing, lifecycle sources, render/CLI points, scanner command/helper, test layout, and exact next decision.

Do not edit code in this prompt.
