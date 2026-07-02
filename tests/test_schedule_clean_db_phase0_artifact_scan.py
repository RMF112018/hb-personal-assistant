"""Artifact scanner tests."""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.schedule_clean_db.artifact_scan import scan_evidence_dir


def test_clean_pm_artifact_passes(tmp_path: Path) -> None:
    (tmp_path / "summary.md").write_text("# Ready\nAll systems nominal.\n", encoding="utf-8")
    report = scan_evidence_dir(tmp_path)
    assert report["passed"] is True


def test_raw_key_leak_flagged(tmp_path: Path) -> None:
    (tmp_path / "summary.md").write_text(
        'schedule_version_key: "tropical|S1|2026-07-01"\n', encoding="utf-8"
    )
    report = scan_evidence_dir(tmp_path)
    assert report["passed"] is False
    assert any(f["rule"] == "raw_schedule_key" for f in report["findings"])


def test_db_path_leak_flagged(tmp_path: Path) -> None:
    (tmp_path / "summary.md").write_text(
        "/Users/me/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite\n",
        encoding="utf-8",
    )
    report = scan_evidence_dir(tmp_path)
    assert any(f["rule"] == "raw_db_path" for f in report["findings"])


def test_traceback_flagged(tmp_path: Path) -> None:
    (tmp_path / "error.txt").write_text("Traceback (most recent call last):\n", encoding="utf-8")
    report = scan_evidence_dir(tmp_path)
    assert any(f["rule"] == "traceback" for f in report["findings"])


def test_causation_phrase_flagged(tmp_path: Path) -> None:
    (tmp_path / "memo.md").write_text("delay caused by subcontractor\n", encoding="utf-8")
    report = scan_evidence_dir(tmp_path)
    assert any(f["rule"] == "causation_language" for f in report["findings"])


def test_allowlisted_technical_file_passes(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "technical_allowlist": ["06-schema-audit-sample.json"],
                "allow_raw_db_paths": ["06-schema-audit-sample.json"],
                "allow_raw_schedule_keys": ["06-schema-audit-sample.json"],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "06-schema-audit-sample.json").write_text(
        '{"schedule_version_key":"tropical|S1|2026-07-01"}\n', encoding="utf-8"
    )
    report = scan_evidence_dir(tmp_path, allowlist_path=allowlist)
    assert report["passed"] is True
