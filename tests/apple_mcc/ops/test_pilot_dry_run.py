from hb_assistant.apple_mcc.ops.live_pilot import plan_live_pilot

def test_pilot():
    p = plan_live_pilot()
    assert p.source_mutation is False and p.redacted is True
