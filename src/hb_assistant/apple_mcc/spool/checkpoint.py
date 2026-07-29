"""Checkpoint advances only after import ACK."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.apple_mcc.contracts.spool_states import SpoolState
from hb_assistant.apple_mcc.spool.ledger import SpoolLedger


def advance_on_ack(ledger: SpoolLedger, item_id: str, ack_path: Path, updated_utc: str) -> None:
    if not ack_path.is_file():
        raise FileNotFoundError("ack_missing")
    text = ack_path.read_text(encoding="utf-8")
    if '"status": "accepted"' not in text and '"status":"accepted"' not in text:
        raise RuntimeError("ack_not_accepted")
    ledger.advance(item_id, SpoolState.ACKED, updated_utc)
