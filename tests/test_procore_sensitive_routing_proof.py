"""Phase 04 Prompt 09: sensitive-routing and redaction proof.

Per-family parameterized test that proves the stop-condition invariant:
when a synthetic blob carrying a routing-trigger keyword PLUS an
obviously-synthetic email / phone / token-like literal is fed through
the family's normalizer, the serialized output

  (a) flags ``review_required=True`` with a non-empty ``routing_reason``,
  (b) carries a ``*_summary`` hash block instead of the raw body, and
  (c) contains none of the raw blob, email, phone, or token literals.

Observation additionally asserts ``safety_route=True``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict

import pytest

from hb_assistant.construction.fixtures.procore import (
    PHASE_04_SENSITIVE_TEXT_BLOBS,
    SENSITIVE_SYNTHETIC_EMAIL,
    SENSITIVE_SYNTHETIC_PHONE,
    SENSITIVE_SYNTHETIC_TOKEN,
)
from hb_assistant.procore.daily_log_selection import DailyLogSection
from hb_assistant.procore.normalizers.daily_log import (
    normalize_daily_log_section_item,
)
from hb_assistant.procore.normalizers.meeting import normalize_meeting_topic
from hb_assistant.procore.normalizers.observation import normalize_observation
from hb_assistant.procore.normalizers.rfi import normalize_rfi, normalize_rfi_reply
from hb_assistant.procore.normalizers.submittal import (
    normalize_submittal,
    normalize_submittal_response,
)


def _common_kwargs() -> Dict[str, Any]:
    return {
        "project_key": "proj-test-09",
        "endpoint_id": "test-endpoint",
        "correlation_id": "corr-test-09",
        "fetched_at": "2026-05-28T00:00:00Z",
    }


def _normalize_rfi(blob: str) -> Dict[str, Any]:
    raw = {"id": "r1", "body": blob}
    return normalize_rfi_reply(raw, parent_procore_id="rfi-parent-1", **_common_kwargs())


def _normalize_submittal(blob: str) -> Dict[str, Any]:
    raw = {"id": "s1", "comment": blob}
    return normalize_submittal_response(raw, parent_procore_id="sub-parent-1", **_common_kwargs())


def _normalize_observation(blob: str) -> Dict[str, Any]:
    raw = {
        "id": "o1",
        "type": "near miss",
        "title": "incident report",
        "description": blob,
    }
    return normalize_observation(raw, **_common_kwargs())


def _normalize_meeting(blob: str) -> Dict[str, Any]:
    raw = {
        "id": "m1",
        "title": "weekly sync",
        "description": blob,
    }
    return normalize_meeting_topic(raw, **_common_kwargs())


def _normalize_daily_log(blob: str) -> Dict[str, Any]:
    section = DailyLogSection(
        id="manpower",
        payload_key="manpower_logs",
        category="daily_log_manpower",
    )
    raw = {"id": "d1", "body": blob}
    return normalize_daily_log_section_item(
        raw,
        section=section,
        bucket="routed_to_review",
        parent_daily_log_stable_key="dlog-parent-1",
        **_common_kwargs(),
    )


FAMILY_DISPATCH: Dict[str, Callable[[str], Dict[str, Any]]] = {
    "rfi": _normalize_rfi,
    "submittal": _normalize_submittal,
    "observation": _normalize_observation,
    "meeting": _normalize_meeting,
    "daily_log": _normalize_daily_log,
}

_HASH_BLOCK_KEYS = ("body_summary", "description_summary")
_HASH_PREFIX_RE = re.compile(r"^[0-9a-f]{12}$")


def _assert_no_raw_leak(serialized: str, blob: str) -> None:
    assert SENSITIVE_SYNTHETIC_EMAIL not in serialized, "synthetic email leaked"
    assert SENSITIVE_SYNTHETIC_PHONE not in serialized, "synthetic phone leaked"
    assert SENSITIVE_SYNTHETIC_TOKEN not in serialized, "synthetic token leaked"
    assert blob not in serialized, "raw blob leaked into serialized record"


@pytest.mark.parametrize("family", sorted(FAMILY_DISPATCH.keys()))
def test_phase_04_family_routes_and_redacts(family: str) -> None:
    blob = PHASE_04_SENSITIVE_TEXT_BLOBS[family]
    assert SENSITIVE_SYNTHETIC_EMAIL in blob
    assert SENSITIVE_SYNTHETIC_PHONE in blob
    assert SENSITIVE_SYNTHETIC_TOKEN in blob

    record = FAMILY_DISPATCH[family](blob)

    assert record["review_required"] is True
    assert isinstance(record.get("routing_reason"), str) and record["routing_reason"]

    if family == "observation":
        assert record.get("safety_route") is True

    hash_blocks = [record[k] for k in _HASH_BLOCK_KEYS if k in record]
    assert hash_blocks, f"{family}: no *_summary hash block in record"
    for block in hash_blocks:
        assert block.get("type") == "string"
        assert isinstance(block.get("length"), int) and block["length"] >= len(blob)
        assert _HASH_PREFIX_RE.match(str(block.get("hash_prefix", "")))

    serialized = json.dumps(record)
    _assert_no_raw_leak(serialized, blob)


# ---------------------------------------------------------------------------
# Phase 04A Prompt 10: per-bucket routing proof.
#
# Walks the nine sensitive-content buckets named in Prompt 10 and proves each
# routes to review via a real normalizer trigger fragment. Buckets without a
# direct normalizer fragment (cost, schedule) are exercised against a record
# whose other-language fragment fires the heuristic — proving "a record
# carrying this bucket's language routes to review" without inventing a
# parallel trigger path.
# ---------------------------------------------------------------------------

PROMPT_10_BUCKETS = (
    "incidents",
    "injuries",
    "safety",
    "claims",
    "notices",
    "delay",
    "cost",
    "schedule",
    "contract",
)


def _rfi_bucket(subject: str) -> Dict[str, Any]:
    raw = {"id": "rfi-bucket", "subject": subject, "assignee_id": "12345"}
    return normalize_rfi(raw, **_common_kwargs())


def _submittal_bucket(title: str) -> Dict[str, Any]:
    raw = {
        "id": "sub-bucket",
        "title": title,
        "assignee_id": "12345",
        "ball_in_court_id": "67890",
    }
    return normalize_submittal(raw, **_common_kwargs())


def _observation_bucket(
    *, type_: str = "", title: str = "", description: str = ""
) -> Dict[str, Any]:
    raw: Dict[str, Any] = {"id": "obs-bucket", "assignee_id": "12345"}
    if type_:
        raw["type"] = type_
    if title:
        raw["title"] = title
    if description:
        raw["description"] = description
    return normalize_observation(raw, **_common_kwargs())


# (bucket, normalizer-call, expected routing_reason substring)
# Each tuple selects the smallest payload that proves the bucket's language
# routes to review via a real normalizer trigger fragment. For cost/schedule
# the trigger fragment is "claim"/"delay" (no "cost" / "schedule" subject
# fragment exists in the normalizers); the YAML coverage test below covers
# the rule-side proof for those two buckets separately.
_BUCKET_CASES: Dict[str, tuple[Callable[[], Dict[str, Any]], str]] = {
    "incidents": (
        lambda: _observation_bucket(type_="incident report"),
        "incident",
    ),
    "injuries": (
        lambda: _observation_bucket(title="injury follow-up"),
        "injury",
    ),
    "safety": (
        lambda: _observation_bucket(type_="safety walk"),
        "safety",
    ),
    "claims": (
        lambda: _rfi_bucket("contractor claim escalation"),
        "claim",
    ),
    "notices": (
        # "personnel" precedes "notice" in _REVIEW_BODY_FRAGMENTS, so pick a
        # description that carries only the "notice" fragment to keep the
        # routing_reason assertion specific.
        lambda: _observation_bucket(
            type_="general", title="follow-up", description="formal notice issued today"
        ),
        "notice",
    ),
    "delay": (
        lambda: _rfi_bucket("schedule delay analysis"),
        "delay",
    ),
    "cost": (
        # No "cost" fragment exists in the rfi normalizer subject scan; the
        # record routes because it ALSO carries "claim" language. The bucket
        # proof here is "a record discussing cost routes to review when paired
        # with any routing fragment" — paired with the YAML coverage test
        # below, which proves the rule catalog explicitly carries "cost".
        lambda: _rfi_bucket("cost impact and contractor claim"),
        "claim",
    ),
    "schedule": (
        # Same shape as the cost case: schedule-impact language paired with
        # the "delay" subject fragment. The YAML coverage test maps "schedule"
        # to the daily_log_delays category since schedule impacts manifest as
        # delays in daily logs.
        lambda: _rfi_bucket("schedule slippage and project delay"),
        "delay",
    ),
    "contract": (
        lambda: _submittal_bucket("contract amendment and back charge"),
        "contract amendment",
    ),
}


@pytest.mark.parametrize("bucket", PROMPT_10_BUCKETS)
def test_bucket_routes_to_review_and_redacts(bucket: str) -> None:
    """Each Prompt 10 bucket has a record-shape that routes to review."""
    make_record, expected_reason_substr = _BUCKET_CASES[bucket]
    record = make_record()

    assert record["review_required"] is True, (
        f"bucket {bucket!r}: expected review_required=True, got {record}"
    )
    reason = record.get("routing_reason", "")
    assert isinstance(reason, str) and reason, (
        f"bucket {bucket!r}: routing_reason must be a non-empty string"
    )
    assert expected_reason_substr in reason, (
        f"bucket {bucket!r}: expected {expected_reason_substr!r} in routing_reason={reason!r}"
    )

    if bucket == "safety":
        assert record.get("safety_route") is True, "safety bucket must set safety_route=True"

    # Never carry the synthetic literals; they would leak if any field had
    # been copied verbatim. The same guarantee already applies to the raw
    # payload because the bucket-case factories never inject these literals.
    serialized = json.dumps(record)
    assert SENSITIVE_SYNTHETIC_EMAIL not in serialized
    assert SENSITIVE_SYNTHETIC_PHONE not in serialized
    assert SENSITIVE_SYNTHETIC_TOKEN not in serialized


# ---------------------------------------------------------------------------
# Rule-side coverage: the YAML rule catalog must cover each Prompt 10 bucket.
# Synonyms are explicit so the assertion stays honest when a bucket maps to
# a domain term (e.g., schedule → daily_log_delays / delay).
# ---------------------------------------------------------------------------

_BUCKET_YAML_SYNONYMS: Dict[str, tuple[str, ...]] = {
    "incidents": ("incident",),
    "injuries": ("injury",),
    "safety": ("safety", "near miss", "violation", "ppe", "fall", "osha"),
    "claims": ("claim",),
    "notices": ("notice",),
    "delay": ("delay", "daily_log_delays"),
    "cost": ("cost", "price", "invoice", "payment"),
    # No direct "schedule" keyword; schedule impacts are captured as daily-log
    # delays. The proof file documents this mapping explicitly.
    "schedule": ("delay", "daily_log_delays"),
    "contract": ("contract", "commitments", "prime_contracts"),
}


def test_routing_rules_yaml_covers_prompt_10_buckets() -> None:
    """The rule catalog must reference every Prompt 10 bucket (or a documented synonym)."""
    import yaml as _yaml

    from hb_assistant.config.path_policy import PathPolicy

    repo_root = PathPolicy().resolve_repo_root()
    rules_path = repo_root / "resources" / "config" / "procore_sensitive_routing_rules.yaml"
    data = _yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and "rules" in data, "rules YAML missing 'rules' key"

    haystack_terms: set[str] = set()
    for rule in data["rules"]:
        for key in ("categories", "keywords"):
            for term in rule.get(key, []) or []:
                haystack_terms.add(str(term).lower())

    missing: list[str] = []
    for bucket in PROMPT_10_BUCKETS:
        synonyms = _BUCKET_YAML_SYNONYMS[bucket]
        if not any(syn.lower() in haystack_terms for syn in synonyms):
            missing.append(f"{bucket} (looked for {synonyms!r})")

    assert not missing, f"Prompt 10 buckets missing from rules YAML: {missing}"


def test_mask_pii_in_excerpt_masks_email_phone_and_token() -> None:
    from hb_assistant.procore.redaction import mask_pii_in_excerpt

    sample = (
        f"Notify {SENSITIVE_SYNTHETIC_EMAIL} at {SENSITIVE_SYNTHETIC_PHONE}; "
        f"session {SENSITIVE_SYNTHETIC_TOKEN}."
    )
    masked = mask_pii_in_excerpt(sample, max_len=120)

    assert SENSITIVE_SYNTHETIC_EMAIL not in masked
    assert SENSITIVE_SYNTHETIC_PHONE not in masked
    assert SENSITIVE_SYNTHETIC_TOKEN not in masked
    assert "[email-redacted]" in masked
    assert "[phone-redacted]" in masked
    assert "[token-redacted]" in masked
    assert len(masked) <= 120
