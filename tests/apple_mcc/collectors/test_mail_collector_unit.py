from hb_assistant.apple_mcc.collectors.mail_collector import plan_collect

def test_plan():
    p = plan_collect(account_name="BF-Personal")
    assert p.account_name == "BF-Personal"
