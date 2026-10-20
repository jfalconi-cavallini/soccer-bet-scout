"""First-half scoring shares fitted from historical half-time scores.

Each side's first-half expected goals are its full-match lambda times its
share. The second half is the rest of that lambda. The two grids are
independent given those means: this is a split, not a two-half state model.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import (
    HALF_LEAGUE_MIN_GOALS,
    HALF_LEAGUE_MIN_MATCHES,
    HALF_MIN_GOALS,
    HALF_MIN_MATCHES,
    HALF_PRIOR_GOALS,
    HALF_SHARE_FALLBACK,
    HALF_SHARE_MAX,
    HALF_SHARE_MIN,
)


@dataclass
class HalfBook:
    league_share: dict[str, float]
    global_share: float
    team_ht: dict[str, float]
    team_ft: dict[str, float]
    team_matches: dict[str, int]


def _clamp(value: float) -> float:
    return min(HALF_SHARE_MAX, max(HALF_SHARE_MIN, value))


def _usable_half(match) -> tuple[int, int] | None:
    ht_home = getattr(match, "ht_home", None)
    ht_away = getattr(match, "ht_away", None)
    if ht_home is None or ht_away is None:
        return None
    if ht_home < 0 or ht_away < 0:
        return None
    if ht_home > match.home_goals or ht_away > match.away_goals:
        return None
    return int(ht_home), int(ht_away)


def fit_half_shares(matches) -> HalfBook:
    """League share is half-time goals over full-time goals.

    A league is used only with enough matches and goals. The global share is
    the mean of those league shares, or the flat fallback when none qualify.
    Scoreless matches do not move a ratio, and they still count as matches.
    """
    league_ht: dict[str, float] = {}
    league_ft: dict[str, float] = {}
    league_n: dict[str, int] = {}
    team_ht: dict[str, float] = {}
    team_ft: dict[str, float] = {}
    team_n: dict[str, int] = {}

    for match in matches:
        halves = _usable_half(match)
        if halves is None:
            continue
        ht_home, ht_away = halves
        competition = match.competition_id
        league_ht[competition] = league_ht.get(competition, 0.0) + ht_home + ht_away
        league_ft[competition] = league_ft.get(competition, 0.0) + match.home_goals + match.away_goals
        league_n[competition] = league_n.get(competition, 0) + 1
        for team, ht_goals, ft_goals in (
            (match.home, ht_home, match.home_goals),
            (match.away, ht_away, match.away_goals),
        ):
            team_ht[team] = team_ht.get(team, 0.0) + ht_goals
            team_ft[team] = team_ft.get(team, 0.0) + ft_goals
            team_n[team] = team_n.get(team, 0) + 1

    league_share: dict[str, float] = {}
    for competition, count in league_n.items():
        full_time = league_ft.get(competition, 0.0)
        if count < HALF_LEAGUE_MIN_MATCHES or full_time < HALF_LEAGUE_MIN_GOALS or full_time <= 0:
            continue
        league_share[competition] = _clamp(league_ht[competition] / full_time)

    if league_share:
        global_share = _clamp(sum(league_share.values()) / len(league_share))
    else:
        global_share = HALF_SHARE_FALLBACK

    return HalfBook(
        league_share=league_share,
        global_share=global_share,
        team_ht=team_ht,
        team_ft=team_ft,
        team_matches=team_n,
    )


def scoring_share(book: HalfBook | None, team: str, competition_id: str) -> float:
    """Club share, shrunk toward the league, once the club sample is large enough."""
    if book is None:
        return HALF_SHARE_FALLBACK
    base = book.league_share.get(competition_id, book.global_share)
    played = book.team_matches.get(team, 0)
    scored = book.team_ft.get(team, 0.0)
    if played < HALF_MIN_MATCHES or scored < HALF_MIN_GOALS:
        return base
    early = book.team_ht.get(team, 0.0)
    shrunk = (HALF_PRIOR_GOALS * base + early) / (HALF_PRIOR_GOALS + scored)
    return _clamp(shrunk)
