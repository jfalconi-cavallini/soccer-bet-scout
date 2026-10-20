"""One Europe-wide club Elo.

Domestic leagues share a single rating pool. Champions League, Europa League,
and Conference League matches are what make a goal in Lisbon comparable to a
goal in Manchester. Covered leagues start in 2021 from their UEFA country
coefficient, not from one shared number. Clubs that never play in those
leagues start 175 points under the league average and regress to that same
point. After each season, ratings move about a third of the way back to that
league's mean, and clubs coming up take the level of the clubs that went down.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from src.config import (
    ELO_HOME_ADVANTAGE,
    ELO_INITIAL,
    ELO_K,
    ELO_REGRESSION,
    ELO_START_SEASON,
    LEAGUES,
    cup_anchor,
    league_seed,
    season_label,
    season_start_year,
)


@dataclass(frozen=True)
class EloMatch:
    """One finished match in replay order. `date` is the kickoff date."""

    day: date
    home: str
    away: str
    home_goals: int
    away_goals: int
    competition_id: str
    kind: str  # "league" or "cup"
    neutral: bool = False
    xg_home: float | None = None
    xg_away: float | None = None


@dataclass
class HistoryPoint:
    day: str
    rating: float
    opponent: str | None = None
    competition_id: str | None = None
    event: str = "match"


@dataclass
class EloTable:
    ratings: dict[str, float]
    history: dict[str, list[HistoryPoint]] = field(default_factory=dict)
    matches_played: dict[str, int] = field(default_factory=dict)
    league_by_team: dict[str, str] = field(default_factory=dict)
    tournaments_by_team: dict[str, set[str]] = field(default_factory=dict)
    tournament_season: dict[str, str] = field(default_factory=dict)
    # team -> tournament id -> latest season label the club appeared in
    team_tournament_seasons: dict[str, dict[str, str]] = field(default_factory=dict)

    def rating(self, team: str) -> float:
        return self.ratings.get(team, ELO_INITIAL)


def expected_score(rating_home: float, rating_away: float, home_advantage: float) -> float:
    """Home side's expected result on a 0-1 scale (draw is 0.5)."""
    return 1.0 / (1.0 + 10 ** ((rating_away - rating_home - home_advantage) / 400.0))


def result_score(goal_diff: float) -> float:
    """Map an xG difference onto the 0-1 scale. Not used for the goal result.

    The goal result is a plain win, draw, or loss. Putting this curve on the
    scoreline as well as margin_multiplier counts the margin twice.
    """
    return 1.0 / (1.0 + math.exp(-goal_diff / 1.2))


def outcome_score(home_goals: int, away_goals: int) -> float:
    """Win 1, draw 0.5, loss 0. The margin multiplier carries the goal difference."""
    if home_goals > away_goals:
        return 1.0
    if home_goals == away_goals:
        return 0.5
    return 0.0


def margin_multiplier(goal_diff: int) -> float:
    """Larger margins move the rating more. One-goal games stay at 1."""
    gap = abs(int(goal_diff))
    if gap <= 1:
        return 1.0
    if gap == 2:
        return 1.5
    return (11.0 + gap) / 8.0


def actual_score(match: EloMatch) -> float:
    """Win/draw/loss, blended with the xG curve when the match has expected goals."""
    goals = outcome_score(match.home_goals, match.away_goals)
    if match.xg_home is None or match.xg_away is None:
        return goals
    chances = result_score(match.xg_home - match.xg_away)
    return 0.5 * goals + 0.5 * chances


def apply_match(ratings: dict[str, float], match: EloMatch, k: float = ELO_K) -> tuple[float, float]:
    """Update ratings in place. Returns (new_home, new_away)."""
    home_adv = 0.0 if match.neutral else ELO_HOME_ADVANTAGE
    home_rating = ratings.get(match.home, ELO_INITIAL)
    away_rating = ratings.get(match.away, ELO_INITIAL)
    expected = expected_score(home_rating, away_rating, home_adv)
    delta = k * margin_multiplier(match.home_goals - match.away_goals) * (actual_score(match) - expected)
    ratings[match.home] = home_rating + delta
    ratings[match.away] = away_rating - delta
    return ratings[match.home], ratings[match.away]


def regress_toward(rating: float, mean: float, fraction: float = ELO_REGRESSION) -> float:
    """Move `fraction` of the gap toward `mean`. fraction=1/3 is the default."""
    return mean + (rating - mean) * (1.0 - fraction)


def inherit_promoted(
    ratings: dict[str, float],
    previous: set[str],
    upcoming: set[str],
) -> None:
    """Promoted clubs take the average rating of the clubs that left the league.

    The average is taken after between-season regression, so the sides coming
    up replace the sides going down at the same level and the league's rating
    mass stays put. Alphabetical order is not used; every promoted club gets
    the same inherited level.
    """
    relegated = previous - upcoming
    promoted = upcoming - previous
    if not promoted or not relegated:
        return
    levels = [ratings[team] for team in relegated if team in ratings]
    if not levels:
        return
    level = sum(levels) / len(levels)
    for team in promoted:
        ratings[team] = level


def _record(history: dict[str, list[HistoryPoint]], team: str, point: HistoryPoint) -> None:
    history.setdefault(team, []).append(point)


def replay(matches: list[EloMatch], today: date | None = None) -> EloTable:
    """Replay every match from the seeded 2021-22 season through `today`.

    The same multiset of matches always produces the same ratings. Input
    order does not matter; matches are sorted before they are applied.
    """
    ordered = sorted(
        matches,
        key=lambda match: (match.day, match.competition_id, match.home, match.away, match.kind),
    )
    ratings: dict[str, float] = {}
    history: dict[str, list[HistoryPoint]] = {}
    played: dict[str, int] = {}
    league_by_team: dict[str, str] = {}
    tournaments: dict[str, set[str]] = {}
    tournament_season: dict[str, str] = {}
    team_tournament_seasons: dict[str, dict[str, str]] = {}

    members: dict[int, dict[str, set[str]]] = {}
    for match in ordered:
        if match.kind != "league":
            continue
        year = season_start_year(match.day)
        members.setdefault(year, {}).setdefault(match.competition_id, set()).update(
            {match.home, match.away}
        )

    seen_seasons: list[int] = []
    current_season: int | None = None
    opening = members.get(ELO_START_SEASON, {})
    team_open_league: dict[str, str] = {}
    for league, teams in opening.items():
        for team in teams:
            team_open_league[team] = league
    covered_average = sum(league_seed(league["id"]) for league in LEAGUES) / len(LEAGUES)

    def starting_rating(team: str, league_id: str | None) -> float:
        if team in team_open_league:
            return league_seed(team_open_league[team])
        if league_id:
            return league_seed(league_id)
        return cup_anchor(covered_average)

    def ensure(team: str, day: date, league_id: str | None) -> None:
        if team not in ratings:
            start = starting_rating(team, league_id)
            ratings[team] = start
            _record(
                history,
                team,
                HistoryPoint(day=day.isoformat(), rating=round(start, 2), event="seed"),
            )

    def close_season(previous: int, boundary: date) -> None:
        prev_members = members.get(previous, {})
        all_prev = set().union(*prev_members.values()) if prev_members else set()
        for league, teams in prev_members.items():
            if len(teams) < 2:
                continue
            mean = sum(ratings.get(team, ELO_INITIAL) for team in teams) / len(teams)
            for team in teams:
                ratings[team] = regress_toward(ratings.get(team, ELO_INITIAL), mean)
        domestic = [ratings[team] for team in all_prev if team in ratings]
        league_level = sum(domestic) / len(domestic) if domestic else covered_average
        for team in list(ratings):
            if team not in all_prev:
                ratings[team] = regress_toward(ratings[team], cup_anchor(league_level))
        next_year = previous + 1
        next_members = members.get(next_year, {})
        for league, upcoming in next_members.items():
            inherit_promoted(ratings, prev_members.get(league, set()), upcoming)
        for team, rating in ratings.items():
            _record(
                history,
                team,
                HistoryPoint(day=boundary.isoformat(), rating=round(rating, 2), event="season"),
            )

    for match in ordered:
        if today is not None and match.day > today:
            break
        season = season_start_year(match.day)
        league_id = match.competition_id if match.kind == "league" else None
        ensure(match.home, match.day, league_id)
        ensure(match.away, match.day, league_id)
        if current_season is None:
            current_season = season
            seen_seasons.append(season)
        elif season != current_season:
            close_season(current_season, date(season, 7, 1))
            current_season = season
            seen_seasons.append(season)

        new_home, new_away = apply_match(ratings, match)
        played[match.home] = played.get(match.home, 0) + 1
        played[match.away] = played.get(match.away, 0) + 1
        _record(
            history,
            match.home,
            HistoryPoint(
                day=match.day.isoformat(),
                rating=round(new_home, 2),
                opponent=match.away,
                competition_id=match.competition_id,
                event="match",
            ),
        )
        _record(
            history,
            match.away,
            HistoryPoint(
                day=match.day.isoformat(),
                rating=round(new_away, 2),
                opponent=match.home,
                competition_id=match.competition_id,
                event="match",
            ),
        )
        if match.kind == "league":
            league_by_team[match.home] = match.competition_id
            league_by_team[match.away] = match.competition_id
        else:
            label = season_label(season)
            for team in (match.home, match.away):
                tournaments.setdefault(team, set()).add(match.competition_id)
                seasons = team_tournament_seasons.setdefault(team, {})
                previous_team = seasons.get(match.competition_id)
                if previous_team is None or previous_team < label:
                    seasons[match.competition_id] = label
            # Latest season that actually contains this tournament.
            previous = tournament_season.get(match.competition_id)
            if previous is None or previous < label:
                tournament_season[match.competition_id] = label

    return EloTable(
        ratings={team: round(rating, 4) for team, rating in ratings.items()},
        history=history,
        matches_played=played,
        league_by_team=league_by_team,
        tournaments_by_team=tournaments,
        tournament_season=tournament_season,
        team_tournament_seasons=team_tournament_seasons,
    )
