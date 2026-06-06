"""Phase 09 Addendum — daily-brief output receipt + deferred import policy tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

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
    rendered_brief_filename,
    resolve_rendered_brief_path,
    write_rendered_brief,
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
        rendered_path="<vault>/Work/Daily Brief/2026-06-06-daily-brief.md",
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


# --- Prompt 04: output path + receipt policy ------------------------------------------------------


def test_output_path_is_correct() -> None:
    resolved = resolve_rendered_brief_path("2026-06-06")
    assert str(resolved).endswith("Work/Daily Brief/2026-06-06-daily-brief.md")


def test_filename_is_date_stable() -> None:
    assert rendered_brief_filename("2026-06-06") == "2026-06-06-daily-brief.md"
    # stable across repeated calls; varies per date.
    assert rendered_brief_filename("2026-06-06") == rendered_brief_filename("2026-06-06")
    assert rendered_brief_filename("2026-01-02") == "2026-01-02-daily-brief.md"


def test_write_creates_dir_with_spaces_and_no_sidecar(tmp_path: Path) -> None:
    # Path with spaces (mirrors the real "Obsidian Vault" / "Daily Brief" layout).
    vault_dir = tmp_path / "Obsidian Vault" / "Work" / "Daily Brief"
    assert not vault_dir.exists()
    result = write_rendered_brief(
        brief_date="2026-06-06",
        body="# Daily Brief — 2026-06-06\n\nadvisory body\n",
        vault_brief_dir=str(vault_dir),
        apply=True,
    )
    assert result["written"] is True
    assert result["persisted_to_sqlite"] is False
    target = vault_dir / "2026-06-06-daily-brief.md"
    assert target.exists()
    assert "advisory body" in target.read_text(encoding="utf-8")
    # Only the single rendered file is written — no DB/sidecar persistence.
    assert [p.name for p in vault_dir.iterdir()] == ["2026-06-06-daily-brief.md"]


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    vault_dir = tmp_path / "Work" / "Daily Brief"
    result = write_rendered_brief(
        brief_date="2026-06-06",
        body="advisory body",
        vault_brief_dir=str(vault_dir),
        apply=False,
    )
    assert result["written"] is False
    assert result["content_hash"]  # hash still computed
    assert result["persisted_to_sqlite"] is False
    assert not vault_dir.exists()


def test_receipt_is_metadata_only() -> None:
    body = "# Daily Brief — 2026-06-06\n\nthe full rendered narrative body text\n"
    receipt = _rendered_receipt(_packet())
    allowed_keys = {
        "receipt_kind",
        "output_class",
        "packet_id",
        "packet_hash",
        "rendered_file_path",
        "rendered_utc",
        "renderer",
        "validation_proof_status",
        "location_policy",
        "advisory_only",
        "not_source_truth",
        "imported_to_memory",
        "imported_to_vector_index",
        "imported_to_source_manifest",
        "imported_to_source_linked_proof",
        "persisted_to_sqlite",
        "external_writeback",
        "import_enabled",
    }
    assert set(receipt) <= allowed_keys
    assert not ({"body", "content", "rendered_text"} & set(receipt))
    # The rendered body never appears inside the metadata receipt.
    assert body not in json.dumps(receipt, default=str)


def test_rendered_excluded_from_trusted_stores() -> None:
    receipt = _rendered_receipt(_packet())
    assert receipt["imported_to_source_manifest"] is False
    assert receipt["imported_to_source_linked_proof"] is False
    assert receipt["persisted_to_sqlite"] is False
    assert RENDERED_OUTPUT_CLASS not in ALLOWLISTED_SOURCE_FAMILIES
