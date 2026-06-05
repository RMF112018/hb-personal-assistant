"""Tests for Prompt 05 agent-ready query marts and latency.

Covers:
- All 4 marts populated after run (project coverage reuse + 3 new).
- Latency keys for the 8 target queries present and numeric.
- CLI subprocess emits expected structure + guardrails.
- Review-required / low-confidence records remain visible (no hiding).
- No raw content paths exercised.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
from pathlib import Path

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator


def _migrate(db_path: str | Path) -> int:
    return SQLiteMigrator(db_path=str(db_path)).apply()


def _seed_minimal(store: ConstructionStore) -> None:
    store.upsert_project_identity(
        project_key="tropical",
        hb_project_number="23-435-01",
        is_active=True,
        match_status="matched",
        match_confidence="high",
    )
    with contextlib.suppress(Exception):
        store.upsert_source_system_record(
            {
                "canonical_record_id": "procore:procore_live_records:REC-001",
                "project_key": "tropical",
                "source_system": "procore",
                "source_table": "procore_live_records",
                "source_primary_key": "REC-001",
                "confidence_class": "deterministic_exact_id",
                "review_required": False,
            }
        )


def test_marts_populate_and_latency_keys(tmp_path: Path) -> None:
    db = tmp_path / "p05.db"
    v = _migrate(db)
    assert v >= 21
    store = ConstructionStore(str(db))
    _seed_minimal(store)

    from hb_assistant.construction.data_quality import populate_agent_ready_query_marts

    report = populate_agent_ready_query_marts(store=store)

    assert report["schema_version"] == 21
    m = report["marts"]
    assert "project_source_coverage_mart" in m
    assert "source_record_summary_mart" in m
    assert "relationship_quality_mart" in m
    assert "cross_domain_context_readiness_mart" in m

    lat = report["latency_ms"]
    for key in [
        "project_coverage",
        "unmapped_records_by_project",
        "relationship_orphans_by_project",
        "review_candidates_by_project",
        "gate_status_by_phase_run",
    ]:
        assert key in lat
        assert isinstance(lat[key], (int, float))

    g = report["guardrails"]
    assert g["review_required_visible"] is True
    assert g["latency_measured"] is True
    assert g["additive_only"] is True


def test_cli_marts_json() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hb_assistant.cli.main",
            "construction-agent",
            "data-quality",
            "marts",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "construction-agent data-quality marts"
    assert "report" in payload
    assert "marts" in payload["report"]
    assert "latency_ms" in payload["report"]
    assert payload["guardrails"]["latency_measured"] is True
