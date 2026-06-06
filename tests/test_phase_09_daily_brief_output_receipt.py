"""Phase 09 Addendum — daily-brief output receipt + deferred import policy tests."""

from __future__ import annotations

import json
import re

import pytest

from hb_assistant.construction.second_brain.daily_brief import rendered_quality as rq
from hb_assistant.construction.second_brain.daily_brief.output_receipt import (
    IMPORT_ENABLED,
    RENDERED_OUTPUT_CLASS,
    RenderedOutputReceiptError,
    build_daily_brief_rendered_output_receipt_proof,
    build_rendered_brief_receipt,
    build_trusted_packet_receipt,
    import_rendered_brief,
)
from hb_assistant.construction.second_brain.retrieval import ALLOWLISTED_SOURCE_FAMILIES

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|access_token|refresh_token|client_secret"
)


def _packet():
    return rq._sample_packet()


def _rendered_receipt(packet):
    return build_rendered_brief_receipt(
        packet=packet,
        rendered_path="<vault>/Construction Intelligence/Phase 09 Rendered Daily Briefs/d.md",
        renderer="claude_scheduled_task",
        validation_passed=True,
    )


def test_packet_receipt_does_not_contain_raw_content() -> None:
    receipt = build_trusted_packet_receipt(packet=_packet())
    blob = json.dumps(receipt, default=str)
    assert not _SECRET_OR_URL.search(blob)
    assert "@" not in blob  # no email-shaped values
    assert receipt["metadata_only"] is True


def test_rendered_receipt_does_not_mark_rendered_as_source_truth() -> None:
    receipt = _rendered_receipt(_packet())
    assert receipt["not_source_truth"] is True
    assert receipt["advisory_only"] is True
    assert receipt["output_class"] == RENDERED_OUTPUT_CLASS


def test_rendered_output_excluded_from_vector_index() -> None:
    receipt = _rendered_receipt(_packet())
    assert receipt["imported_to_vector_index"] is False
    # The rendered output class is not a retrieval/embeddable family.
    assert RENDERED_OUTPUT_CLASS not in ALLOWLISTED_SOURCE_FAMILIES


def test_rendered_output_excluded_from_accepted_memory() -> None:
    receipt = _rendered_receipt(_packet())
    assert receipt["imported_to_memory"] is False
    assert RENDERED_OUTPUT_CLASS != "accepted_long_term_memory"


def test_optional_import_is_disabled_and_deferred() -> None:
    assert IMPORT_ENABLED is False
    receipt = _rendered_receipt(_packet())
    assert receipt["import_enabled"] is False
    with pytest.raises(RenderedOutputReceiptError):
        import_rendered_brief(receipt)


def test_receipt_references_packet_id_and_hash() -> None:
    packet = _packet()
    receipt = _rendered_receipt(packet)
    assert receipt["packet_id"] == packet["packet_id"]
    assert receipt["packet_hash"] and len(receipt["packet_hash"]) == 48


def test_proof_passes_and_writes_artifacts(tmp_path) -> None:
    proof = build_daily_brief_rendered_output_receipt_proof(
        evidence_dir=str(tmp_path), write_evidence=True
    )
    assert proof["proof_passed"] is True
    for name, value in proof["checks"].items():
        assert value is True, name
    for fname in (
        "daily-brief-rendered-output-receipt-proof.json",
        "daily-brief-rendered-output-receipt-proof.md",
    ):
        assert (tmp_path / fname).exists(), fname
    assert not _SECRET_OR_URL.search(
        (tmp_path / "daily-brief-rendered-output-receipt-proof.json").read_text()
    )
