"""Attack and defense ratings, then a per-match expected-goals pair.

Each club's attack is how many chances they create relative to the venue
baseline. Defense is how many they allow, same idea. Recent matches count
more. When a file has xG, those values are blended with actual goals.
The Elo gap then shifts the goal difference without replacing the totals.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from src.config import (
    ELO_GOAL_WEIGHT,
    ELO_GOALS_PER_400,
    RATING_DECAY_XI,
    RATING_PRIOR_MATCHES,
    RATING_WINDOW_DAYS,
    XG_BLEND,
)
from src.model.elo import EloMatch


def blend_chance(goals: int, xg: float | None, xg_weight: float = XG_BLEND) -> tuple[float, bool]:
    """Return (chance value, whether real xG was used)."""
    if xg is None:
        return float(goals), False
    return (1.0 - xg_weight) * float(goals) + xg_weight * float(xg), True


def _shrink(average: float, weight: float, prior: float, prior_weight: float) -> float:
    if weight <= 0:
        return prior
    return (average * weight + prior * prior_weight) / (weight + prior_weight)


class StrengthBook:
    """Venue-specific attack/defense and league scoring baselines."""

    def __init__(self) -> None:
        self.attack_home: dict[str, float] = {}
        self.attack_away: dict[str, float] = {}
        self.defense_home: dict[str, float] = {}
        self.defense_away: dict[str, float] = {}
        self.league_home: dict[str, float] = {}
        self.league_away: dict[str, float] = {}
        self.team_league: dict[str, str] = {}
        self.global_home = 1.45
        self.global_away = 1.15
        self.xg_matches = 0
        self.goal_matches = 0

    def baseline(self, team: str, venue: str) -> float:
        league = self.team_league.get(team)
        table = self.league_home if venue == "home" else self.league_away
        if league and league in table:
            return table[league]
        return self.global_home if venue == "home" else self.global_away

    def lambdas(
        self,
        home: str,
        away: str,
        elo_home: float,
        elo_away: float,
        competition_id: str | None,
        kind: str,
    ) -> dict:
        """Expected goals for one match, before and after the Elo shift."""
        if kind == "league" and competition_id in self.league_home:
            base_home = self.league_home[competition_id]
            base_away = self.league_away[competition_id]
        else:
            base_home = 0.5 * (self.baseline(home, "home") + self.baseline(away, "home"))
            base_away = 0.5 * (self.baseline(home, "away") + self.baseline(away, "away"))

        home_attack = self.attack_home.get(home, 1.0)
        away_defense = self.defense_away.get(away, 1.0)
        away_attack = self.attack_away.get(away, 1.0)
        home_defense = self.defense_home.get(home, 1.0)

        raw_home = max(0.15, base_home * home_attack * away_defense)
        raw_away = max(0.15, base_away * away_attack * home_defense)

        total = raw_home + raw_away
        raw_diff = raw_home - raw_away
        elo_diff = (elo_home - elo_away) / 400.0 * ELO_GOALS_PER_400
        blended_diff = (1.0 - ELO_GOAL_WEIGHT) * raw_diff + ELO_GOAL_WEIGHT * elo_diff
        # Keep the match total from the attack/defense model. Elo only
        # moves how that total is shared.
        lam_home = max(0.15, (total + blended_diff) / 2.0)
        lam_away = max(0.15, (total - blended_diff) / 2.0)
        return {
            "lambda_home_raw": raw_home,
            "lambda_away_raw": raw_away,
            "lambda_home": lam_home,
            "lambda_away": lam_away,
            "elo_gap": elo_home - elo_away,
            "base_home": base_home,
            "base_away": base_away,
            "home_attack": home_attack,
            "away_attack": away_attack,
            "home_defense": home_defense,
            "away_defense": away_defense,
        }


def build_strengths(
    matches: list[EloMatch],
    as_of: date,
    decay: float = RATING_DECAY_XI,
    window_days: int = RATING_WINDOW_DAYS,
    prior_matches: float = RATING_PRIOR_MATCHES,
    xg_weight: float = XG_BLEND,
) -> StrengthBook:
    """Fit strengths from matches strictly before `as_of`."""
    book = StrengthBook()
    earliest = as_of - timedelta(days=window_days)
    used = [
        match
        for match in matches
        if earliest <= match.day < as_of
    ]

    # League baselines from domestic games only.
    home_sum: dict[str, float] = {}
    away_sum: dict[str, float] = {}
    weight_sum: dict[str, float] = {}
    for match in used:
        if match.kind != "league":
            continue
        weight = math.exp(-decay * (as_of - match.day).days)
        home_chance, used_xg = blend_chance(match.home_goals, match.xg_home, xg_weight)
        away_chance, away_xg = blend_chance(match.away_goals, match.xg_away, xg_weight)
        if used_xg or away_xg:
            book.xg_matches += 1
        else:
            book.goal_matches += 1
        league = match.competition_id
        home_sum[league] = home_sum.get(league, 0.0) + weight * home_chance
        away_sum[league] = away_sum.get(league, 0.0) + weight * away_chance
        weight_sum[league] = weight_sum.get(league, 0.0) + weight
        book.team_league[match.home] = league
        book.team_league[match.away] = league

    for league, weight in weight_sum.items():
        if weight <= 0:
            continue
        book.league_home[league] = home_sum[league] / weight
        book.league_away[league] = away_sum[league] / weight

    if book.league_home:
        book.global_home = sum(book.league_home.values()) / len(book.league_home)
        book.global_away = sum(book.league_away.values()) / len(book.league_away)

    # Per-team indexed attack and defense, one number per venue.
    buckets: dict[str, dict[str, float]] = {}

    def add(team: str, slot: str, weight: float, value: float) -> None:
        row = buckets.setdefault(team, {})
        row[slot] = row.get(slot, 0.0) + weight * value
        row[slot + "_w"] = row.get(slot + "_w", 0.0) + weight

    for match in used:
        weight = math.exp(-decay * (as_of - match.day).days)
        if match.kind == "league" and match.competition_id in book.league_home:
            base_home = book.league_home[match.competition_id]
            base_away = book.league_away[match.competition_id]
        else:
            base_home = book.global_home
            base_away = book.global_away
        base_home = max(base_home, 0.4)
        base_away = max(base_away, 0.3)
        home_chance, _ = blend_chance(match.home_goals, match.xg_home, xg_weight)
        away_chance, _ = blend_chance(match.away_goals, match.xg_away, xg_weight)
        add(match.home, "ah", weight, home_chance / base_home)
        add(match.home, "dh", weight, away_chance / base_away)
        add(match.away, "aa", weight, away_chance / base_away)
        add(match.away, "da", weight, home_chance / base_home)

    for team, row in buckets.items():
        def avg(slot: str) -> float:
            weight = row.get(slot + "_w", 0.0)
            if weight <= 0:
                return 1.0
            return _shrink(row[slot] / weight, weight, 1.0, prior_matches)

        book.attack_home[team] = avg("ah")
        book.defense_home[team] = avg("dh")
        book.attack_away[team] = avg("aa")
        book.defense_away[team] = avg("da")

    return book
