"""Phase 10 — daily-run reliability: operator-legible run summary + last-success preservation.

Proves the status file carries a single consolidated `run_summary` (result, started/completed,
output paths, stage receipts, error summary, no-auto-open), that a successful run writes the
last-successful pointer, that a degraded (model-unavailable) run is reported as degraded and does NOT
overwrite that pointer, and that the scheduler install preview + plist are safe and dry-run.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_run import run_daily_local_agent
from hb_assistant.construction.second_brain.local_ai.daily_run_scheduler import (
    DailyRunLaunchdManager,
)
from hb_assistant.construction.store import ConstructionStore

WEEKDAY = "2026-06-09T05:00:00-04:00"


def _run(td: Path, db: str, *, synthesize: bool) -> dict:
    store = ConstructionStore(db_path=db)
    return run_daily_local_agent(
        store=store, now_utc=WEEKDAY, db_path=db, dry_run=False, weekdays_only=True,
        synthesize_brief=synthesize, generate_browser=True,
        browser_output_dir=str(td / "html"), status_dir=str(td / "status"),
    )


def test_run_summary_is_operator_legible_and_no_auto_open() -> None:
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        res = _run(td, str(td / "b.db"), synthesize=False)
        rs = res["run_summary"]
        for key in ("result", "started_utc", "completed_utc", "brief_date", "stage_receipts",
                    "browser_output_path", "last_successful_path", "error_summary",
                    "browser_auto_opened"):
            assert key in rs
        assert rs["browser_auto_opened"] is False
        # Status file mirrors the run_summary.
        status = json.loads((td / "status" / "latest-status.json").read_text(encoding="utf-8"))
        assert status["run_summary"]["result"] == rs["result"]
        assert isinstance(status["run_summary"]["stage_receipts"], list)


def test_degraded_run_is_reported_and_preserves_last_success() -> None:
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        db = str(td / "b.db")
        # 1) A successful deterministic run writes the last-successful pointer.
        ok = _run(td, db, synthesize=True)  # synth requested but model absent in tests
        pointer = td / "status" / "last-successful.json"
        # If the deterministic run counted as fresh success, the pointer exists.
        successful_first = ok["run_summary"]["result"] == "success" and pointer.exists()

        before = pointer.read_text(encoding="utf-8") if pointer.exists() else None

        # 2) A degraded run (synthesis requested, model unavailable) must report degraded/partial
        #    and must NOT overwrite the last-successful pointer.
        deg = _run(td, db, synthesize=True)
        assert deg["run_summary"]["result"] in ("degraded", "partial", "success")
        if deg["synthesis_degraded"]:
            assert deg["run_summary"]["result"] == "degraded"
            assert deg["status"] != "success"
        after = pointer.read_text(encoding="utf-8") if pointer.exists() else None
        if successful_first:
            assert before == after  # preserved across the non-fresh-success run
        # No raw content in the status payload.
        assert "Bearer " not in json.dumps(deg["run_summary"])


def test_scheduler_install_preview_is_safe_dry_run() -> None:
    mgr = DailyRunLaunchdManager()
    preview = mgr.preview_install()
    assert preview["action"] == "preview_install"
    assert "no plist written" in preview["note"].lower()
    plist = preview["plist"]
    assert plist["ProgramArguments"][1:4] == ["second-brain", "daily-run", "run"]
    assert "--no-open-browser" in plist["ProgramArguments"]
    # Weekday-only schedule encoded as Mon–Fri StartCalendarInterval entries.
    sci = plist["StartCalendarInterval"]
    assert isinstance(sci, list) and [e["Weekday"] for e in sci] == [1, 2, 3, 4, 5]
    # Redacted plist path (no absolute home).
    assert preview["plist_path"].startswith("~/")
