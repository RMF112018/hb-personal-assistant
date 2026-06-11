You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-email-followup-candidate-projection-package/`

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
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Use `/tmp` DB copies for apply validation.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, full recipient arrays, unbounded subjects, model prompts, or model responses.

# 04 — Candidate Persistence and Source Refs

## Objective

Persist email-derived candidates idempotently into domain tables and daily-brief candidate/source-ref tables.

## Required Behavior

For every generated candidate that passes persistence thresholds:

1. Persist to the appropriate domain table, as applicable:
   - `follow_up_watch_items`
   - `task_candidates`
   - `commitment_candidates`
   - `email_followup_enrichments` only if repo truth says this remains the active safe review table
2. Persist a daily-brief candidate through the central writer:
   - `daily_brief_action_candidates`
   - `candidate_source_refs`
3. Source refs are mandatory.
4. IDs must be deterministic.
5. Re-running on the same DB copy must not duplicate rows.
6. Existing partial rows missing refs must be repaired idempotently where safe.

## Section Mapping

Default mapping:

| Candidate Family | Daily Brief Section |
|---|---|
| `waiting_on_response` | `waiting` |
| `response_needed` | `follow_up` |
| `stale_thread_nudge` | `follow_up` |
| `user_commitment` | `actions` or `follow_up` based on existing conventions |
| `third_party_commitment` | `waiting` |
| `project_action_item` | `actions` |
| `time_sensitive_followup` | `follow_up` |

Use repo conventions if they differ, but document the mapping.

## Source Ref Contract

Use source refs like:

```python
{
    "source_family": "email_thread",
    "source_ref": f"thread:{thread_ref}",
    "source_table": "email_raw_thread_structured",
}
```

or:

```python
{
    "source_family": "email_message",
    "source_ref": f"message:{message_id_hash}",
    "source_table": "email_raw_message_structured",
}
```

The central writer must hash `source_ref`. Do not store raw private URLs or body refs as source refs.

## Validation

Add tests proving:

- candidate rows persist
- source refs persist
- duplicate runs do not duplicate
- source refs are repaired for existing candidates when applicable
- candidates without source refs are not persisted or are marked failed/degraded
- guard columns remain default/zero

## Evidence

Write:

`docs/evidence/phase-10-email-followup-candidate-projection/04-persistence-and-source-refs.md`
