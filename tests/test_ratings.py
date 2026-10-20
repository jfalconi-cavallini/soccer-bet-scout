"""League goal totals stay near the goals those leagues actually scored."""

from datetime import date, timedelta

from src.model.elo import EloMatch
from src.model.ratings import StrengthBook, build_strengths


def test_predicted_league_total_matches_actual_goals():
    teams = [f"t{index}" for index in range(6)]
    attack = [1.45, 1.25, 1.05, 0.95, 0.75, 0.55]
    defense = [0.70, 0.85, 1.00, 1.05, 1.25, 1.45]
    start = date(2025, 8, 1)
    matches = []
    day = start
    for home_i, home in enumerate(teams):
        for away_i, away in enumerate(teams):
            if home_i == away_i:
                continue
            home_goals = max(0, round(1.45 * attack[home_i] * defense[away_i]))
            away_goals = max(0, round(1.15 * attack[away_i] * defense[home_i]))
            matches.append(
                EloMatch(
                    day=day,
                    home=home,
                    away=away,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    competition_id="E0",
                    kind="league",
                )
            )
            day += timedelta(days=1)

    as_of = date(2026, 1, 1)
    book = build_strengths(matches, as_of)
    predicted = []
    actual = []
    for match in matches:
        lambdas = book.lambdas(match.home, match.away, 1500, 1500, "E0", "league")
        predicted.append(lambdas["lambda_home"] + lambdas["lambda_away"])
        actual.append(match.home_goals + match.away_goals)
    pred_mean = sum(predicted) / len(predicted)
    act_mean = sum(actual) / len(actual)
    assert abs(pred_mean - act_mean) < 0.15, (pred_mean, act_mean)


def test_cross_league_cup_takes_the_goal_difference_from_elo():
    """A weaker league is not treated as an equal opponent just because its index is 1."""
    book = StrengthBook()
    book.league_home = {"E0": 1.55, "G1": 1.45}
    book.league_away = {"E0": 1.15, "G1": 1.10}
    book.team_league = {"city": "E0", "aek": "G1", "villa": "E0"}
    for team in ("city", "aek", "villa", "slovan"):
        book.attack_home[team] = book.attack_away[team] = 1.0
        book.defense_home[team] = book.defense_away[team] = 1.0
    book.attack_home["city"] = 1.2

    league = book.lambdas("city", "villa", 1800, 1500, "E0", "league")
    same_cup = book.lambdas("city", "villa", 1800, 1500, "UCL", "cup")
    cross = book.lambdas("city", "aek", 1800, 1500, "UCL", "cup")
    uncovered = book.lambdas("city", "slovan", 1700, 1325, "UCL", "cup")

    # Domestic split still preserves the attack/defense total.
    assert abs(
        (league["lambda_home"] + league["lambda_away"])
        - (league["lambda_home_raw"] + league["lambda_away_raw"])
    ) < 0.05
    assert league["cross_league"] is False
    # Two clubs from one league keep that split in a cup.
    assert same_cup["cross_league"] is False
    assert abs(same_cup["lambda_home"] - league["lambda_home"]) < 1e-9
    assert abs(same_cup["lambda_away"] - league["lambda_away"]) < 1e-9

    # (300 + 80) / 400 * 2 goals. The weaker side's rate falls, the favorite's rises.
    assert cross["cross_league"] is True
    assert abs((cross["lambda_home"] - cross["lambda_away"]) - (380 / 400 * 2)) < 0.05
    assert cross["lambda_home"] > cross["lambda_home_raw"]
    assert cross["lambda_away"] < cross["lambda_away_raw"]
    assert (cross["lambda_home"] - cross["lambda_away"]) > (league["lambda_home"] - league["lambda_away"])

    # A club with no domestic league is on the cup scale too, not the 30% blend.
    assert uncovered["cross_league"] is True
    assert abs((uncovered["lambda_home"] - uncovered["lambda_away"]) - ((375 + 80) / 400 * 2)) < 0.05
