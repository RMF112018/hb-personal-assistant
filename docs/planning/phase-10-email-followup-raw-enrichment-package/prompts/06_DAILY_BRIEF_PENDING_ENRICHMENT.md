# Prompt 06 — Daily Brief Pending Enrichment Integration

## Objective

Allow the daily brief to consume pending email follow-up enrichments safely, without raw excerpts, and with clear pending-review labeling.

## Scope

Integrate V45 enrichment rows into the relevant daily brief synthesis/intelligence/render path.

## Required Behavior

Daily brief may consume enrichment rows with:

```text
review_status = pending
```

But every pending enrichment must be labeled equivalent to:

```text
Model-enriched / pending review
```

Do not include raw excerpts.

Do not include raw prompt/model response.

Do not include URLs/tokens/body HTML/email dumps.

Daily brief should include only structured fields:

- enriched title
- waiting state
- suggested next action
- due date if present
- confidence band or score
- source/candidate/watch refs
- review status
- reason codes when useful

## Fallback Behavior

If no enrichments exist or model enrichment fails:

- Existing deterministic daily brief output must continue.
- No fatal failure should occur solely because raw enrichment is unavailable.
- JSON/status should report enrichment unavailable/degraded where relevant.

## Source-Linking

Every enrichment-derived brief item must retain link-back to:

- V45 enrichment ID
- candidate ID
- watch item ID when present
- source refs / aliases as repo convention supports

## CLI / Daily-Run Option

Add an explicit daily-run/daily-brief flag only if appropriate after inspecting existing surfaces, equivalent to:

```bash
hb-assistant second-brain daily-run run   --with-email-raw-enrichment   --db /tmp/hb_email_followup_raw_enrichment.sqlite   --dry-run   --json
```

Do not add raw-local preview to daily-run.

## Required Tests

Add tests proving:

- Pending enrichment appears in daily brief with pending/model label.
- Accepted/reviewed enrichment appears without misleading pending label, if review status supports accepted.
- Daily brief contains no raw excerpt.
- Daily brief contains no URL/token/body HTML.
- Source/candidate/watch refs survive.
- Missing enrichment table or no rows degrades cleanly.
- Existing deterministic daily brief tests still pass.

## Stop Conditions

Stop if:

- Daily brief architecture would require raw excerpts to render value.
- Pending enrichment cannot be labeled clearly.
- Existing source-linking would be broken.

## Commit

After tests pass:

```bash
git add <daily brief files> <tests>
git commit -m "feat(daily-brief): consume pending email enrichment safely"
```

## Exit Criteria

- Daily brief consumes pending enrichments safely.
- Labeling/source-link tests pass.
- No raw leakage.
- Commit created.
