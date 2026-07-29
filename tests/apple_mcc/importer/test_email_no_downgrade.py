from hb_assistant.construction.email_calendar.source_quality import APPLE_MAIL_FULL, rank, EMAIL_METADATA_ONLY

def test_rank_order():
    assert rank(APPLE_MAIL_FULL) > rank(EMAIL_METADATA_ONLY)
