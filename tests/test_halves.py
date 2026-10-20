"""Half-time shares fitted from historical scores, and the grids they feed."""

from datetime import date, timedelta

from src.config import FIRST_HALF_SHARE
from src.data.fduk import parse_csv
from src.data.models import CatalogMatch, prefer
from src.model.dixon_coles import score_grid
from src.model.elo import EloMatch, replay
from src.model.halves import fit_half_shares, scoring_share
from src.model.predict import predict_match
from src.model.ratings import build_strengths


def _half(index: int, home: str, away: str, hg: int, ag: int, ht_h: int, ht_a: int, competition: str = "E0"):
    return EloMatch(
        day=date(2024, 8, 1) + timedelta(days=index),
        home=home,
        away=away,
        home_goals=hg,
        away_goals=ag,
        competition_id=competition,
        kind="league",
        ht_home=ht_h,
        ht_away=ht_a,
    )


def _league_at_half(count: int = 200) -> list[EloMatch]:
    """1-0 at half-time, 2-0 at full-time. Share sits on 0.5."""
    return [_half(index, f"home{index}", f"away{index}", 2, 0, 1, 0) for index in range(count)]


def test_league_share_tracks_half_time_goals_and_stays_in_range():
    book = fit_half_shares(_league_at_half(40))
    assert book.league_share["E0"] == 0.5
    assert 0.35 <= book.league_share["E0"] <= 0.55
    thin = fit_half_shares(_league_at_half(10))
    assert "E0" not in thin.league_share
    assert thin.global_share == FIRST_HALF_SHARE


def test_a_supported_early_scorer_moves_above_the_league_and_stays_shrunk():
    matches = _league_at_half(200)
    for index in range(16):
        matches.append(_half(300 + index, "hot", f"foil{index}", 2, 0, 2, 0))
    book = fit_half_shares(matches)
    league = book.league_share["E0"]
    hot = scoring_share(book, "hot", "E0")
    assert 0.35 <= league <= 0.55
    assert hot > league
    assert hot < 0.95
    assert hot <= 0.62
    # Two matches, every goal in the first half, is not enough to leave the league.
    matches.append(_half(400, "thin", "foilx", 2, 0, 2, 0))
    matches.append(_half(401, "thin", "foily", 2, 0, 2, 0))
    small = fit_half_shares(matches)
    assert scoring_share(small, "thin", "E0") == small.league_share["E0"]


def test_scoreless_matches_count_without_moving_the_ratio():
    matches = _league_at_half(40)
    for index in range(15):
        matches.append(_half(500 + index, "quiet", f"nil{index}", 0, 0, 0, 0))
    book = fit_half_shares(matches)
    assert book.team_matches["quiet"] == 15
    assert book.team_ft["quiet"] == 0
    assert scoring_share(book, "quiet", "E0") == book.league_share["E0"]
    assert book.league_share["E0"] == 0.5


def test_impossible_half_is_ignored_and_a_missing_half_is_absent():
    text = """Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG
E0,24/10/2026,15:00,Arsenal,Everton,2,0,1,0
E0,25/10/2026,15:00,Chelsea,Spurs,1,0,2,0
E0,26/10/2026,15:00,Liverpool,Brentford,1,1,,
"""
    rows = parse_csv(text, {"id": "E0", "name": "Premier League"})
    assert [(row.home_goals, row.ht_home, row.ht_away) for row in rows] == [
        (2, 1, 0),
        (1, None, None),
        (1, None, None),
    ]
    kept = prefer(
        CatalogMatch(
            day=date(2026, 10, 24),
            home="arsenal",
            away="everton",
            home_name="Arsenal",
            away_name="Everton",
            home_goals=2,
            away_goals=0,
            competition_id="E0",
            competition="Premier League",
            kind="league",
            xg_home=1.8,
            xg_away=0.4,
        ),
        CatalogMatch(
            day=date(2026, 10, 24),
            home="arsenal",
            away="everton",
            home_name="Arsenal",
            away_name="Everton",
            home_goals=2,
            away_goals=0,
            competition_id="E0",
            competition="Premier League",
            kind="league",
            ht_home=1,
            ht_away=0,
        ),
    )
    assert kept.xg_home == 1.8
    assert kept.ht_home == 1 and kept.ht_away == 0
    assert kept.to_elo().ht_home == 1


def test_first_half_grid_sums_to_one_and_fallback_stays_flat():
    matches = []
    for index in range(12):
        matches.append(
            EloMatch(
                day=date(2025, 8, 1) + timedelta(days=index),
                home="alpha",
                away="beta",
                home_goals=2,
                away_goals=0,
                competition_id="E0",
                kind="league",
            )
        )
    table = replay(matches)
    book = build_strengths(matches, date(2026, 10, 20))
    pred = predict_match(
        "alpha",
        "gamma",
        "Alpha",
        "Gamma",
        date(2026, 10, 24),
        None,
        "E0",
        "Premier League",
        "league",
        book,
        table,
        matches,
    )
    assert abs(pred["xg_home_1h"] - pred["xg_home"] * FIRST_HALF_SHARE) < 0.02
    half = pred["first_half"]
    assert abs(half["home_win_pct"] + half["draw_pct"] + half["away_win_pct"] - 100) < 0.2
    assert "0.5" in half["over"] and "1.5" in half["under"]
    assert len(half["top_scorelines"]) == 5
    assert pred["second_half"]["xg_home"] > 0
    grid = score_grid(pred["xg_home"] * FIRST_HALF_SHARE, pred["xg_away"] * FIRST_HALF_SHARE)
    assert abs(sum(sum(row) for row in grid) - 1) < 1e-9

    fitted = _league_at_half(200)
    for index in range(16):
        fitted.append(_half(300 + index, "alpha", f"foil{index}", 2, 0, 2, 0))
    half_book = fit_half_shares(fitted)
    tilted = predict_match(
        "alpha",
        "gamma",
        "Alpha",
        "Gamma",
        date(2026, 10, 24),
        None,
        "E0",
        "Premier League",
        "league",
        book,
        table,
        matches,
        half_book=half_book,
    )
    assert tilted["model"]["first_half_share_home"] > FIRST_HALF_SHARE
    assert tilted["xg_home_1h"] > pred["xg_home_1h"]
    assert tilted["home_win_pct"] == pred["home_win_pct"]
