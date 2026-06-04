# ruff: noqa: I001
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "proofs"
    / "phase_08d_agent_data_evaluation_evidence_collector.py"
)
spec = importlib.util.spec_from_file_location("phase_08d_agent_data_evaluation_evidence_collector", SCRIPT)
assert spec is not None
collector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(collector)


def test_readonly_connection_rejects_mutation(tmp_path: Path) -> None:
    db = tmp_path / "sample.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

    ro = collector.sqlite_readonly_connection(db)
    try:
        assert ro.execute("PRAGMA query_only").fetchone()[0] == 1
        try:
            ro.execute("INSERT INTO sample(value) VALUES ('x')")
        except sqlite3.OperationalError:
            pass
        else:  # pragma: no cover
            raise AssertionError("read-only connection allowed mutation")
    finally:
        ro.close()


def test_risky_field_profile_does_not_export_values(tmp_path: Path) -> None:
    db = tmp_path / "sample.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, raw_body TEXT, status TEXT)")
    conn.execute("INSERT INTO sample(raw_body, status) VALUES ('raw email body secret text', 'open')")
    conn.commit()

    profile = collector.column_profile(
        conn,
        "sample",
        {"name": "raw_body", "type": "TEXT", "notnull": 0, "pk": 0},
        1,
    )
    serialized = str(profile)
    assert profile["potential_raw_content_risk_field"] is True
    assert "raw email body secret text" not in serialized
    assert profile["maximum_observed_string_length"] == 26


def test_safety_scan_flags_token_value(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "bad.md").write_text("Authorization: Bearer abcdefghijklmnopqrstuvwxyz\n")
    scan = collector.safety_scan(evidence)
    assert scan["scan_status"] == "fail"
    assert scan["unsafe_finding_count"] >= 1


def test_safety_scan_allows_detector_labels_without_values(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "scan.md").write_text("Scanned for access_token and refresh_token labels only.\n")
    scan = collector.safety_scan(evidence)
    assert scan["scan_status"] == "pass"


def test_json_key_inventory_exports_keys_not_values(tmp_path: Path) -> None:
    db = tmp_path / "sample.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, metadata_json TEXT)")
    conn.execute("INSERT INTO sample(metadata_json) VALUES (?)", ('{"safe_key":"do not export this value"}',))
    conn.commit()

    profile = collector.column_profile(
        conn,
        "sample",
        {"name": "metadata_json", "type": "TEXT", "notnull": 0, "pk": 0},
        1,
    )
    serialized = str(profile)
    assert "safe_key" in profile["json_key_inventory"]
    assert "do not export this value" not in serialized
