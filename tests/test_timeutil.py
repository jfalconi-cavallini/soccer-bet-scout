"""Kickoffs are stored in UTC and rendered in America/Chicago."""

from datetime import date

from src.data.cups import parse_cup_text
from src.report.timeutil import central_european_kickoff, format_kickoff, london_kickoff


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


def test_uefa_text_kickoff_is_central_european_not_london():
    # 17 Sep 2024, 21:00 was the CEST slot (UTC+2). UK viewers saw 20:00 BST.
    kick = central_european_kickoff(date(2024, 9, 17), "21:00")
    assert kick.isoformat().startswith("2024-09-17T19:00:00")
    london = london_kickoff(date(2024, 9, 17), "21:00")
    assert london.isoformat().startswith("2024-09-17T20:00:00")
    rendered = format_kickoff(kick.isoformat())
    assert "2:00 PM" in rendered
    parsed = parse_cup_text(
        "Tue Sep 17 2024\n  21:00  FC Bayern München v Dinamo Zagreb  9-2\n",
        "UCL",
        2024,
    )
    assert parsed[0].kickoff_utc.startswith("2024-09-17T19:00:00")
