"""Phase 10L-B: centralized Email Archive routing — corrected domain paths + per-domain attachments.

Proves work/home/shared archive notes route DIRECTLY under their domain folder (no ``Work/Work`` double
domain), attachments route per-domain (work byte-identical to the pre-10L layout), the write-guard
accepts all three domains, legacy double-domain paths are detected, and every produced path stays under
the self-index-guarded ``Email Archive/`` root.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_archive_paths as sap
from hb_assistant.obsidian_mcp import source_email_attachments as att
from hb_assistant.obsidian_mcp.source_indexer import EMAIL_ARCHIVE_FOLDER, is_email_archive_path


def _detail(source_root_key: str) -> dict[str, object]:
    return {"source_id": "abcdef0123456789beef", "source_root_key": source_root_key,
            "rel_path": "23-435-01/Correspondence/RFI 12.eml", "source_kind": "email"}


@pytest.mark.parametrize(
    ("root_key", "domain"),
    [("onedrive-work", "Work"), ("home-personal", "Home"), ("mystery-root", "Shared")],
)
def test_archive_note_routes_directly_under_domain(root_key: str, domain: str) -> None:
    rel = sap.archive_note_rel_path(_detail(root_key))
    assert rel.startswith(f"{EMAIL_ARCHIVE_FOLDER}/{domain}/")
    # No double-domain segment and the source-id-suffixed markdown card name.
    assert f"{EMAIL_ARCHIVE_FOLDER}/Work/Work/" not in rel
    assert rel.endswith("__abcdef012345.md")
    assert not sap.is_legacy_archive_path(rel)


def test_no_work_work_double_domain_for_any_domain() -> None:
    for root_key in ("onedrive-work", "home-personal", "mystery"):
        rel = sap.archive_note_rel_path(_detail(root_key))
        assert "/Work/Home/" not in rel and "/Work/Shared/" not in rel and "/Work/Work/" not in rel


def test_legacy_double_domain_detected_but_corrected_work_note_is_not_legacy() -> None:
    assert sap.is_legacy_archive_path(f"{EMAIL_ARCHIVE_FOLDER}/Work/Work/x__abc.md")
    assert sap.is_legacy_archive_path(f"{EMAIL_ARCHIVE_FOLDER}/Work/Home/x__abc.md")
    assert sap.is_legacy_archive_path(f"{EMAIL_ARCHIVE_FOLDER}/Work/Shared/x__abc.md")
    # A corrected work note (file directly under Work/) is NOT legacy.
    assert not sap.is_legacy_archive_path(f"{EMAIL_ARCHIVE_FOLDER}/Work/x__abc.md")


def test_self_index_guard_excludes_all_archive_roots() -> None:
    for domain in ("Work", "Home", "Shared"):
        assert is_email_archive_path(f"{EMAIL_ARCHIVE_FOLDER}/{domain}/note.md")
        assert is_email_archive_path(f"{EMAIL_ARCHIVE_FOLDER}/{domain}/Attachments/aa/x.pdf")


def _extracted() -> att.ExtractedAttachment:
    return att.ExtractedAttachment(
        index=0, filename="spec.pdf", content_type="application/pdf", disposition="attachment",
        content_id=None, size_bytes=10, sha256="0" * 64, is_inline=False, ext="pdf",
        status="extracted", data=b"hello")


def test_work_attachments_still_route_under_email_archive_work_attachments() -> None:
    rel = att.attachment_rel_path("abcdef0123456789", _extracted())  # default domain_folder="Work"
    assert rel.startswith(f"{EMAIL_ARCHIVE_FOLDER}/Work/Attachments/")
    assert att.ATTACHMENTS_SUBDIR.endswith(f"{EMAIL_ARCHIVE_FOLDER}/Work/Attachments")


@pytest.mark.parametrize("domain", ["Work", "Home", "Shared"])
def test_attachment_roots_per_domain(domain: str) -> None:
    rel = att.attachment_rel_path("abcdef0123456789", _extracted(), domain_folder=domain)
    assert rel.startswith(f"{EMAIL_ARCHIVE_FOLDER}/{domain}/Attachments/")
    assert sap.is_attachments_path(rel)
    assert is_email_archive_path(rel)


@pytest.mark.parametrize("domain", ["Work", "Home", "Shared"])
def test_write_guard_accepts_each_domain_and_rejects_outside(tmp_path: Path, domain: str) -> None:
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    rel = att.attachment_rel_path("abcdef0123456789", _extracted(), domain_folder=domain)
    assert att.write_attachment_binary(vault, rel, b"hello") == "written"
    assert (vault / rel).is_file()
    # A path outside the attachments roots is refused.
    with pytest.raises(ValueError):
        att.write_attachment_binary(vault, "Source Notes/Work/not-an-attachment.pdf", b"x")
