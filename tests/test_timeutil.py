"""Kickoffs are stored in UTC and rendered in America/Chicago."""

from datetime import date

from src.report.timeutil import format_kickoff, london_kickoff


def test_summer_kickoff_is_chicago_daylight_time():
    assert format_kickoff("2026-07-15T18:00:00Z") == "Wed, Jul 15, 2026, 1:00 PM CDT"


def test_winter_kickoff_is_chicago_standard_time():
    assert format_kickoff("2026-01-15T18:00:00Z") == "Thu, Jan 15, 2026, 12:00 PM CST"


def test_london_local_time_converts_to_utc():
    kick = london_kickoff(date(2026, 10, 24), "15:00")
    # Late October is still British Summer Time (UTC+1).
    assert kick.isoformat().startswith("2026-10-24T14:00:00")
    rendered = format_kickoff(kick.isoformat())
    assert "CDT" in rendered
    assert "9:00 AM" in rendered
