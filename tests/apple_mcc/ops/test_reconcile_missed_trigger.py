from hb_assistant.apple_mcc.ops.reconcile import reconcile_missed

def test_dry():
    r = reconcile_missed(pending=3, dry_run=True)
    assert r.replayed == 0 and r.missed == 3
