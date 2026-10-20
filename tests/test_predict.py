"""Goal model outputs and the Elo shift into expected goals."""

from datetime import date

from src.config import FIRST_HALF_SHARE
from src.model.elo import EloMatch, replay
from src.model.predict import predict_match
from src.model.ratings import blend_chance, build_strengths


def _played(day, home, away, hg, ag, xg=None):
    return EloMatch(
        day=day,
        home=home,
        away=away,
        home_goals=hg,
        away_goals=ag,
        competition_id="E0",
        kind="league",
        xg_home=None if xg is None else xg[0],
        xg_away=None if xg is None else xg[1],
    )


def test_xg_blend_sits_between_goals_and_xg():
    blended, used = blend_chance(3, 1.0, xg_weight=0.5)
    assert used is True
    assert blended == 2.0
    goals_only, used_goals = blend_chance(3, None)
    assert used_goals is False
    assert goals_only == 3


def test_prediction_card_fields_and_first_half_share():
    matches = []
    for index in range(12):
        matches.append(_played(date(2025, 8, 1 + index), "alpha", "beta", 2, 0, xg=(1.8, 0.4)))
        matches.append(_played(date(2025, 9, 1 + index), "beta", "gamma", 0, 1, xg=(0.6, 1.4)))
    table = replay(matches)
    book = build_strengths(matches, date(2026, 10, 20))
    pred = predict_match(
        "alpha",
        "gamma",
        "Alpha",
        "Gamma",
        date(2026, 10, 24),
        "2026-10-24T19:30:00+00:00",
        "E0",
        "Premier League",
        "league",
        book,
        table,
        matches,
    )
    assert abs(pred["home_win_pct"] + pred["draw_pct"] + pred["away_win_pct"] - 100) < 0.2
    assert abs(pred["xg_home_1h"] - pred["xg_home"] * FIRST_HALF_SHARE) < 0.02
    assert abs(pred["xg_away_1h"] - pred["xg_away"] * FIRST_HALF_SHARE) < 0.02
    assert "CDT" in pred["kickoff_ct"]
    assert len(pred["top_scorelines"]) == 5
    assert "2.5" in pred["over"]
    assert any(section["title"] == "Goals minus xG" for section in pred["narrative"])
    attack = next(section for section in pred["narrative"] if section["title"] == "Attack against defense")
    assert "defense above 1.00 allows more" in attack["body"]
    # Alpha has been the stronger side, so the Elo gap should favor them.
    assert pred["elo_gap"] > 0
    assert pred["home_win_pct"] > pred["away_win_pct"]


def test_elo_gap_shifts_share_of_goals_not_just_the_label():
    matches = [_played(date(2025, 9, index), "alpha", "beta", 1, 1) for index in range(1, 10)]
    table = replay(matches)
    book = build_strengths(matches, date(2026, 1, 1))
    even = book.lambdas("alpha", "beta", 1500, 1500, "E0", "league")
    tilted = book.lambdas("alpha", "beta", 1700, 1400, "E0", "league")
    assert tilted["lambda_home"] > even["lambda_home"]
    assert abs((tilted["lambda_home"] + tilted["lambda_away"]) - (even["lambda_home"] + even["lambda_away"])) < 0.05
    neutral = book.lambdas("alpha", "beta", 1500, 1500, "UCL", "cup", neutral=True)
    assert even["elo_gap_used"] == even["elo_gap"] + 80
    assert neutral["elo_gap_used"] == 0
    assert even["lambda_home"] > neutral["lambda_home"]


def test_stale_file_hides_form_and_rest():
    matches = [_played(date(2026, 9, 19), "alpha", "beta", 1, 0)]
    table = replay(matches)
    book = build_strengths(matches, date(2026, 10, 21))
    pred = predict_match(
        "alpha",
        "beta",
        "Alpha",
        "Beta",
        date(2026, 10, 21),
        None,
        "E0",
        "Premier League",
        "league",
        book,
        table,
        matches,
        data_through=date(2026, 9, 19),
    )
    form = next(section for section in pred["narrative"] if section["title"] == "Form and chance trend")
    rest = next(section for section in pred["narrative"] if section["title"] == "Rest and travel")
    assert "2026-09-19" in form["body"]
    assert "days ago" not in rest["body"]
    assert any(section["title"] == "Goals minus xG" for section in pred["narrative"])
    fresh = predict_match(
        "alpha",
        "beta",
        "Alpha",
        "Beta",
        date(2026, 10, 21),
        None,
        "E0",
        "Premier League",
        "league",
        book,
        table,
        matches,
        data_through=date(2026, 10, 18),
    )
    fresh_rest = next(section["body"] for section in fresh["narrative"] if section["title"] == "Rest and travel")
    assert "days ago" in fresh_rest


def test_tournament_filter_names_the_loaded_season_until_the_current_one():
    from src.config import tournament_filter_label

    assert tournament_filter_label("Champions League", "2025-26", "2026-27") == "Champions League 2025-26 entrants"
    assert tournament_filter_label("Europa League", "2026-27", "2026-27") == "Europa League"
    assert tournament_filter_label("Conference League", None, "2026-27") == "Conference League"
