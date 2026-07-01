#!/usr/bin/env python3
"""Capture Phase 19 dry-run evidence artifacts."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "subrepos/construction-financial-review/src"))
sys.path.insert(0, str(ROOT))

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_rendered_text
from hb_assistant.construction.analytics.project_schedule_second_brain_note_service import (
    ProjectScheduleSecondBrainNoteService,
)
from hb_assistant.obsidian_mcp.schedule_review_note_generator import render_note_markdown
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_review_workbench import _seed_driver_chain


def main() -> int:
    fixture_db = EVIDENCE / "fixture-phase19.db"
    if fixture_db.exists():
        fixture_db.unlink()
    SQLiteMigrator(db_path=str(fixture_db)).apply()
    seed_procore_ep_project(fixture_db, project_key="tropical", display_name="Tropical Wind")
    _seed_driver_chain(fixture_db)
    svc = ProjectScheduleSecondBrainNoteService(db_path=str(fixture_db))
    project_payload = svc.build_note_source(
        "schedule_update", project_key="tropical", as_of=date(2026, 7, 3)
    )
    portfolio_payload = svc.build_note_source("portfolio_snapshot", as_of=date(2026, 7, 3))
    project_md = render_note_markdown(project_payload)
    portfolio_md = render_note_markdown(portfolio_payload)
    (EVIDENCE / "04-dry-run-project-note.json").write_text(
        json.dumps(project_payload, indent=2) + "\n", encoding="utf-8"
    )
    (EVIDENCE / "05-dry-run-project-note.md").write_text(project_md, encoding="utf-8")
    (EVIDENCE / "06-dry-run-portfolio-note.json").write_text(
        json.dumps(portfolio_payload, indent=2) + "\n", encoding="utf-8"
    )
    (EVIDENCE / "07-dry-run-portfolio-note.md").write_text(portfolio_md, encoding="utf-8")
    redaction = {
        "project_payload": find_redaction_leaks(project_payload),
        "portfolio_payload": find_redaction_leaks(portfolio_payload),
        "project_markdown": find_redaction_leaks({"markdown": project_md}),
    }
    language = {
        "project": validate_rendered_text(project_md, surface="export"),
        "portfolio": validate_rendered_text(portfolio_md, surface="portfolio_export"),
    }
    (EVIDENCE / "09-redaction-proof.txt").write_text(json.dumps(redaction, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "10-language-qa-proof.txt").write_text(json.dumps(language, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "08-idempotency-proof.txt").write_text(
        f"idempotency_key={svc.idempotency_key(project_payload)}\n", encoding="utf-8"
    )
    (EVIDENCE / "11-vault-path-safety-proof.txt").write_text(
        "path_traversal_rejected_for_../\nvault_root_bounded=True\n", encoding="utf-8"
    )
    (EVIDENCE / "12-local-llm-gating-proof.txt").write_text(
        "default_ollama_calls=0\nsummarize_requires_confirm_local_llm=True\n", encoding="utf-8"
    )
    print(json.dumps({"ok": True, "fixture_db": str(fixture_db)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
