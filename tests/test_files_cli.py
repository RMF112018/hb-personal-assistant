from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from hb_assistant.cli.main import app


runner = CliRunner()


def _env() -> dict[str, str]:
    return {"HB_APP_SUPPORT_DIR": str(Path.cwd() / ".tmp-app-support-files-cli-tests")}


def test_files_sample_uses_synthetic_mode() -> None:
    result = runner.invoke(app, ["files", "sample", "--json"], env=_env())
    assert result.exit_code == 0
    assert '"mode": "sample"' in result.stdout


def test_files_ingest_returns_no_provenance_candidates_when_empty() -> None:
    result = runner.invoke(app, ["files", "ingest", "--dry-run", "--json", "--limit", "1"], env=_env())
    assert result.exit_code == 1
    assert '"status": "no_provenance_candidates"' in result.stdout


def test_files_ingest_uses_real_persisted_candidates() -> None:
    with patch("hb_assistant.cli.files.Store.list_pending_ingest_candidates", return_value=[{
        "source_record_id": 77,
        "drive_item_id": "cli-test",
        "name": "CliTest.pdf",
        "size_bytes": 1024,
        "web_url": None,
        "download_status": "not_downloaded",
        "parse_status": "not_parsed",
    }]):
        result = runner.invoke(app, ["files", "ingest", "--dry-run", "--json", "--limit", "5"], env=_env())
    assert result.exit_code == 0
    assert '"mode": "real"' in result.stdout
    assert '"status": "ok"' in result.stdout
