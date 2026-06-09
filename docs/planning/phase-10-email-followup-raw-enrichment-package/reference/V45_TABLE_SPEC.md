# Reference — V45 Review-Safe Enrichment Table Spec

## Purpose

Persist model-enriched follow-up metadata derived from bounded local raw email context without persisting raw email content.

## Preferred Table Name

```text
email_followup_enrichments
```

Adapt to repo naming conventions if necessary.

## Required Properties

- Review-safe.
- Source-linked.
- Idempotent.
- Hash-only raw reference.
- No raw body/prompt/response.
- No unsafe URLs/tokens/HTML.
- Compatible with pending daily-brief consumption.

## Suggested Columns

```sql
CREATE TABLE email_followup_enrichments (
    enrichment_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    source_candidate_id TEXT NOT NULL,
    source_candidate_type TEXT NOT NULL,
    watch_item_id TEXT,
    email_thread_ref_hash TEXT,
    email_message_ref_hashes_json TEXT NOT NULL DEFAULT '[]',
    raw_excerpt_hash TEXT NOT NULL,
    enriched_title TEXT NOT NULL,
    waiting_state TEXT NOT NULL,
    assignee_type TEXT NOT NULL,
    assignee_display TEXT,
    suggested_next_action TEXT,
    due_at_utc TEXT,
    confidence REAL NOT NULL,
    reason_codes_json TEXT NOT NULL DEFAULT '[]',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    review_status TEXT NOT NULL DEFAULT 'pending',
    model_task TEXT NOT NULL DEFAULT 'email_followup_raw_enrichment',
    model_profile_id TEXT,
    prompt_template_version TEXT NOT NULL,
    input_context_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    created_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL,

    -- Add the exact Phase 10 guard columns used by existing tables.
    -- These must default to 0 and remain 0 in proof.
    -- Examples only; use actual repo guard-column names.
    unsafe_raw_body_present INTEGER NOT NULL DEFAULT 0,
    unsafe_raw_prompt_present INTEGER NOT NULL DEFAULT 0,
    unsafe_raw_response_present INTEGER NOT NULL DEFAULT 0,
    unsafe_html_present INTEGER NOT NULL DEFAULT 0,
    unsafe_url_present INTEGER NOT NULL DEFAULT 0,
    unsafe_token_present INTEGER NOT NULL DEFAULT 0,
    unsafe_secret_present INTEGER NOT NULL DEFAULT 0,
    unsafe_external_writeback_present INTEGER NOT NULL DEFAULT 0,
    unsafe_email_send_present INTEGER NOT NULL DEFAULT 0,
    unsafe_graph_writeback_present INTEGER NOT NULL DEFAULT 0,
    unsafe_calendar_writeback_present INTEGER NOT NULL DEFAULT 0,
    unsafe_procore_writeback_present INTEGER NOT NULL DEFAULT 0,
    unsafe_mcp_raw_exposure_present INTEGER NOT NULL DEFAULT 0
);
```

Use actual repo guard names and schema conventions.

## Required Indexes

At minimum:

```sql
CREATE INDEX idx_email_followup_enrichments_candidate
    ON email_followup_enrichments(source_candidate_id);

CREATE INDEX idx_email_followup_enrichments_watch_item
    ON email_followup_enrichments(watch_item_id);

CREATE INDEX idx_email_followup_enrichments_review_status
    ON email_followup_enrichments(review_status);

CREATE INDEX idx_email_followup_enrichments_waiting_state
    ON email_followup_enrichments(waiting_state);

CREATE INDEX idx_email_followup_enrichments_created_utc
    ON email_followup_enrichments(created_utc);
```

## Disallowed Column Names / Semantics

Do not add columns containing raw content or unsafe egress. Disallowed unless explicitly hash-only and named accordingly:

```text
body
body_text
body_html
html
raw_text
raw_body
raw_prompt
raw_response
prompt
response
url
token
secret
signed_url
download_url
join_url
```

Allowed:

```text
raw_excerpt_hash
input_context_hash
output_hash
email_thread_ref_hash
```

## Review Status Values

Suggested:

```text
pending
accepted
rejected
superseded
```

If existing review status values exist, reuse them.

## Daily Brief Consumption

Rows with `review_status = pending` may be consumed by the daily brief only if labeled:

```text
Model-enriched / pending review
```

No raw excerpts may appear in daily brief output.
