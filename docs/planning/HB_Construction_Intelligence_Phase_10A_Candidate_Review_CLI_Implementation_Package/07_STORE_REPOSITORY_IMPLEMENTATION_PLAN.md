# 07 Store Repository Implementation Plan

## Likely target file

`src/hb_assistant/construction/store/repositories.py`

Reconfirm locally before editing.

## Add candidate read methods

Implement methods similar to:

```python
def get_task_candidate(self, candidate_id: str) -> dict[str, Any] | None: ...
def get_commitment_candidate(self, candidate_id: str) -> dict[str, Any] | None: ...
def get_candidate(self, candidate_id: str, candidate_type: str | None = None) -> CandidateLookupResult: ...
```

## Add list method

Implement a parameterized query builder for:

```python
def list_review_candidates(
    self,
    *,
    status: str = "pending",
    candidate_type: str = "all",
    safety_category: str | None = None,
    assignee_class: str | None = None,
    waiting_state: str | None = None,
    urgency: str | None = None,
    model_profile_id: str | None = None,
    source_family: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    sort: str = "newest",
    limit: int = 25,
) -> list[dict[str, Any]]: ...
```

Use `UNION ALL` across task and commitment tables. Normalize commitment actor as `assignee_class` in output or expose both `actor_class` and normalized `assignee_class` clearly.

## Add update methods

```python
def update_candidate_review_state(...): ...
def update_candidate_fields(...): ...
def insert_candidate_review_event(...): ...
```

## Event insert requirement

Do not swallow event insert failures. Either raise a typed error or return a structured failure that the service/CLI propagates.

## Source refs

Continue using the existing `list_candidate_source_refs()` or add a candidate-specific variant:

```python
def list_candidate_source_refs_for_candidate(candidate_type: str, candidate_id: str) -> list[dict[str, Any]]: ...
```

Only return safe fields.
