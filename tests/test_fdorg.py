"""football-data.org fills a missing result and supplies a UTC kickoff."""

from datetime import date

from src.data.fdorg import match_windows, parse_fdorg_match
from src.data.models import CatalogMatch, prefer


def _match(**overrides) -> CatalogMatch:
    base = dict(
        day=date(2026, 10, 18),
        home="athletic bilbao",
        away="real sociedad",
        home_name="Athletic Club",
        away_name="Real Sociedad",
        home_goals=None,
        away_goals=None,
        competition_id="SP1",
        competition="La Liga",
        kind="league",
        kickoff_utc="2026-10-18T12:00:00+00:00",
        source="openfootball",
    )
    base.update(overrides)
    return CatalogMatch(**base)


def test_slate_windows_stay_within_ten_days():
    windows = list(match_windows(date(2026, 10, 20), 16))
    assert windows == [
        (date(2026, 10, 20), date(2026, 10, 29)),
        (date(2026, 10, 30), date(2026, 11, 5)),
    ]
    for start, end in windows:
        assert (end - start).days <= 9


def test_finished_api_row_becomes_a_result():
    match = parse_fdorg_match(
        {
            "utcDate": "2026-10-18T14:15:00Z",
            "status": "FINISHED",
            "stage": "REGULAR_SEASON",
            "homeTeam": {"name": "Athletic Club"},
            "awayTeam": {"name": "Real Sociedad de Futbol"},
            "score": {"fullTime": {"home": 1, "away": 0}},
        },
        "SP1",
        "La Liga",
        "league",
    )
    assert match is not None
    assert match.finished
    assert match.home == "athletic bilbao"
    assert match.home_goals == 1
    assert match.kickoff_utc.startswith("2026-10-18T14:15:00")


def test_api_result_replaces_a_fixture_and_csv_keeps_xg():
    filled = prefer(
        _match(),
        _match(home_goals=2, away_goals=1, kickoff_utc="2026-10-18T19:00:00+00:00", source="football-data.org"),
    )
    assert filled.home_goals == 2
    assert filled.kickoff_utc.startswith("2026-10-18T19:00:00")

    csv_row = _match(
        home_goals=1,
        away_goals=0,
        xg_home=1.4,
        xg_away=0.6,
        kickoff_utc="2026-10-18T13:00:00+00:00",
        source="fduk",
    )
    kept = prefer(
        csv_row,
        _match(home_goals=1, away_goals=0, kickoff_utc="2026-10-18T19:00:00+00:00", source="football-data.org"),
    )
    assert kept.xg_home == 1.4
    assert kept.source == "fduk"
    assert kept.kickoff_utc.startswith("2026-10-18T19:00:00")
