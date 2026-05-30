"""Phase 06 Prompt 08A — static no-plaintext / no-mutation guardrails.

Scans the Phase 06 email modules + the graph CLI for forbidden mailbox-mutation
and plaintext-body patterns, and proves no email SQLite table carries a plaintext
body column while email_messages.full_body_persisted stays CHECK-locked to 0.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

# Files that implement the email workflow (must stay read-only + no plaintext body).
_SCAN_FILES = [
    *(_ROOT / "src/hb_assistant/construction/email").glob("*.py"),
    _ROOT / "src/hb_assistant/cli/graph.py",
    _ROOT / "src/hb_assistant/graph/mail_readonly_client.py",
    _ROOT / "src/hb_assistant/graph/mail_endpoint_guard.py",
]

# Mailbox-mutation + plaintext-body tokens that must never appear in these modules.
_FORBIDDEN_TOKENS = (
    "createReply",
    "createForward",
    "sendMail",
    "/reply",
    "/replyAll",
    "/forward",
    "/move",
    "/copy",
    "markRead",
    "markUnread",
    "body_plaintext",
    "raw_body_persisted = 1",
    "raw_body",
    "body_html",
    "full_body_in_obsidian",
)
_WRITE_VERB_CALL = re.compile(r"\.(post|put|patch|delete)\s*\(")


@pytest.mark.parametrize("path", _SCAN_FILES, ids=lambda p: p.name)
def test_no_forbidden_tokens_in_email_modules(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    leaks = [tok for tok in _FORBIDDEN_TOKENS if tok in text]
    assert not leaks, f"{path.name}: forbidden tokens present: {leaks}"


@pytest.mark.parametrize("path", _SCAN_FILES, ids=lambda p: p.name)
def test_no_write_verb_calls_in_email_modules(path: Path) -> None:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        assert not _WRITE_VERB_CALL.search(line), f"{path.name}:{i} write-verb call: {line.strip()!r}"


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def test_no_plaintext_body_column_in_any_email_table() -> None:
    from hb_assistant.store.migrator import SQLiteMigrator

    db = _tmp_db()
    SQLiteMigrator(db_path=db).apply()
    conn = sqlite3.connect(db)
    try:
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'email_%'"
            )
        ]
        forbidden = {"body_plaintext", "raw_body", "body_html", "body_content", "body_text", "body", "content"}
        for tbl in tables:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")}
            leak = cols & forbidden
            assert not leak, f"{tbl} has plaintext-body column(s): {leak}"
        # email_messages still CHECK-locks full_body_persisted = 0.
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='email_messages'"
        ).fetchone()[0]
        assert "CHECK(full_body_persisted = 0)" in ddl
        # The vault table stores only an encrypted ref + plaintext-persistence locks.
        vault_ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='email_message_body_vault_refs'"
        ).fetchone()[0]
        assert "encrypted_full_body_ref" in vault_ddl
        assert "CHECK(plaintext_persisted = 0)" in vault_ddl
    finally:
        conn.close()


def test_evidence_dir_has_no_decrypted_body_markers() -> None:
    # The encrypted-body evidence must carry only refs/hashes/counts, never decrypted
    # bodies. (Evidence MAY mention forbidden column names like ``raw_body`` to document
    # their absence; we only flag markers that would appear if real plaintext leaked.)
    evidence = _ROOT / "docs/evidence/construction-intelligence-phase-06-email"
    leak_markers = ("BEGIN PGP", "----- decrypted body", "DECRYPTED PLAINTEXT")
    for path in evidence.glob("10A-*"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for tok in leak_markers:
            assert tok not in text, f"{path.name}: unexpected decrypted-body marker {tok!r}"
