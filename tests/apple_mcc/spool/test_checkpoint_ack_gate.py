from pathlib import Path
from hb_assistant.apple_mcc.spool.ledger import SpoolLedger
from hb_assistant.apple_mcc.spool.checkpoint import advance_on_ack
from hb_assistant.apple_mcc.contracts.spool_states import SpoolState
from hb_assistant.apple_mcc.importer.ack import ImportAck

def test_ack_gate(tmp_path):
    led = SpoolLedger(tmp_path / "s.sqlite")
    led.put("i1", "mail", "t0")
    for s in (SpoolState.QUEUED, SpoolState.TRANSPORTING, SpoolState.DELIVERED):
        led.advance("i1", s, "t")
    ack = tmp_path / "ack.json"
    ImportAck(batch_id="b", status="accepted", item_count=1).write(ack)
    advance_on_ack(led, "i1", ack, "t2")
