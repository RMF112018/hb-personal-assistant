"""Phase 10 — deterministic Procore action-signal digest (advisory, no writeback).

Covers the deterministic digest shape + source-linking, redaction (no free-text/metadata
exposure), dry-run zero writes, apply-requires-cap + max-persist, idempotent candidates,
guard-column invariants on daily_brief_action_candidates, the empty-Procore clean path, the
optional synthesis layer (off by default + model-unavailable fail-closed), and the CLI wiring.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import build_procore_action_digest
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

NOW = "2026-06-08T00:00:00+00:00"

_GUARD_COLUMNS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_writeback_performed",
    "procore_writeback_performed",
    "email_send_performed",
    "calendar_mutation_performed",
)

# Fields that must NEVER appear in digest output (free-text / hashes / pointers).
_FORBIDDEN_KEYS = (
    "metadata_json",
    "encrypted_full_text_ref",
    "text_hash",
    "title_redacted",
    "summary_redacted",
    "owner_entity_key",
    "body",
    "signed_url",
    "download_url",
    "token",
    "secret",
)

_COLS = (
    "action_signal_id, project_key, record_key, endpoint_id, signal_type, signal_status, "
    "importance, due_at_utc, owner_entity_key, title_redacted, summary_redacted, "
    "reason_codes_json, first_detected_at_utc, last_seen_at_utc, resolved_at_utc, "
    "source_change_event_id, metadata_json"
)


def _seed(db: str, rows: list[tuple]) -> ConstructionStore:
    s = ConstructionStore(db_path=db)  # creates schema
    conn = sqlite3.connect(db)
    conn.executemany(
        f"INSERT INTO procore_action_signals ({_COLS}) VALUES ({', '.join(['?'] * 17)})",
        rows,
    )
    conn.commit()
    conn.close()
    return s


def _signal(
    sid: str,
    project: str,
    signal_type: str,
    *,
    importance: str = "high",
    due: str | None = None,
) -> tuple:
    return (
        sid,
        project,
        f"{project}|ep||{sid}",
        "ep",
        signal_type,
        "open",
        importance,
        due,
        "ohash",
        "t",
        "sm",
        "[]",
        "2026-05-01T00:00:00+00:00",
        "2026-06-01T00:00:00+00:00",
        None,
        None,
        "{}",
    )


def _default_rows() -> list[tuple]:
    return [
        _signal("s1", "alpha", "inspection_item_unanswered", due="2026-06-01T00:00:00+00:00"),
        _signal("s2", "alpha", "inspection_item_unanswered", importance="medium"),
        _signal("s3", "beta", "invoice_payment_due", due="2026-07-01T00:00:00+00:00"),
    ]


# --- deterministic shape / source-linking --------------------------------------


def test_digest_shape_and_source_linking(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db)
    assert out["summary"]["projects"] == 2
    assert out["summary"]["total_open_signals"] == 3
    assert out["summary"]["overdue_total"] == 1  # only s1 is past due vs NOW
    alpha = next(p for p in out["projects"] if p["project_key"] == "alpha")
    grp = alpha["groups"][0]
    assert grp["signal_type"] == "inspection_item_unanswered"
    assert grp["count"] == 2
    # source-linked: each group lists contributing signal ids/record keys
    assert grp["source_refs"] and grp["source_refs"][0]["action_signal_id"] in {"s1", "s2"}


def test_digest_is_deterministic(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    a = build_procore_action_digest(store=s, now_utc=NOW, db_path=db)
    b = build_procore_action_digest(store=s, now_utc=NOW, db_path=db)
    assert a["summary"] == b["summary"]


def test_no_forbidden_keys_in_output(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db, synthesize=False)
    blob = json.dumps(out)
    for k in _FORBIDDEN_KEYS:
        assert f'"{k}"' not in blob, k


# --- dry-run / apply posture ---------------------------------------------------


def test_limit_bounds_groups_and_would_persist(tmp_path: Path) -> None:
    # One project with 3 distinct signal-type groups; --limit 2 must bound output + would_persist.
    db = str(tmp_path / "t.sqlite")
    rows = [
        _signal("s1", "alpha", "type_a"),
        _signal("s2", "alpha", "type_b"),
        _signal("s3", "alpha", "type_c"),
    ]
    s = _seed(db, rows)
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db, limit=2)
    assert out["summary"]["would_persist"] == 2  # capped from 3
    alpha = out["projects"][0]
    assert alpha["group_count"] == 3  # true total still reported (no silent cap)
    assert alpha["groups_considered"] == 2
    assert len(alpha["groups"]) == 2


def test_dry_run_writes_zero_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db)
    assert out["applied"] is False
    assert out["summary"]["persisted"] == 0
    assert out["summary"]["would_persist"] == 2  # 2 distinct (project, signal_type) groups
    assert s.list_daily_brief_action_candidates(brief_date="2026-06-08") == []


def test_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    try:
        build_procore_action_digest(store=s, now_utc=NOW, db_path=db, dry_run=False)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "max_persist" in str(e)


def test_max_persist_caps_writes(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    out = build_procore_action_digest(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=1
    )
    assert out["summary"]["persisted"] == 1
    assert out["summary"]["would_persist"] == 2
    assert len(s.list_daily_brief_action_candidates(brief_date="2026-06-08")) == 1


def test_apply_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    build_procore_action_digest(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    out2 = build_procore_action_digest(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10
    )
    assert out2["summary"]["persisted"] == 0
    assert out2["summary"]["skipped_existing"] == 2
    assert len(s.list_daily_brief_action_candidates(brief_date="2026-06-08")) == 2


def test_guard_columns_zero_after_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    build_procore_action_digest(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    for row in conn.execute(f"SELECT {cols} FROM daily_brief_action_candidates").fetchall():
        assert all(v == 0 for v in row)
    conn.close()


def test_empty_procore_is_clean(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)  # no signals
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db)
    assert out["ok"] is True
    assert out["summary"]["projects"] == 0
    assert out["summary"]["groups"] == 0


# --- optional synthesis --------------------------------------------------------


def test_synthesize_off_by_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db)
    assert out["synthesis"] == {"requested": False}


def test_synthesize_without_client_fails_closed(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())
    out = build_procore_action_digest(
        store=s, now_utc=NOW, db_path=db, synthesize=True, client=None
    )
    assert out["synthesis"]["requested"] is True
    assert out["synthesis"]["ok"] is False
    assert out["synthesis"]["reason"] == "no_local_model_client"
    # deterministic digest unaffected
    assert out["summary"]["total_open_signals"] == 3


def test_synthesize_feeds_only_redacted_aggregates(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, _default_rows())

    class _SpyClient:
        captured = {}

        def generate_json(self, *, system: str, prompt: str) -> str:
            _SpyClient.captured = {"system": system, "prompt": prompt}
            return json.dumps({"narrative": "advisory", "risk_flags": ["overdue inspections"]})

    out = build_procore_action_digest(
        store=s, now_utc=NOW, db_path=db, synthesize=True, client=_SpyClient()
    )
    assert out["synthesis"]["ok"] is True
    # only counts + risk keywords were sent — never record ids/titles/metadata
    sent = _SpyClient.captured["prompt"]
    for forbidden in ("action_signal_id", "record_key", "metadata", "title_redacted", "s1", "s2"):
        assert forbidden not in sent


# --- CLI -----------------------------------------------------------------------


def test_cli_dry_run_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db, _default_rows())
    res = runner.invoke(app, ["procore-digest", "build", "--db", db, "--as-of", NOW, "--summary"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["applied"] is False
    assert payload["summary"]["persisted"] == 0


def test_cli_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db, _default_rows())
    res = runner.invoke(app, ["procore-digest", "build", "--db", db, "--apply"])
    assert res.exit_code == 2
    assert json.loads(res.output)["error"] == "apply_requires_max_persist"


def test_cli_apply_capped(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db, _default_rows())
    res = runner.invoke(
        app,
        ["procore-digest", "build", "--db", db, "--apply", "--max-persist", "1", "--as-of", NOW],
    )
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["summary"]["persisted"] == 1
