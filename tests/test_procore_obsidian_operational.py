"""Tests for the Phase 06B operational Obsidian outputs (Prompt 13)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.procore.obsidian_operational import (
    apply_project_health_note,
    build_daily_digest,
    build_meeting_prep,
    build_project_health_note,
)
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_enrichment import emit_action_signal

_NOW = "2026-05-29T00:00:00Z"
_PAST = "2026-05-01T00:00:00Z"
_SINCE = "2026-05-20T00:00:00Z"
_SECRET_TITLE = "ZZSENSITIVEMEETINGZZ"
runner = CliRunner()

_BANNED = ("liable", "liability", "entitled", "breach", "negligent", "at fault")
_SECRETS = (
    "bearer ",
    "authorization",
    "refresh_token",
    "client_secret",
    "-----begin",
    "access_token",
    "?sv=",
    "sig=",
    "x-amz",
)


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _record(
    db: Path,
    *,
    endpoint_id: str,
    record_id: str,
    title: str = "",
    review: bool = False,
    updated: str = _NOW,
) -> str:
    conn = get_connection(str(db))
    conn.execute("PRAGMA foreign_keys=OFF")  # test seed: skip the sync-run FK (throwaway DB)
    conn.execute(
        """INSERT INTO procore_live_records (project_key, procore_project_id, endpoint_id,
           parent_procore_id, procore_record_id, procore_record_number, title_redacted, status,
           updated_at_utc, canonical_json_redacted, review_required, first_seen_at_utc,
           last_seen_at_utc, last_sync_run_id, raw_body_persisted)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
        (
            "tropical",
            "P1",
            endpoint_id,
            "",
            record_id,
            f"M-{record_id}",
            title,
            "open",
            updated,
            "{}",
            1 if review else 0,
            _NOW,
            _NOW,
            "run-1",
        ),
    )
    conn.commit()
    return "|".join(["tropical", endpoint_id, "", record_id])


def _seed(db: Path) -> None:
    r1 = _record(db, endpoint_id="rfis", record_id="1", title="rfi-one")
    emit_action_signal(
        project_key="tropical",
        record_key=r1,
        endpoint_id="rfis",
        signal_type="rfi_overdue",
        importance="high",
        due_at_utc=_PAST,
        now_utc=_NOW,
        db_path=db,
    )
    m1 = _record(db, endpoint_id="meetings", record_id="10", title="weekly-coord")
    emit_action_signal(
        project_key="tropical",
        record_key=m1,
        endpoint_id="meetings",
        signal_type="meeting_topic_open_high_priority",
        importance="high",
        now_utc=_NOW,
        db_path=db,
    )
    # a review-flagged meeting whose title must never appear in rendered output
    _record(db, endpoint_id="meetings", record_id="11", title=_SECRET_TITLE, review=True)


# --- renderer tests ---


def test_project_health_note_sections_and_counts() -> None:
    db = _db()
    _seed(db)
    out = build_project_health_note("tropical", now_utc=_NOW, db_path=db)
    assert out["section_keys"] == ["status", "components", "top_risks", "stale", "review_required"]
    assert out["counts"]["top_risks"] >= 1
    assert "rfi_overdue" in out["rendered"]
    assert out["warnings"]["review_required_records"] >= 1


def test_meeting_prep_sections_and_diverts_review() -> None:
    db = _db()
    _seed(db)
    out = build_meeting_prep("tropical", since_utc=_SINCE, now_utc=_NOW, db_path=db)
    assert out["counts"]["meeting_actions"] >= 1
    assert out["counts"]["review_flagged_meetings"] == 1
    # the review-flagged meeting title is diverted, never inlined
    assert _SECRET_TITLE not in out["rendered"]
    assert "weekly-coord" in out["rendered"]


def test_daily_digest_headline_and_overdue() -> None:
    db = _db()
    _seed(db)
    out = build_daily_digest("tropical", since_utc=_SINCE, now_utc=_NOW, db_path=db)
    assert "headline" in out["section_keys"]
    assert out["counts"]["overdue"] >= 1
    assert out["warnings"]["review_required_records"] >= 1


# --- no raw body / secret tests ---


@pytest.mark.parametrize("builder", ("project_health", "meeting_prep", "daily_digest"))
def test_no_secret_or_banned_content(builder: str) -> None:
    db = _db()
    _seed(db)
    if builder == "project_health":
        rendered = build_project_health_note("tropical", now_utc=_NOW, db_path=db)["rendered"]
    elif builder == "meeting_prep":
        rendered = build_meeting_prep("tropical", since_utc=_SINCE, now_utc=_NOW, db_path=db)[
            "rendered"
        ]
    else:
        rendered = build_daily_digest("tropical", since_utc=_SINCE, now_utc=_NOW, db_path=db)[
            "rendered"
        ]
    low = rendered.lower()
    assert not [w for w in _SECRETS if w in low], builder
    assert not [w for w in _BANNED if w in low], builder
    assert _SECRET_TITLE not in rendered


# --- marker-bounded update tests ---


def test_apply_writes_marker_bounded_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db()
    _seed(db)
    vault = tmp_path / "construction-vault"
    vault.mkdir()
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))

    res = apply_project_health_note("tropical", now_utc=_NOW, db_path=db)
    assert res["vault_configured"] is True
    target = Path(res["written_paths"][0])
    assert target.parent == vault / "01_Projects"
    text = target.read_text(encoding="utf-8")
    start = "<!-- HB-PROCORE-OPERATIONAL-PROJECT-HEALTH:START -->"
    end = "<!-- HB-PROCORE-OPERATIONAL-PROJECT-HEALTH:END -->"
    assert text.count(start) == 1 and text.count(end) == 1

    # re-apply: markers stay singular (bounded region replaced, not appended)
    apply_project_health_note("tropical", now_utc=_NOW, db_path=db)
    text2 = target.read_text(encoding="utf-8")
    assert text2.count(start) == 1 and text2.count(end) == 1


# --- CLI dry-run / apply guardrail tests ---


def _patch_conn(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    import hb_assistant.procore.obsidian_operational as oo_mod
    import hb_assistant.store.connection as conn_mod
    import hb_assistant.store.migrator as mig_mod
    import hb_assistant.store.procore_action_queue as aq_mod
    import hb_assistant.store.procore_commitment_projection as com_mod
    import hb_assistant.store.procore_cost_exposure as ce_mod
    import hb_assistant.store.procore_enrichment as enr_mod
    import hb_assistant.store.procore_financials as fin_mod
    import hb_assistant.store.procore_history as hist_mod
    import hb_assistant.store.procore_operational as op_mod
    import hb_assistant.store.procore_project_health as ph_mod
    import hb_assistant.store.procore_relationship_quality as rq_mod
    import hb_assistant.store.procore_schedule_exposure as se_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(str(db))

    for mod in (
        conn_mod,
        mig_mod,
        enr_mod,
        fin_mod,
        hist_mod,
        aq_mod,
        ce_mod,
        se_mod,
        ph_mod,
        rq_mod,
        com_mod,
        op_mod,
        oo_mod,
    ):
        monkeypatch.setattr(mod, "get_connection", _get, raising=False)


def test_cli_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "c.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app,
        [
            "procore",
            "obsidian",
            "daily-digest",
            "--project",
            "tropical",
            "--since",
            "24 hours ago",
            "--dry-run",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["dry_run"] is True
    assert payload["written_paths"] == []
    assert "rendered" in payload and "warnings" in payload


def test_cli_apply_without_confirm_non_tty_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "c2.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app,
        ["procore", "obsidian", "project-health", "--project", "tropical", "--apply", "--json"],
    )
    assert res.exit_code != 0  # non-TTY --apply requires --confirm


def test_cli_apply_no_vault_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "c3.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    monkeypatch.delenv("HB_CONSTRUCTION_VAULT_ROOT", raising=False)
    res = runner.invoke(
        app,
        [
            "procore",
            "obsidian",
            "project-health",
            "--project",
            "tropical",
            "--apply",
            "--confirm",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 3, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is False
    assert "vault_root_unconfigured" in payload["reason_codes"]


def test_cli_unparseable_since_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "c4.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app,
        [
            "procore",
            "obsidian",
            "meeting-prep",
            "--project",
            "tropical",
            "--since",
            "not-a-date",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 3, res.output
    payload = json.loads(res.output)
    assert "since_unparseable" in payload["reason_codes"]
