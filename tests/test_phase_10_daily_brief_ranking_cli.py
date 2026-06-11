"""Phase 10 V51 — `second-brain daily-brief rank-candidates` CLI tests.

Verifies dry-run = zero writes + exit 0, apply requires a cap (exit 2), apply persists (exit 0),
--no-client is a success path, mock advisory output enriches while a leaky mock falls back, and the
emitted JSON is raw-free.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from tests._phase_10_ranking_seed import BRIEF_DATE, seed_ranking_store

runner = CliRunner()
_FIXTURES = Path("tests/fixtures/phase_10_candidate_ranking")
_FORBIDDEN = ("http://", "https://", "@example", "bearer", "secret", "body_html", "raw_body")


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "t.sqlite")
    seed_ranking_store(db)
    return db


def _invoke(db: str, *args: str):
    return runner.invoke(
        app,
        ["daily-brief", "rank-candidates", "--brief-date", BRIEF_DATE, "--db", db, "--json", *args],
    )


def test_dry_run_no_client_exit_zero_no_writes(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = _invoke(db, "--dry-run", "--no-client")
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["status"] == "ok"
    assert payload["applied"] is False
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM daily_brief_ranked_candidates").fetchone()[0] == 0
    conn.close()


def test_apply_without_cap_is_invalid(tmp_path: Path) -> None:
    res = _invoke(_db(tmp_path), "--apply", "--no-client")
    assert res.exit_code == 2
    assert json.loads(res.stdout)["error"] == "apply_requires_max_persist"


def test_apply_with_cap_persists(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = _invoke(db, "--apply", "--max-persist", "100", "--no-client")
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["applied"] is True
    assert payload["persistence"]["persisted_ranked"] == 3


def test_mock_valid_advice_enriches(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = _invoke(db, "--dry-run", "--mock-output", str(_FIXTURES / "mock_valid_advice.json"))
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["ranking"]["model_status"] == "model_enriched"


def test_mock_invalid_advice_falls_back(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = _invoke(db, "--dry-run", "--mock-output", str(_FIXTURES / "mock_invalid_advice.json"))
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["ranking"]["model_status"] == "withheld"
    assert payload["ranking"]["deterministic_fallback_used"] is True


def test_cli_json_is_raw_free(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = _invoke(db, "--apply", "--max-persist", "100", "--no-client").stdout.lower()
    for forbidden in _FORBIDDEN:
        assert forbidden not in out


def test_invalid_provider_rejected(tmp_path: Path) -> None:
    res = _invoke(_db(tmp_path), "--provider", "openai")
    assert res.exit_code == 2
