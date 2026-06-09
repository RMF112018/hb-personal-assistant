"""Phase 10 V45 — local-only model route + structured-output validation tests (offline).

Proves the ``email_followup_raw_enrichment`` task family routes local-only with no cloud fallback,
the strict output schema accepts valid JSON and rejects invalid enums / raw leakage, cross-context
validation rejects unknown cited refs and hash mismatches, and an unavailable local model degrades
cleanly without a backend call.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from hb_assistant.construction.second_brain.local_ai.contracts import load_local_model_profiles
from hb_assistant.construction.second_brain.local_ai.email_followup_route import (
    TASK_FAMILY,
    EmailFollowupEnrichmentOutput,
    build_enrichment_prompt,
    find_raw_leak,
    route_email_followup,
    run_email_followup_model,
    validate_enrichment_output,
)
from hb_assistant.construction.second_brain.local_ai.model_router import (
    load_local_model_task_routing,
)
from hb_assistant.construction.second_brain.local_ai.raw_followup_window import (
    RawFollowupWindow,
    RawWindowCaps,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient

_PRESENT = {"mistral-nemo:12b", "llama3.1:8b", "qwen2.5:14b"}


def _window() -> RawFollowupWindow:
    return RawFollowupWindow(
        candidate_id="cand-1",
        candidate_type="task",
        subject_sanitized="RFI response",
        window_text="[email_msg:abc] please confirm the slab schedule.",
        raw_excerpt_hash="sha256:deadbeef0123",
        source_aliases=["email_msg:abc"],
        message_ref_hashes=["abc"],
        thread_ref_hash="sha256:thread01",
        message_count=1,
        caps=RawWindowCaps(),
        meta={},
        blockers=[],
    )


def _valid_output() -> dict:
    return {
        "enriched_title": "Send revised RFI response",
        "waiting_state": "waiting_on_me",
        "assignee_type": "me",
        "assignee_display": "Bobby",
        "suggested_next_action": "Draft and send the revised RFI response.",
        "due_at_utc": None,
        "confidence": 0.82,
        "reason_codes": ["direct_ask"],
        "cited_source_aliases": ["email_msg:abc"],
        "cited_candidate_ids": ["cand-1"],
        "cited_watch_item_ids": [],
        "raw_excerpt_hash": "sha256:deadbeef0123",
    }


def test_route_exists() -> None:
    routing = load_local_model_task_routing()
    assert TASK_FAMILY in routing.routes


def test_route_is_local_only_no_cloud_fallback() -> None:
    profiles = load_local_model_profiles()
    route = route_email_followup(profiles=profiles, present_models=_PRESENT)
    assert route.available is True
    assert route.no_cloud is True
    assert route.model_name in _PRESENT
    # every profile in the fallback chain is a local (ollama) profile
    by_id = {p.profile_id: p for p in profiles.profiles}
    for pid in route.fallback_chain:
        assert by_id[pid].provider == "ollama"


def test_schema_accepts_valid_json() -> None:
    out = EmailFollowupEnrichmentOutput.model_validate(_valid_output())
    assert out.waiting_state == "waiting_on_me"


def test_schema_rejects_invalid_enum() -> None:
    bad = {**_valid_output(), "waiting_state": "totally_made_up"}
    with pytest.raises(ValidationError):
        EmailFollowupEnrichmentOutput.model_validate(bad)


def test_schema_rejects_extra_field() -> None:
    bad = {**_valid_output(), "raw_email_body": "leak"}
    with pytest.raises(ValidationError):
        EmailFollowupEnrichmentOutput.model_validate(bad)


def test_schema_rejects_raw_leak_in_action() -> None:
    bad = {**_valid_output(), "suggested_next_action": "see https://evil.example.com/x"}
    with pytest.raises(ValidationError):
        EmailFollowupEnrichmentOutput.model_validate(bad)


def test_find_raw_leak_categories() -> None:
    assert find_raw_leak("ping http://x.y") == "url"
    assert find_raw_leak("Bearer abc123") == "bearer"
    assert find_raw_leak("a@b.com") == "email"
    assert find_raw_leak("<div>hi</div>") == "html"
    assert find_raw_leak("clean text") is None


def test_unknown_source_alias_rejected() -> None:
    out = EmailFollowupEnrichmentOutput.model_validate(
        {**_valid_output(), "cited_source_aliases": ["email_msg:NOT_PROVIDED"]}
    )
    v = validate_enrichment_output(
        out, allowed_aliases=["email_msg:abc"], allowed_candidate_ids=["cand-1"],
        allowed_watch_item_ids=[], raw_excerpt_hash="sha256:deadbeef0123",
    )
    assert "cited_alias_not_in_input" in v


def test_unknown_candidate_and_watch_rejected() -> None:
    out = EmailFollowupEnrichmentOutput.model_validate(
        {**_valid_output(), "cited_candidate_ids": ["ghost"], "cited_watch_item_ids": ["w-ghost"]}
    )
    v = validate_enrichment_output(
        out, allowed_aliases=["email_msg:abc"], allowed_candidate_ids=["cand-1"],
        allowed_watch_item_ids=[], raw_excerpt_hash="sha256:deadbeef0123",
    )
    assert "cited_candidate_not_in_input" in v
    assert "cited_watch_item_not_in_input" in v


def test_hash_mismatch_rejected() -> None:
    out = EmailFollowupEnrichmentOutput.model_validate(_valid_output())
    v = validate_enrichment_output(
        out, allowed_aliases=["email_msg:abc"], allowed_candidate_ids=["cand-1"],
        allowed_watch_item_ids=[], raw_excerpt_hash="sha256:DIFFERENT",
    )
    assert "raw_excerpt_hash_mismatch" in v


def test_invented_deadline_rejected() -> None:
    out = EmailFollowupEnrichmentOutput.model_validate(
        {**_valid_output(), "due_at_utc": "2026-07-01T00:00:00+00:00", "reason_codes": ["direct_ask"]}
    )
    v = validate_enrichment_output(
        out, allowed_aliases=["email_msg:abc"], allowed_candidate_ids=["cand-1"],
        allowed_watch_item_ids=[], raw_excerpt_hash="sha256:deadbeef0123",
    )
    assert "due_date_unsupported" in v


def test_valid_output_passes_cross_context() -> None:
    out = EmailFollowupEnrichmentOutput.model_validate(_valid_output())
    v = validate_enrichment_output(
        out, allowed_aliases=["email_msg:abc"], allowed_candidate_ids=["cand-1"],
        allowed_watch_item_ids=[], raw_excerpt_hash="sha256:deadbeef0123",
    )
    assert v == []


def test_run_model_ok_offline() -> None:
    profiles = load_local_model_profiles()
    res = run_email_followup_model(
        window=_window(),
        candidate_meta={"candidate_id": "cand-1", "candidate_type": "task"},
        profiles=profiles,
        present_models=_PRESENT,
        backend=StaticOutputClient(json.dumps(_valid_output())),
        dry_run=True,
    )
    assert res["status"] == "ok"
    assert res["validated"]["enriched_title"] == "Send revised RFI response"
    assert res["route"]["no_cloud"] is True


def test_run_model_unavailable_degrades_without_backend_call() -> None:
    profiles = load_local_model_profiles()
    backend = StaticOutputClient(json.dumps(_valid_output()))
    res = run_email_followup_model(
        window=_window(),
        candidate_meta={"candidate_id": "cand-1", "candidate_type": "task"},
        profiles=profiles,
        present_models=set(),  # no local models installed → route blocked
        backend=backend,
        dry_run=True,
    )
    assert res["status"] == "blocked"
    assert res["validated"] is None
    assert backend.call_count == 0  # fail-closed: no generation attempted


def test_run_model_rejects_hallucinated_citation() -> None:
    profiles = load_local_model_profiles()
    bad = {**_valid_output(), "cited_candidate_ids": ["ghost"]}
    res = run_email_followup_model(
        window=_window(),
        candidate_meta={"candidate_id": "cand-1", "candidate_type": "task"},
        profiles=profiles,
        present_models=_PRESENT,
        backend=StaticOutputClient(json.dumps(bad)),
        dry_run=True,
    )
    assert res["status"] == "invalid"
    assert "cited_candidate_not_in_input" in res["violations"]


def test_prompt_exposes_aliases_and_hash() -> None:
    system, prompt, ctx = build_enrichment_prompt(
        window=_window(), candidate_meta={"candidate_id": "cand-1", "candidate_type": "task"}
    )
    assert "email_msg:abc" in ctx
    assert "sha256:deadbeef0123" in ctx
    assert "Do NOT output URLs" in system
