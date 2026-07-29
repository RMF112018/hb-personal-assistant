from hb_assistant.apple_mcc.contacts.cross_container import allow_cross_container_link

def test_policy():
    assert allow_cross_container_link(left_container="a", right_container="a", policy_allow=False)
    assert not allow_cross_container_link(left_container="a", right_container="b", policy_allow=False)
