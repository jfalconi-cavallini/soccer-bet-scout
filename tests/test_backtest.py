"""Walk-forward scores, closing prices, and the no-leakage rule."""

from datetime import date, timedelta

from src.data.fduk import closing_odds, parse_csv
from src.model.backtest import (
    BACKTEST_FROM,
    devig,
    forecast_matches,
    log_loss,
    ranked_probability_score,
    summarize_forecasts,
    top_pick,
)
from src.model.elo import EloMatch, replay
from src.model.ratings import build_strengths


def _match(day, home, away, hg, ag, ht_h=None, ht_a=None, competition="E0"):
    return EloMatch(
        day=day,
        home=home,
        away=away,
        home_goals=hg,
        away_goals=ag,
        competition_id=competition,
        kind="league",
        ht_home=ht_h,
        ht_away=ht_a,
    )


def _history():
    rows = []
    for index in range(24):
        rows.append(_match(date(2024, 8, 1) + timedelta(days=index), "alpha", "beta", 2, 0, 1, 0))
        rows.append(_match(date(2024, 9, 1) + timedelta(days=index), "beta", "alpha", 0, 1, 0, 0))
    rows.append(_match(date(2024, 12, 1), "alpha", "beta", 3, 0, 2, 0))
    rows.append(_match(date(2025, 1, 15), "alpha", "beta", 1, 0, 1, 0))
    rows.append(_match(date(2025, 1, 15), "gamma", "delta", 1, 1, 0, 0))
    rows.append(_match(date(2025, 2, 1), "alpha", "beta", 0, 5, 0, 2))
    return rows


def _by_home(rows, day, home):
    return next(row for row in rows if row["day"] == day.isoformat() and row["home_goals"] is not None and home in (row.get("home"), ""))


def test_scores_and_devig_are_bounded():
    assert ranked_probability_score(1, 0, 0, 2, 0) == 0
    assert ranked_probability_score(0, 0, 1, 2, 0) == 1
    assert log_loss(1, 0, 0, 2, 0) == 0
    assert top_pick(0.4, 0.4, 0.2) == "home"
    home, draw, away = devig(2.0, 3.0, 6.0)
    assert abs(home + draw + away - 1) < 1e-12
    assert home > draw > away


def test_closing_odds_ignore_the_opening_price():
    text = """Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,B365H,B365D,B365A,PSCH,PSCD,PSCA
E0,15/01/2025,15:00,Alpha,Beta,1,0,1,0,1.40,4.00,7.00,1.80,3.60,4.50
E0,16/01/2025,15:00,Gamma,Delta,1,1,0,0,1.50,4.00,6.00,,,
E0,17/01/2025,15:00,City,Town,2,1,1,0,,,,
"""
    # Second row has no Pinnacle close. Third has no close at all.
    # Add Bet365 closing on the second row via a fresh string.
    text = """Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,B365H,B365D,B365A,B365CH,B365CD,B365CA,PSCH,PSCD,PSCA
E0,15/01/2025,15:00,Alpha,Beta,1,0,1,0,1.40,4.00,7.00,1.50,4.20,6.50,1.80,3.60,4.50
E0,16/01/2025,15:00,Gamma,Delta,1,1,0,0,1.50,4.00,6.00,1.70,3.80,5.00,,,
E0,17/01/2025,15:00,City,Town,2,1,1,0,2.00,3.40,3.60,,,,,,,
"""
    rows = parse_csv(text, {"id": "E0", "name": "Premier League"})
    assert rows[0].close_book == "pinnacle"
    assert rows[0].close_home == 1.80
    assert rows[1].close_book == "bet365"
    assert rows[1].close_home == 1.70
    assert rows[2].close_home is None
    assert closing_odds({"B365H": "1.2", "B365D": "5", "B365A": "9"}) is None


def test_replay_hook_does_not_change_the_ratings():
    matches = _history()
    plain = replay(matches, today=date(2025, 2, 1))
    seen = []

    def hook(ratings, match):
        seen.append((match.day, ratings[match.home]))

    hooked = replay(matches, today=date(2025, 2, 1), before_apply=hook)
    assert plain.ratings == hooked.ratings
    assert seen


def test_forecast_does_not_use_the_match_or_the_future(monkeypatch):
    calls = []
    real = build_strengths

    def spy(matches, as_of, **kwargs):
        calls.append(as_of)
        assert all(match.day < as_of for match in matches)
        assert not any(match.day >= date(2025, 2, 1) for match in matches if as_of <= date(2025, 1, 15))
        return real(matches, as_of, **kwargs)

    monkeypatch.setattr("src.model.backtest.build_strengths", spy)
    original = _history()
    first = forecast_matches(original, date(2025, 1, 15), date(2025, 2, 1))
    leaked = _history()
    # The scored match, the other match that day, and a later match all change.
    leaked[-3] = _match(date(2025, 1, 15), "alpha", "beta", 0, 4, 0, 2)
    leaked[-2] = _match(date(2025, 1, 15), "gamma", "delta", 5, 0, 3, 0)
    leaked[-1] = _match(date(2025, 2, 1), "alpha", "beta", 6, 0, 4, 0)
    second = forecast_matches(leaked, date(2025, 1, 15), date(2025, 2, 1))

    def pick(rows, day, home_goals_ignored, home):
        # Identity is the clubs, which the row does not store. Use order.
        return rows

    alpha = [row for row in first if row["day"] == "2025-01-15"][0]
    alpha_again = [row for row in second if row["day"] == "2025-01-15"][0]
    gamma = [row for row in first if row["day"] == "2025-01-15"][1]
    gamma_again = [row for row in second if row["day"] == "2025-01-15"][1]
    assert alpha["p_home"] == alpha_again["p_home"]
    assert gamma["p_home"] == gamma_again["p_home"]
    assert alpha["home_goals"] == 1
    assert alpha_again["home_goals"] == 0
    assert calls
    assert all(day >= date(2025, 1, 15) for day in calls)

    # A result from the day before does move the forecast.
    shifted = _history()
    shifted[-4] = _match(date(2024, 12, 1), "alpha", "beta", 0, 5, 0, 3)
    third = forecast_matches(shifted, date(2025, 1, 15), date(2025, 1, 15))
    moved = [row for row in third if row["day"] == "2025-01-15"][0]
    assert moved["p_home"] != alpha["p_home"]


def test_window_starts_at_2024_25_and_summary_math_holds():
    assert BACKTEST_FROM == date(2024, 7, 1)
    rows = forecast_matches(_history(), BACKTEST_FROM, date(2025, 1, 15))
    assert all(row["day"] >= "2024-07-01" for row in rows)
    assert any(row["day"] == "2024-08-01" for row in rows)
    report = summarize_forecasts(rows, BACKTEST_FROM, date(2025, 1, 15))
    assert report["overall"]["matches"] == len(rows)
    assert report["overall"]["model_brier"] is not None
    assert "home" in {item["market"] for item in report["markets"]}
    assert "1h_btts" in {item["market"] for item in report["markets"]}
    assert "btts_over_2.5" in {item["market"] for item in report["markets"]}
    home = next(item for item in report["markets"] if item["market"] == "home")
    assert len(home["bins"]) == 5
