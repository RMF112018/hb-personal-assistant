from pathlib import Path
from hb_assistant.apple_mcc.collectors.calendar_collector import load_ics_fixture, plan_collect

def test_ics_and_plan():
    ics = load_ics_fixture(Path("tests/fixtures/apple_mcc/calendar/single.ics"))
    assert "VEVENT" in ics
    plan = plan_collect(sources=[{"title": "iCloud", "identifier": "x"}])
    assert "iCloud" in plan.sources
