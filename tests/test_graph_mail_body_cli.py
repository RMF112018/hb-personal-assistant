"""Phase 06 Prompt 08A — `graph mail body show` controlled decrypt CLI (local-only)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.security.text_vault import encrypt_text

runner = CliRunner()
_SYNTHETIC = "Synthetic body text used only in this isolated CLI test."


def _invoke(tmp_path: Path, *args: str):
    return runner.invoke(
        app, list(args), env={"HB_APP_SUPPORT_DIR": str(tmp_path)}, catch_exceptions=False
    )


def _seed_body_ref() -> str:
    # Default store + CLI both resolve to the same app-support DB; synthetic id.
    from hb_assistant.config.loader import load_config
    from hb_assistant.config.path_policy import PathPolicy

    store = ConstructionStore()
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    store.upsert_email_message(message_id="m1", thread_key="t", source_id="sx")
    ref = encrypt_text(_SYNTHETIC)
    store.upsert_email_body_vault_ref(
        message_id="m1",
        encrypted_full_body_ref=ref or "r",
        body_hash="a" * 64,
        body_length=len(_SYNTHETIC),
        extraction_policy="encrypted_text_vault",
        body_content_type="text",
        review_required=False,
        sensitivity_classification=None,
    )
    return str(PathPolicy(load_config()).get_db_path())


def test_body_show_requires_reason(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "mail", "body", "show", "--message-id", "m1", "--json")
    assert res.exit_code != 0  # missing required --reason


def test_body_show_unknown_id_found_false(tmp_path: Path) -> None:
    res = _invoke(
        tmp_path,
        "graph",
        "mail",
        "body",
        "show",
        "--message-id",
        "nope",
        "--reason",
        "validation",
        "--json",
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["found"] is False


def test_body_show_redacted_summary_no_plaintext() -> None:
    runner_local = CliRunner()
    db = _seed_body_ref()
    res = runner_local.invoke(
        app,
        [
            "graph",
            "mail",
            "body",
            "show",
            "--message-id",
            "m1",
            "--reason",
            "operator_review",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["found"] is True
    assert payload["encrypted_full_body_ref_present"] is True
    assert payload["plaintext_persisted"] is False
    assert payload["body_length"] == len(_SYNTHETIC)
    # Default output never contains the plaintext.
    assert _SYNTHETIC not in res.output

    # An audit receipt was recorded (no plaintext).
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT operation, detail_json FROM email_processing_receipts WHERE operation='body_decrypt_read'"
        ).fetchall()
    finally:
        conn.close()
    assert rows, "expected a body_decrypt_read audit receipt"
    assert _SYNTHETIC not in (rows[0][1] or "")
