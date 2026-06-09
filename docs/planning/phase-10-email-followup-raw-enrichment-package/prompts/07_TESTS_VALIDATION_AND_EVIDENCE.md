# Prompt 07 — Tests, Validation, and Evidence

## Objective

Run the complete validation matrix, prove no raw leakage, prove DB-copy behavior, and create redacted evidence.

## Required Evidence Directory

Create:

```text
docs/evidence/phase-10-email-followup-raw-enrichment/
```

Use `templates/EVIDENCE_MANIFEST_TEMPLATE.md` as the README basis.

## Required Validation Commands

Run repo-style equivalents. Prefer broad tests if runtime permits.

Minimum:

```bash
python -m pytest tests -q
ruff check src tests
mypy src
```

If broad `ruff` or `mypy` surfaces pre-existing unrelated failures, do not fix unrelated files without permission. Instead:

- Prove changed files are clean.
- Prove targeted tests pass.
- Record unrelated failures clearly in evidence/final handoff.

## DB-Copy Live Proof

Use a copied DB only. Never mutate production DB.

Suggested pattern:

```bash
SOURCE_DB="<path-to-dev-or-production-db>"
PROOF_DB="/tmp/hb_email_followup_raw_enrichment_proof.sqlite"
cp "$SOURCE_DB" "$PROOF_DB"
```

Then run:

```bash
.venv/bin/hb-assistant second-brain follow-up-watch scan   --with-raw-enrichment   --db "$PROOF_DB"   --dry-run   --json > /tmp/email_raw_enrichment_dry_run.json
```

Then run capped apply:

```bash
.venv/bin/hb-assistant second-brain follow-up-watch scan   --with-raw-enrichment   --db "$PROOF_DB"   --apply   --max-persist 10   --json > /tmp/email_raw_enrichment_apply.json
```

Then rerun apply for idempotency:

```bash
.venv/bin/hb-assistant second-brain follow-up-watch scan   --with-raw-enrichment   --db "$PROOF_DB"   --apply   --max-persist 10   --json > /tmp/email_raw_enrichment_apply_again.json
```

Only commit redacted summaries, not raw outputs if they risk content exposure.

## Required Proofs

Create redacted evidence files for:

- branch state
- schema version and V45 table introspection
- fresh DB migration
- copied DB migration
- raw sanitizer proof
- raw-local preview behavior proof using synthetic data only
- structured output proof
- route/local-only proof
- dry-run writes-nothing proof
- apply with cap proof
- idempotency proof
- model-unavailable proof
- guard-column proof
- daily brief pending-label proof
- forbidden-string scan proof
- production DB unchanged proof

## Forbidden String Scan

Run scans over:

- generated evidence directory
- CLI JSON artifacts selected for evidence
- daily brief browser output generated in proof
- Obsidian output generated in proof
- test snapshots if any

Use `validation/FORBIDDEN_STRING_SCAN_GUIDE.md`.

At minimum search for patterns equivalent to:

```text
http://
https://
Bearer 
Authorization:
access_token
refresh_token
id_token
client_secret
BEGIN PRIVATE KEY
join.microsoft.com
teams.microsoft.com/l/meetup-join
zoom.us/j/
body_html
raw_prompt
raw_response
```

Also scan for real known local sensitive strings only if Bobby has provided a safe private local pattern list. Do not commit that list.

## Guard Column Proof

Use existing repo schema guard patterns. Prove all Phase 10 guard columns remain zero for the new V45 table and existing relevant tables.

## Stop Conditions

Stop if:

- Any raw content appears in committed evidence.
- Forbidden scan finds real leaks.
- Production DB changes.
- Apply is not idempotent.
- Guard columns nonzero.
- Daily brief includes raw excerpts.
- Raw preview appears in JSON/evidence.

## Commit

After tests/evidence pass:

```bash
git add docs/evidence/phase-10-email-followup-raw-enrichment <tests if not already committed>
git commit -m "test(email): add raw enrichment validation and no-leakage proof"
```

If tests were already committed in previous prompts and only evidence is added, use:

```bash
git commit -m "test(email): add raw enrichment evidence proof"
```

## Exit Criteria

- Validation complete.
- Evidence complete and raw-free.
- Commit created.
