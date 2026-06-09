# Phase 10 — Email Follow-Up Raw Enrichment Implementation Package

## Objective

Implement the next Phase 10 candidate in `RMF112018/hb-personal-assistant`:

**Email follow-up / raw enrichment**

This package is designed for a local code agent to execute in one shot using:

```bash
Execute the objective defined at /Users/bobbyfetting/hb-personal-assistant/docs/planning/phase-10-email-followup-raw-enrichment-package/README.md
```

If the package is being run from another location, substitute the absolute package path.

The implementation must add controlled, local-only raw email enrichment to improve:

- follow-up quality
- open-loop detection
- waiting-on-me / waiting-on-others classification
- source-linked daily brief intelligence
- operator review usefulness

The implementation must not introduce email send, draft creation, cloud LLM use, raw persistence in normal candidate tables, raw evidence leakage, production DB mutation during validation, Graph writeback, calendar mutation, Procore writeback, MCP raw exposure, or any external writeback.

## Resolved Product Decisions

Bobby selected the following decisions after the audit:

1. **Expose raw-local operator preview.**
2. **Include a V45 review-safe enrichment table in the implementation.**
3. **Allow the daily brief to consume pending enriched fields**, provided those fields are clearly labeled as model-enriched / pending review and remain source-linked and raw-free.

These are authoritative for this package.

## Repository

- GitHub repository: `RMF112018/hb-personal-assistant`
- Local path: `/Users/bobbyfetting/hb-personal-assistant`
- Expected implementation branch: `experiment/phase-10-email-followup-raw-enrichment`
- Expected base: current `main` after `git fetch origin` and `git pull --ff-only origin main`

## Current Context to Verify, Not Assume

Prior audit context found:

- The recent intelligence remediation branch was merged through PR #11.
- Current GitHub `main` was observed at merge commit `d7c13a88e937163923eacc26329adebc6e4cec1f`.
- Previous experiment branch head was `c49caedc5fea2c3d20e3f03be172f205f74f8907`.
- Schema head was V44 before this package.
- The next implementation should branch from current `main`, not from the old intelligence remediation branch.

Treat this as context only. Repo truth is authoritative. Prompt 00 requires fresh verification.

## Hard Constraints

The local agent must obey all constraints below.

### Git / Repository Constraints

- Do not modify `main` directly.
- Do not merge.
- Do not rebase.
- Do not force-push.
- Create a new experiment branch from fresh `main`.
- Keep commits surgical and phase-scoped.
- Do not touch unrelated files except where required by tests or import wiring.
- Do not commit untracked local config such as `config/config.yml`.
- If `config/config.yml` exists and is untracked, treat it as foreign/local and leave untouched.

### Runtime / External Writeback Constraints

- Do not send emails.
- Do not create email drafts.
- Do not mutate calendar data.
- Do not perform Procore writeback.
- Do not perform Graph writeback.
- Do not perform MCP raw exposure.
- Do not perform any external writeback.
- Do not use cloud LLMs.
- Do not mutate production DB during validation.
- Use DB copies for live proof.

### Raw Content Constraints

- Do not store raw email body in normal candidate tables.
- Do not store raw email body in the V45 enrichment table.
- Do not store raw prompts.
- Do not store raw model responses.
- Do not store tokens, secrets, signed URLs, join URLs, download URLs, or unsafe HTML.
- Do not put raw snippets in committed evidence, docs, logs, browser brief, Obsidian brief, or test artifacts.
- Raw email content may be loaded only for bounded local operator preview or ephemeral local model context.
- Raw-local preview must require an explicit flag and must be bounded, redacted, local-only, and excluded from JSON/evidence by default.

### Apply / Persistence Constraints

- Default behavior must remain dry-run / plan-safe.
- Apply must require explicit `--apply` plus bounded caps such as `--max-persist`.
- Persistence must be idempotent.
- Persistence must be source-linked.
- Persistence must be review-safe.
- Persisted rows must contain only structured/redacted fields and hashes.

## Target Architecture

Implement a unified local task family:

```text
email_followup_raw_enrichment
```

The workflow:

```text
accepted_tasks / accepted_commitments / follow_up_watch_items
        |
        v
eligible source-linked email refs only
        |
        v
ephemeral raw email window builder
        |  - no raw DB writes
        |  - no raw packet persistence
        |  - quote/signature stripping
        |  - URL/token/email redaction
        |  - per-message and total caps
        v
local model structured output
        |
        v
validation gates
        |  - schema valid
        |  - source refs valid
        |  - no raw leakage
        |  - confidence/reason thresholds
        v
V45 review-safe enrichment table
        |
        v
review surfaces + pending daily brief fields
```

## Required Prompt Chain

Execute the prompts in order. Each prompt has explicit exit criteria. Do not proceed to the next prompt until the current one is complete and committed unless the prompt says otherwise.

1. `prompts/00_PREFLIGHT_REPO_TRUTH_AUDIT.md`
2. `prompts/01_V45_SCHEMA_AND_CONTRACTS.md`
3. `prompts/02_RAW_WINDOW_SANITIZER_AND_PREVIEW.md`
4. `prompts/03_LOCAL_MODEL_ROUTE_AND_STRUCTURED_OUTPUT.md`
5. `prompts/04_ENRICHMENT_ENGINE_AND_PERSISTENCE.md`
6. `prompts/05_CLI_SURFACES.md`
7. `prompts/06_DAILY_BRIEF_PENDING_ENRICHMENT.md`
8. `prompts/07_TESTS_VALIDATION_AND_EVIDENCE.md`
9. `prompts/08_DOCS_RUNBOOK_AND_FINAL_HANDOFF.md`

## Expected Commit Sequence

Use the exact order unless repo truth requires a small adjustment. Each commit should be clean, tested, and self-contained.

1. `audit(email-raw-enrichment): record repo truth and implementation plan gates`
2. `feat(schema): add V45 email follow-up enrichment table`
3. `feat(email): add bounded raw follow-up window sanitizer and local preview`
4. `feat(local-ai): add email follow-up raw enrichment route and contracts`
5. `feat(follow-up): persist review-safe raw enrichment results`
6. `feat(cli): expose raw follow-up enrichment surfaces`
7. `feat(daily-brief): consume pending email enrichment safely`
8. `test(email): add raw enrichment validation and no-leakage proof`
9. `docs(email): add raw enrichment runbook and evidence handoff`

If the implementation naturally requires fewer commits, that is acceptable only if the final handoff clearly maps each required scope to a commit.

## Required CLI Surfaces

Add or extend commands consistent with existing CLI conventions. The final exact names should follow repo style, but the target surfaces are:

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

Later daily-run integration must be explicit:

```bash
hb-assistant second-brain daily-run run   --with-email-raw-enrichment   --db /tmp/hb_email_followup_raw_enrichment.sqlite   --dry-run   --json
```

Do not add raw-local preview to daily-run.

## V45 Persistence Strategy

Add a V45 migration for a new table equivalent to:

```text
email_followup_enrichments
```

The table must contain review-safe structured fields and hashes only. It must not contain raw body, raw excerpt text, raw prompt, raw response, HTML, URLs, tokens, or secrets.

See `reference/V45_TABLE_SPEC.md`.

## Daily Brief Rule

Daily brief may consume pending enrichment fields, but each pending item must be clearly labeled. Use wording equivalent to:

```text
Model-enriched / pending review
```

The brief must never include raw excerpts. It may include structured fields such as title, waiting state, suggested next action, due date, confidence band, source/candidate references, and review status.

## Required Evidence Directory

Create evidence under:

```text
docs/evidence/phase-10-email-followup-raw-enrichment/
```

Evidence must be redacted and raw-free. Use `templates/EVIDENCE_MANIFEST_TEMPLATE.md`.

## Required Tests

At minimum, add tests for:

- V45 fresh migration.
- V45 migration on copied DB.
- V45 table contains no raw-content columns.
- Guard columns remain zero.
- Raw window excludes attachments and HTML.
- Raw window strips quoted replies.
- Raw window strips signatures.
- Raw window redacts URLs, tokens, join links, signed/download URLs, and email addresses.
- Raw-local preview requires explicit flag.
- Raw-local preview is not emitted in JSON by default.
- Structured output schema enforcement.
- Unknown source refs are rejected.
- Hallucinated candidate/watch refs are rejected.
- Model unavailable degrades cleanly.
- Dry-run writes nothing.
- Apply requires cap.
- Apply is idempotent.
- Daily brief labels pending enriched fields.
- Daily brief does not include raw excerpts.
- Forbidden-string scan passes.

## Stop Conditions

Stop and report before proceeding if any of the following occurs:

- Repo is not on a clean implementation branch.
- `main` has unmerged local changes.
- Required schema migration pattern is unclear.
- Existing raw packet builder cannot be used safely without persisting raw packet JSON.
- Any test or evidence path emits raw email content.
- Raw prompt or raw model response is persisted.
- Daily brief includes raw excerpts.
- Pending enrichment appears without review/pending label.
- Apply can run without caps.
- External writeback code is touched or invoked.
- Production DB is mutated.
- Local model routing can fall back to cloud.
- Guard columns are nonzero.
- Forbidden-string scan finds a real leak.

## Final Handoff

Use `templates/FINAL_HANDOFF_TEMPLATE.md` for the final response.

The final handoff must include:

- Branch and HEAD.
- Commit list.
- Changed files.
- Schema version and migration summary.
- CLI surfaces added.
- Safety guarantees.
- Test commands and results.
- Evidence files.
- DB-copy proof.
- Production DB unchanged proof.
- Known limitations.
- Exact next operator command to run.
