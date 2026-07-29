from pathlib import Path
from hb_assistant.apple_mcc.spool.ledger import SpoolLedger
from hb_assistant.apple_mcc.contracts.spool_states import SpoolState

def test_restart(tmp_path):
    led = SpoolLedger(tmp_path / "spool.sqlite")
    led.put("i1", "mail", "2026-07-29T00:00:00Z")
    led.advance("i1", SpoolState.QUEUED, "2026-07-29T00:01:00Z")
