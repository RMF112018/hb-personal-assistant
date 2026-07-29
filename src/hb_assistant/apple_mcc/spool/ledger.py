"""Local spool ledger."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.apple_mcc.contracts.spool_states import SpoolState, transition


class SpoolLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spool_items (
              item_id TEXT PRIMARY KEY,
              state TEXT NOT NULL,
              domain TEXT NOT NULL,
              payload_path TEXT,
              updated_utc TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def put(self, item_id: str, domain: str, updated_utc: str, payload_path: str | None = None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO spool_items(item_id, state, domain, payload_path, updated_utc) VALUES (?,?,?,?,?)",
            (item_id, SpoolState.CAPTURED.value, domain, payload_path, updated_utc),
        )
        self.conn.commit()

    def advance(self, item_id: str, dst: SpoolState, updated_utc: str) -> None:
        row = self.conn.execute("SELECT state FROM spool_items WHERE item_id = ?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(item_id)
        new = transition(SpoolState(row[0]), dst)
        self.conn.execute(
            "UPDATE spool_items SET state = ?, updated_utc = ? WHERE item_id = ?",
            (new.value, updated_utc, item_id),
        )
        self.conn.commit()
