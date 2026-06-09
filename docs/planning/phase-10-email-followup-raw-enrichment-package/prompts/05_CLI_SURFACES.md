# Prompt 05 — CLI Surfaces

## Objective

Expose controlled CLI surfaces for raw email follow-up enrichment and explicit raw-local operator preview.

## Scope

Add or extend CLI commands consistent with existing `hb-assistant second-brain` conventions.

## Required Surfaces

Implement the closest repo-style equivalents of:

```bash
hb-assistant second-brain follow-up-watch enrich   --candidate-id <candidate_id>   --db /tmp/hb_email_followup_raw_enrichment.sqlite   --dry-run
```

```bash
hb-assistant second-brain follow-up-watch enrich   --candidate-id <candidate_id>   --show-raw-local   --db /tmp/hb_email_followup_raw_enrichment.sqlite   --dry-run
```

```bash
hb-assistant second-brain follow-up-watch scan   --with-raw-enrichment   --db /tmp/hb_email_followup_raw_enrichment.sqlite   --dry-run   --json
```

```bash
hb-assistant second-brain follow-up-watch scan   --with-raw-enrichment   --apply   --max-persist 10   --db /tmp/hb_email_followup_raw_enrichment.sqlite   --json
```

If `follow-up-watch enrich` does not fit existing command style, choose the smallest coherent extension and document the reason.

## Raw-Local Preview CLI Rules

`--show-raw-local` must:

- Be explicit.
- Be unavailable in default JSON output.
- Print only bounded redacted local preview.
- Print a warning banner that preview is local-only and must not be copied into evidence.
- Never write raw preview to evidence/log files.
- Never imply raw preview was persisted.

If `--json` and `--show-raw-local` are both provided, default behavior should be to refuse with a clear error unless a separate diagnostic override exists. Prefer refusal.

## JSON Output Shape

Dry-run JSON should include:

```json
{
  "ok": true,
  "mode": "dry_run",
  "with_raw_enrichment": true,
  "would_persist": 0,
  "persisted": 0,
  "skipped": [],
  "enrichments": [
    {
      "candidate_id": "...",
      "watch_item_id": "...",
      "review_status": "pending",
      "enriched_title": "...",
      "waiting_state": "...",
      "suggested_next_action": "...",
      "confidence": 0.0,
      "source_refs": [],
      "raw_excerpt_hash": "sha256:..."
    }
  ]
}
```

No raw excerpt text may appear.

## Exit Code Rules

- Successful dry-run: 0
- Successful apply: 0
- No eligible items: 0 with clear report
- Model unavailable but deterministic fallback safe: 0 or repo-style degraded code, but JSON must report degraded status
- Apply without cap: nonzero
- Raw-local preview with JSON conflict: nonzero
- Raw leakage detected: nonzero
- DB unavailable: nonzero

## Required Tests

Add CLI tests for:

- Dry-run JSON writes nothing.
- Apply requires cap.
- Apply respects cap.
- `--show-raw-local` requires explicit flag.
- `--show-raw-local --json` is refused or safely handled.
- JSON output contains no raw text.
- CLI reports model unavailable clearly.
- CLI reports no eligible items clearly.
- Exit codes match expectations.

## Stop Conditions

Stop if:

- Existing CLI structure cannot support this without broad unrelated refactor.
- Raw preview would leak into JSON snapshots.
- Apply can happen through an existing command path without caps.

## Commit

After tests pass:

```bash
git add <cli files> <tests>
git commit -m "feat(cli): expose raw follow-up enrichment surfaces"
```

## Exit Criteria

- CLI surfaces added.
- Raw-local preview controlled.
- JSON output raw-free.
- Tests pass.
- Commit created.
