"""Prediction log keeps the first call, then scores it."""

from datetime import datetime, timezone

from src.track.settlement import brier, calibration, settle, upsert_prediction


def test_brier_is_zero_for_a_certain_correct_call():
    assert brier(1, 0, 0, 2, 0) == 0
    assert brier(1, 0, 0, 0, 1) == 2


def test_upsert_does_not_rewrite_and_settle_fills_brier():
    log = {"predictions": []}
    upsert_prediction(
        log,
        {
            "match_id": "2026-10-24-alpha-beta",
            "home": "alpha",
            "away": "beta",
            "p_home": 0.5,
            "p_draw": 0.3,
            "p_away": 0.2,
        },
    )
    upsert_prediction(
        log,
        {
            "match_id": "2026-10-24-alpha-beta",
            "home": "alpha",
            "away": "beta",
            "p_home": 0.9,
            "p_draw": 0.05,
            "p_away": 0.05,
        },
    )
    assert len(log["predictions"]) == 1
    assert log["predictions"][0]["p_home"] == 0.5
    assert settle(log, {"2026-10-24-alpha-beta": (1, 1)}) == 1
    assert settle(log, {"2026-10-24-alpha-beta": (1, 1)}) == 0
    assert log["predictions"][0]["result"]["home_goals"] == 1
    report = calibration(log)
    assert report["settled"] == 1
    assert report["brier"] is not None
    assert len(report["bins"]) == 5
    assert len(report["draw_bins"]) == 5
    assert len(report["away_bins"]) == 5
    draw_hit = next(item for item in report["draw_bins"] if item["count"])
    assert draw_hit["actual"] == 1


def test_refresh_lands_once_inside_the_day_before_kickoff():
    log = {"predictions": []}
    kickoff = "2026-10-24T19:00:00+00:00"
    first = {
        "match_id": "m1",
        "kickoff_utc": kickoff,
        "home": "alpha",
        "away": "beta",
        "p_home": 0.5,
        "p_draw": 0.3,
        "p_away": 0.2,
        "xg_home": 1.2,
        "xg_away": 0.9,
    }
    upsert_prediction(log, first, now=datetime(2026, 10, 20, tzinfo=timezone.utc))
    early = dict(first, p_home=0.55, p_draw=0.25, p_away=0.2)
    upsert_prediction(log, early, now=datetime(2026, 10, 22, tzinfo=timezone.utc))
    assert log["predictions"][0]["refresh"] is None
    close = dict(first, p_home=0.6, p_draw=0.22, p_away=0.18)
    upsert_prediction(log, close, now=datetime(2026, 10, 23, 20, tzinfo=timezone.utc))
    later = dict(first, p_home=0.7, p_draw=0.2, p_away=0.1)
    upsert_prediction(log, later, now=datetime(2026, 10, 24, 1, tzinfo=timezone.utc))
    row = log["predictions"][0]
    assert row["p_home"] == 0.5
    assert row["refresh"]["p_home"] == 0.6
    assert settle(log, {"m1": (1, 0)}) == 1
    assert row["brier"] == round(brier(0.6, 0.22, 0.18, 1, 0), 4)
    assert row["brier_first"] == round(brier(0.5, 0.3, 0.2, 1, 0), 4)


def test_markets_backfill_without_rewriting_the_result_call():
    log = {"predictions": []}
    upsert_prediction(
        log,
        {
            "match_id": "m-markets",
            "home": "alpha",
            "away": "beta",
            "p_home": 0.5,
            "p_draw": 0.3,
            "p_away": 0.2,
        },
    )
    upsert_prediction(
        log,
        {
            "match_id": "m-markets",
            "home": "alpha",
            "away": "beta",
            "p_home": 0.9,
            "p_draw": 0.05,
            "p_away": 0.05,
            "markets": {"btts": 0.6, "over_2.5": 0.4, "1h_btts": 0.3, "ah_home_-1": 0.25},
        },
    )
    row = log["predictions"][0]
    assert row["p_home"] == 0.5
    assert row["markets"]["btts"] == 0.6
    assert settle(
        log,
        {"m-markets": {"home_goals": 2, "away_goals": 1, "ht_home": 1, "ht_away": 0}},
    ) == 1
    assert row["market_hits"]["btts"] == 1
    assert row["market_hits"]["over_2.5"] == 1
    assert row["market_hits"]["1h_btts"] == 0
    assert "ah_home_-1" not in row["market_hits"]
    assert row["market_brier"] is not None
    report = calibration(log)
    assert any(item["market"] == "btts" and item["actual"] == 1 for item in report["markets"])
    assert set(report["market_bins"]) == {"btts", "over_2.5", "1h_btts", "1h_over_0.5"}
    btts_bin = next(item for item in report["market_bins"]["btts"] if item["count"])
    assert btts_bin["actual"] == 1


def test_refresh_is_where_markets_land_when_one_exists():
    log = {"predictions": []}
    kickoff = "2026-10-24T19:00:00+00:00"
    first = {
        "match_id": "m2",
        "kickoff_utc": kickoff,
        "home": "alpha",
        "away": "beta",
        "p_home": 0.5,
        "p_draw": 0.3,
        "p_away": 0.2,
    }
    upsert_prediction(log, first, now=datetime(2026, 10, 20, tzinfo=timezone.utc))
    close = dict(first, p_home=0.6, p_draw=0.22, p_away=0.18, markets={"over_2.5": 0.7})
    upsert_prediction(log, close, now=datetime(2026, 10, 23, 20, tzinfo=timezone.utc))
    row = log["predictions"][0]
    assert row["p_home"] == 0.5
    assert "markets" not in row
    assert row["refresh"]["markets"]["over_2.5"] == 0.7
    later = dict(first, markets={"over_2.5": 0.2, "btts": 0.4})
    upsert_prediction(log, later, now=datetime(2026, 10, 24, 1, tzinfo=timezone.utc))
    assert row["refresh"]["markets"]["over_2.5"] == 0.7
    assert row["refresh"]["p_home"] == 0.6
