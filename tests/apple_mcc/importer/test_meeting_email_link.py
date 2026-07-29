from hb_assistant.apple_mcc.importer.meeting_link import extract_join_urls, score_meeting_email_link

def test_link_score():
    assert score_meeting_email_link(email_subject="Standup", event_subject="Standup") == 1.0
    assert "https://zoom.us/j/1" in extract_join_urls("join https://zoom.us/j/1 now")
