# Runbook — Phase 10 Email Follow-Up Raw Enrichment (V45)

Local-only, dry-run-first operator workflow for enriching source-linked follow-up items from a
bounded, sanitized, NON-persisted local raw email window, and consuming the results in the daily
brief. No cloud LLM, no email send/draft, no Graph/calendar/Procore/external writeback.

## Preconditions

- Repo venv active; use the real toolchain `.venv/bin/python3.12` / `.venv/bin/hb-assistant`
  (bare `python` is an empty 3.14).
- Schema head V45 (applied automatically on first `ConstructionStore` open / migration).
- A local Ollama daemon with `mistral-nemo:12b` for live enrichment. Without it the engine
  fail-closes (degraded, nothing persisted) — this is safe.
- Eligibility: enrichment only touches accepted task/commitment candidates that are **email
  source-linked** (`candidate_source_refs` with an email source family) and **open**.

## Safe DB-copy setup (never mutate production)

```bash
SOURCE_DB="$(.venv/bin/python3.12 -c 'from hb_assistant.config.path_policy import PathPolicy; print(PathPolicy().get_db_path())')"
PROOF_DB="/tmp/hb_email_followup_raw_enrichment_proof.sqlite"
rm -f "$PROOF_DB" && cp "$SOURCE_DB" "$PROOF_DB"
shasum -a 256 "$SOURCE_DB"   # record BEFORE
```

## Dry-run (default; zero writes)

```bash
.venv/bin/hb-assistant second-brain follow-up-watch enrich --db "$PROOF_DB" --dry-run --json
# or additively alongside the deterministic watch scan:
.venv/bin/hb-assistant second-brain follow-up-watch scan --with-raw-enrichment --db "$PROOF_DB" --dry-run --json
```

## Raw-local preview (terminal-only; never evidence)

```bash
.venv/bin/hb-assistant second-brain follow-up-watch enrich \
  --candidate-id <candidate_id> --show-raw-local --dry-run --no-json --db "$PROOF_DB"
```

`--show-raw-local` REQUIRES `--dry-run` + `--no-json`; it is refused with `--json` or `--apply`. The
preview is bounded + redacted, prints a warning banner, and is never persisted or written to
evidence/logs.

## Apply with caps (on the DB copy)

```bash
.venv/bin/hb-assistant second-brain follow-up-watch enrich \
  --db "$PROOF_DB" --apply --max-persist 10 --json
# idempotency: rerun the same command → row count must not grow
.venv/bin/hb-assistant second-brain follow-up-watch enrich \
  --db "$PROOF_DB" --apply --max-persist 10 --json
```

`--apply` REQUIRES a positive `--max-persist` (else exit 2). Persistence is idempotent.

## Daily brief (pending enrichment consumption)

```bash
.venv/bin/hb-assistant second-brain daily-run run \
  --with-email-raw-enrichment --db "$PROOF_DB" --dry-run --json
```

Pending rows appear under `email_raw_enrichment`, each labeled **"Model-enriched / pending review"**
(low-confidence → "low confidence / needs review"), source-linked and raw-free. No raw-local preview
is available on `daily-run`.

## Evidence generation

```bash
# evidence bundle (raw-free, redacted):
docs/evidence/phase-10-email-followup-raw-enrichment/
# forbidden-string scan: see validation/FORBIDDEN_STRING_SCAN_GUIDE.md in the package
```

## Production DB unchanged

```bash
shasum -a 256 "$SOURCE_DB"   # record AFTER — must equal BEFORE
```

All validation runs on `/tmp` copies; production is read+copied, never written.

## Failure modes (all safe)

- No local model → `model_unavailable`, nothing persisted (exit 0; degraded reported in JSON).
- No eligible candidates → `note: no_eligible_candidates` (exit 0).
- Missing raw content for an item → skipped `no_raw_content_available`.
- Model output cites unknown refs / hash mismatch / invented deadline → withheld (`validation_failed`).
- Raw leak detected in any persisted field → row withheld, exit nonzero (hard safety signal).
- `--apply` without `--max-persist` → exit 2.

## What is NEVER persisted / surfaced

Raw email body, raw excerpts, raw prompts, raw model responses, body HTML, URLs, signed/download/
join links, tokens/secrets, email-address dumps. Only structured/redacted fields + SHA-256[:12]
hashes + opaque source aliases/refs.

## What operators may inspect locally

The bounded, redacted raw-local preview via `--show-raw-local --dry-run --no-json` (terminal only).

## Rollback

- Stop passing `--with-raw-enrichment` / `--with-email-raw-enrichment`; do not run `enrich`. The V45
  table can remain inert if unconsumed.
- Do not run `--show-raw-local` unless previewing.
- If needed, revert the feature commits in reverse order on the experiment branch.
- No production DB rollback is needed (validation used copies; apply is capped + idempotent). If V45
  ever reaches production, roll back via migration policy + DB backup.
```
