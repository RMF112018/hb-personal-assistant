# 145 — Phase 09 Prompt 26 Daily Brief Approved-Source Population

Status: implemented. Builds on records 120-144 and supersedes the Phase 08A daily-brief default output
path recorded in 68.

## Problem

Phase 09 approved-source discovery was empty because new daily briefs were written under
`Work/HB Personal Assistant/12_Daily_Brief`, while the approved Obsidian index policy only scans approved
generated-output roots such as `Construction Intelligence/Phase 08A Daily Briefs`.

The apply-with-receipt failure was a separate receipt-idempotency bug. The live schema confirms
`second_brain_research_packets.packet_id TEXT PRIMARY KEY`; the only other index is the non-unique
`ix_second_brain_research_packets_project`. Daily-brief research packets intentionally use a deterministic
`packet_id`, so repeated `--emit-receipt` runs attempted to insert the same primary key.

## Fix

- `write_research_packet_receipt` now uses `ON CONFLICT(packet_id) DO UPDATE` for the same metadata fields
  the writer already records. It preserves `created_utc`, does not add `updated_utc`, and leaves all guard
  columns untouched at the schema-enforced zero defaults.
- New daily-brief approved outputs default to
  `Construction Intelligence/Phase 08A Daily Briefs/<date>_daily_brief.md`. Explicit `vault_brief_dir`
  overrides are unchanged.
- Applied, source-linked daily-brief runs are now admitted to the Phase 09 approved-source manifest through
  the `generated_outputs` family using only `daily_brief_runs` metadata (`brief_run_id` hash, output content
  hash, review tier/status/confidence). The Obsidian index dry-run remains the proof that the generated note
  is in an approved root and marker-bounded; an Obsidian apply manifest can also contribute
  `approved_obsidian_outputs`.
- Old `Work/HB Personal Assistant/12_Daily_Brief` notes are treated as local orphan outputs from the prior
  behavior. They are not migrated or deleted automatically.

## Guardrails

No raw content, external writeback, notification, HTML rendering, vector apply, prompts, responses, tokens,
URLs, or source-system payloads are introduced. Daily-brief receipts remain metadata-only and source-linked.
The approved-source manifest remains a metadata enumerator; it does not build embeddings or vectors.

## Verification

Post-change results:

- `python -m compileall src tests` — passed.
- `ruff check .` — passed.
- `mypy src` — passed, 294 source files.
- `pytest -m "not live and not integration and not manual"` — passed, 3194 passed / 6 deselected /
  23 warnings. The first sandboxed run failed only on Graph status DNS resolution; the required rerun was
  performed outside the restricted sandbox and passed.
- `hb-assistant second-brain daily-brief generate --date 2026-06-05 --mode apply --emit-receipt --json`
  — passed; wrote `Construction Intelligence/Phase 08A Daily Briefs/2026-06-05_daily_brief.md`.
- Repeated `hb-assistant second-brain daily-brief generate --date 2026-06-05 --mode dry_run
  --emit-receipt --json` — passed twice without `IntegrityError`.
- `hb-assistant second-brain index obsidian --dry-run --json` — passed; `entry_count=1` under
  `Construction Intelligence/Phase 08A Daily Briefs`.
- `hb-assistant second-brain index linkage-proof --json` — passed; `proof_passed=true`,
  `guard_sum=0`, `entry_count=1`.
- `hb-assistant second-brain retrieval approved-sources build --json` — passed;
  `approved_ref_count=2`, `approved_family_count=1`, contributed by `generated_outputs`.
- `hb-assistant second-brain retrieval approved-sources proof --json` — passed; `proof_passed=true`.

Acceptance requires apply-with-receipt and repeated dry-run receipts to avoid `IntegrityError`, the dry-run
Obsidian index to report at least one approved daily-brief entry, and approved-source build to report
`approved_ref_count > 0` with contributing family counts visible.
