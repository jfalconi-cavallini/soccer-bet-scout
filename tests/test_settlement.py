"""Prediction log keeps the first call, then scores it."""

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
