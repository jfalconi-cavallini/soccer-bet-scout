"""League goal totals stay near the goals those leagues actually scored."""

from datetime import date, timedelta

from src.model.elo import EloMatch
from src.model.ratings import build_strengths


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
