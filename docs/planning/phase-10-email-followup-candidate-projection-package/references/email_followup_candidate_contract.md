# Email Follow-Up Candidate Contract

## Internal Candidate Object

```python
@dataclass(frozen=True)
class EmailFollowupCandidate:
    candidate_key: str
    family: str
    source_family: str
    source_table: str
    source_ref: str
    message_id_hash: str | None
    thread_ref: str | None
    project_key: str | None
    project_resolution_status: str
    title_redacted: str
    reason_redacted: str
    recommended_next_action: str
    priority: int
    confidence: float
    due_bucket: str | None
    stale_bucket: str | None
    raw_access_used: bool
```

## Candidate Families

- `waiting_on_response`
- `response_needed`
- `stale_thread_nudge`
- `user_commitment`
- `third_party_commitment`
- `project_action_item`
- `time_sensitive_followup`

## Text Bounds

- `title_redacted`: max 120 chars.
- `reason_redacted`: max 240 chars.
- `recommended_next_action`: max 160 chars.
- No raw body, raw HTML, private URL, token, secret, or full recipient list.

## Persistence Thresholds

- Persist domain candidates when `confidence >= 0.55`, except commitments require `>= 0.70` unless repo truth has a stricter standard.
- Persist daily-brief candidates when `confidence >= 0.55` and a source ref exists.
- Do not persist daily-brief candidates without refs.
- If candidate is project-like but unresolved, persist with `project_key = NULL` and review-required status only if repo conventions support this; otherwise report in stage status/data gap.
