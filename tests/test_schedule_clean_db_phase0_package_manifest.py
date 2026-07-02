"""Import package manifest tests."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from hb_assistant.construction.schedule_clean_db.package_manifest import build_package_manifest

FIXTURES = Path(__file__).resolve().parents[0] / "fixtures" / "schedules"


def test_xer_manifest() -> None:
    manifest = build_package_manifest(FIXTURES / "xer" / "minimal.xer")
    assert manifest["detected_package_type"] == "xer"


def test_xml_manifest() -> None:
    manifest = build_package_manifest(FIXTURES / "xml" / "minimal_schedule.xml")
    assert manifest["detected_package_type"] == "xml"


def test_zip_xer_html(tmp_path: Path) -> None:
    zpath = tmp_path / "pkg.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("schedule.xer", (FIXTURES / "xer" / "minimal.xer").read_text())
        zf.writestr("companion.html", "<html></html>")
    manifest = build_package_manifest(zpath)
    roles = {m["role"] for m in manifest["zip_members"]}
    assert "primary_candidate" in roles
    assert "companion" in roles


def test_zip_xml_html(tmp_path: Path) -> None:
    zpath = tmp_path / "xml_pkg.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("schedule.xml", (FIXTURES / "xml" / "minimal_schedule.xml").read_text())
        zf.writestr("companion.html", "<html></html>")
    manifest = build_package_manifest(zpath)
    assert manifest["detected_package_type"] == "zip"


def test_unknown_file(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("not a schedule")
    manifest = build_package_manifest(path)
    assert manifest["detected_package_type"] == "unknown"


def test_missing_file_rejected() -> None:
    with pytest.raises(FileNotFoundError):
        build_package_manifest("/no/such/package.xer")
