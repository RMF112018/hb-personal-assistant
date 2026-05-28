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
from hb_assistant.procore.normalizers.rfi import normalize_rfi_reply
from hb_assistant.procore.normalizers.submittal import (
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
    return normalize_rfi_reply(
        raw, parent_procore_id="rfi-parent-1", **_common_kwargs()
    )


def _normalize_submittal(blob: str) -> Dict[str, Any]:
    raw = {"id": "s1", "comment": blob}
    return normalize_submittal_response(
        raw, parent_procore_id="sub-parent-1", **_common_kwargs()
    )


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
