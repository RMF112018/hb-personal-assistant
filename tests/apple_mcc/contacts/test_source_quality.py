from hb_assistant.construction.email_calendar.source_quality import (
    APPLE_MAIL_FULL,
    CNCONTACT_FULL,
    rank,
)


def test_apple_ranks() -> None:
    assert rank(APPLE_MAIL_FULL) >= 90
    assert rank(CNCONTACT_FULL) >= 90
