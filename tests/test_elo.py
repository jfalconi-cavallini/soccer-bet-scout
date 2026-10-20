"""Elo replay: same matches, same ratings, including season regression."""

from datetime import date

from src.model.elo import (
    EloMatch,
    actual_score,
    margin_multiplier,
    outcome_score,
    replay,
    result_score,
)


def _match(day, home, away, hg, ag, competition="E0", kind="league", neutral=False, xg=None):
    xg_home = xg_away = None
    if xg is not None:
        xg_home, xg_away = xg
    return EloMatch(
        day=day,
        home=home,
        away=away,
        home_goals=hg,
        away_goals=ag,
        competition_id=competition,
        kind=kind,
        neutral=neutral,
        xg_home=xg_home,
        xg_away=xg_away,
    )


def test_replay_is_deterministic_regardless_of_input_order():
    matches = [
        _match(date(2021, 8, 14), "alpha", "beta", 2, 0),
        _match(date(2021, 8, 21), "beta", "alpha", 1, 1),
        _match(date(2021, 9, 15), "alpha", "gamma", 3, 1, xg=(2.4, 0.8)),
        _match(date(2021, 10, 2), "gamma", "beta", 0, 1, kind="cup", competition="UCL"),
        _match(date(2022, 8, 13), "alpha", "beta", 1, 0),
    ]
    forward = replay(matches)
    backward = replay(list(reversed(matches)))
    assert forward.ratings == backward.ratings
    assert forward.history.keys() == backward.history.keys()
    for team in forward.history:
        assert [point.rating for point in forward.history[team]] == [
            point.rating for point in backward.history[team]
        ]


def test_promoted_club_inherits_relegated_level():
    matches = [
        _match(date(2021, 8, 1 + i), "alpha", "beta", 3, 0)
        for i in range(8)
    ]
    matches.append(_match(date(2022, 8, 6), "alpha", "gamma", 1, 1))
    table = replay(matches)

    def season_rating(team):
        points = [point for point in table.history[team] if point.event == "season"]
        assert points, team
        return points[-1].rating

    assert season_rating("gamma") == season_rating("beta")
    assert table.rating("alpha") > table.rating("beta")


def test_opening_leagues_follow_the_uefa_coefficient_and_cup_clubs_start_lower():
    from src.config import ELO_INITIAL, cup_anchor, league_seed

    assert league_seed("E0") > league_seed("P1") > league_seed("N1")
    assert league_seed("P1") > league_seed("B1") > league_seed("G1")
    matches = [
        _match(date(2021, 8, 1), "alpha", "beta", 1, 0),
        _match(date(2021, 9, 15), "minnow", "alpha", 0, 1, kind="cup", competition="UCL"),
        _match(date(2022, 8, 6), "alpha", "beta", 1, 0),
    ]
    table = replay(matches)

    def point(team: str, event: str) -> float:
        return next(item.rating for item in table.history[team] if item.event == event)

    assert point("alpha", "seed") == round(league_seed("E0"), 2)
    assert point("minnow", "seed") == round(cup_anchor(ELO_INITIAL), 2)
    assert point("alpha", "seed") - point("minnow", "seed") >= 150
    # Season regression pulls the cup club toward the domestic average minus 175,
    # which sits under the Premier League seed and is not 1500.
    assert point("minnow", "season") < point("alpha", "seed") - 100


def test_bigger_margin_moves_more_than_a_one_goal_win():
    close = replay([_match(date(2021, 8, 14), "alpha", "beta", 1, 0)])
    wide = replay([_match(date(2021, 8, 14), "alpha", "beta", 4, 0)])
    assert wide.rating("alpha") > close.rating("alpha")
    # The scoreline itself is a win, not a goal-difference curve.
    # result_score(4) is about 0.97; the multiplier is what separates 4-0 from 1-0.
    assert actual_score(_match(date(2021, 8, 14), "alpha", "beta", 4, 0)) == 1.0
    assert actual_score(_match(date(2021, 8, 14), "alpha", "beta", 1, 0)) == 1.0
    assert margin_multiplier(1) == 1
    assert margin_multiplier(2) == 1.5
    assert result_score(0) == 0.5
    assert outcome_score(2, 0) == 1
    assert outcome_score(1, 1) == 0.5
    assert outcome_score(0, 2) == 0
