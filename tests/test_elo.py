"""Elo replay: same matches, same ratings, including season regression."""

from datetime import date

from src.model.elo import EloMatch, margin_multiplier, replay, result_score


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


def test_bigger_margin_moves_more_than_a_one_goal_win():
    close = replay([_match(date(2021, 8, 14), "alpha", "beta", 1, 0)])
    wide = replay([_match(date(2021, 8, 14), "alpha", "beta", 4, 0)])
    assert wide.rating("alpha") > close.rating("alpha")
    assert margin_multiplier(1) == 1
    assert margin_multiplier(2) == 1.5
    assert result_score(0) == 0.5
