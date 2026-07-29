from hb_assistant.construction.email_calendar.source_quality import APPLE_EVENTKIT_FULL, APPLE_EVENTKIT_META, rank

def test_cal_rank():
    assert rank(APPLE_EVENTKIT_FULL) > rank(APPLE_EVENTKIT_META)
