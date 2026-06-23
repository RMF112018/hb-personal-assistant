"""Integration smoke test for evidence package generation script."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_forecasting_db_complete_evidence.sh"


def _minimal_forecasting_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE forecast_config_items (id INTEGER, status TEXT, created_utc TEXT, updated_utc TEXT);
        CREATE TABLE procore_ep_budget_detail_rows (
          record_key TEXT, project_key TEXT, budget_code TEXT, budget_code_id TEXT,
          actual_cost TEXT, grand_total TEXT, updated_utc TEXT, is_current INTEGER
        );
        INSERT INTO forecast_config_items VALUES (1, 'active', '2026-06-21T00:00:00+00:00', '2026-06-21T00:00:00+00:00');
        INSERT INTO procore_ep_budget_detail_rows
          VALUES ('r1', 'testproj', '01-100', '100', '1000.00', '5000.00', '2026-06-21T00:00:00+00:00', 1);
        """
    )
    conn.commit()
    conn.close()


@pytest.mark.integration
def test_evidence_script_smoke_with_minimal_db(tmp_path: Path) -> None:
    db = tmp_path / "minimal.sqlite"
    _minimal_forecasting_db(db)
    env = {
        **os.environ,
        "LIVE_DB": str(db),
        "VENV_PYTHON": sys.executable,  # the venv interpreter (has hb_assistant + deps), not bare python3
        "HB_FORECASTING_EVIDENCE_SKIP_SCHEMACRAWLER": "1",
        "HB_FORECASTING_EVIDENCE_SKIP_NO_RAW": "1",
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]

    tgz = Path(proc.stdout.strip().splitlines()[-1])
    if not tgz.is_absolute():
        tgz = REPO_ROOT / tgz
    assert tgz.exists()

    with tarfile.open(tgz, "r:gz") as tf:
        names = tf.getnames()
        assert any(n.endswith("96-package-complete.txt") for n in names)
        assert any(n.endswith("97-file-manifest.txt") for n in names)
        assert any(n.endswith("98-no-raw-leak-scan.json") for n in names)
        assert any(n.endswith("99-zero-byte-files.txt") for n in names)
        assert any("01-amount-field-classification.json" in n for n in names)
        assert not any("/._" in n or n.startswith("._") for n in names)

    stamp = tgz.stem.replace("forecasting-db-complete-evidence-", "")
    out_dir = REPO_ROOT / "docs/evidence/forecasting-db-complete-evidence" / stamp
    scan_path = out_dir / "98-no-raw-leak-scan.json"
    assert scan_path.exists()
    scan_data = json.loads(scan_path.read_text(encoding="utf-8"))
    assert scan_data.get("ok") is True or scan_data.get("skipped") is True

    summary_path = out_dir / "00-evidence-package-summary.json"
    json.loads(summary_path.read_text(encoding="utf-8"))