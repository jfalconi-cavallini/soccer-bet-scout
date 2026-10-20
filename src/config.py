"""Shared constants for the scout.

Men's club competitions only. The Elo pool is these domestic leagues plus
UEFA Champions League, Europa League, and Conference League matches.
"""

from __future__ import annotations

import re
from datetime import date

# Competition names that are not the men's pool. Checked on every loaded match.
_WOMENS_COMPETITION = re.compile(
    r"women|woman|feminine|femenina|frauen|dames|ladies|\bwsl\b|\bnwsl\b",
    re.IGNORECASE,
)

# Anchor for the coefficient formula. The average covered league starts here.
ELO_INITIAL = 1500.0
ELO_START_SEASON = 2021  # 2021-22

# Five-year UEFA association coefficients at the end of 2020/21, the ranking
# in force when this pool's first season starts. Source: UEFA country
# coefficient table for 2021 (wildstat / UEFA association rankings).
UEFA_COEFFICIENT_2021 = {
    "E0": 100.569,
    "SP1": 97.855,
    "I1": 75.438,
    "D1": 73.570,
    "F1": 56.081,
    "P1": 48.549,
    "N1": 39.200,
    "B1": 36.500,
    "AT1": 35.825,
    "SC0": 33.375,
    "T1": 30.100,
    "G1": 26.000,
}
# Elo points per coefficient point, so England starts well above Greece.
ELO_PER_COEFFICIENT = 2.5
# Cup-only clubs sit this far under the covered-league average, and regress there.
CUP_ELO_BELOW_LEAGUE = 175.0

# Home advantage added to the home side before the expected-score lookup.
ELO_HOME_ADVANTAGE = 80.0
ELO_K = 22.0

# Between seasons, pull one third of the way back to the league mean.
ELO_REGRESSION = 1.0 / 3.0

# Dixon-Coles low-score correction. Negative rho boosts 0-0 and 1-1.
DIXON_COLES_RHO = -0.10
SCORE_GRID_MAX = 6

# Fallback share of full-match xG assigned to the first half when a league
# has too little half-time history. Fitted shares replace this per club.
FIRST_HALF_SHARE = 0.45
HALF_SHARE_FALLBACK = FIRST_HALF_SHARE
# Shrink a club's own half-time scoring rate toward the league with this
# many goals of prior weight. Ignore the club rate below the match/goal floors.
HALF_PRIOR_GOALS = 12.0
HALF_MIN_MATCHES = 15
HALF_MIN_GOALS = 12.0
HALF_SHARE_MIN = 0.30
HALF_SHARE_MAX = 0.62
# A league share is published only once the half-time sample is this large.
HALF_LEAGUE_MIN_MATCHES = 40
HALF_LEAGUE_MIN_GOALS = 80.0

# Time decay for attack/defense: weight = exp(-xi * days).
# xi = 0.005 is a half-life of about 139 days.
RATING_DECAY_XI = 0.005
RATING_WINDOW_DAYS = 540
RATING_PRIOR_MATCHES = 6.0

# When a match has xG, blend it with actual goals for attack/defense.
XG_BLEND = 0.65

# How much of the goal-difference expectation comes from the Elo gap.
# The rest comes from attack and defense. Non-neutral matches add the
# Elo home advantage onto that gap so the 30% Elo share does not drop it.
# Domestic matches stay here: attack and defense already separate clubs
# inside one league, so Elo only moves the split.
ELO_GOAL_WEIGHT = 0.30
ELO_GOALS_PER_400 = 1.0
# Cross-league and cup matches. Attack and defense are centered inside each
# league, so an average Greek side and an average English side both sit near
# 1 and the domestic blend throws away the league gap. The Elo rating already
# carries that gap (covered leagues sit on their mean, cup-only clubs sit on
# the anchor below). Historical European matches score about two goals of
# difference per 400 Elo points, so the cup difference uses the whole gap at
# that scale. The attack/defense total is kept. Two clubs from the same
# domestic league stay on the domestic blend, including when they meet in Europe.
CUP_ELO_GOAL_WEIGHT = 1.0
CUP_ELO_GOALS_PER_400 = 2.0

CHICAGO_TZ = "America/Chicago"
# football-data.co.uk prints every league's clock in UK local time.
KICKOFF_SOURCE_TZ = "Europe/London"
# UEFA text files and most continental openfootball files use this offset.
CENTRAL_EUROPE_TZ = "Europe/Berlin"

# football-data.co.uk division code, openfootball file code, display name.
# `tz` is the local clock in openfootball's league JSON (not the UK CSV).
LEAGUES: list[dict] = [
    {"id": "E0", "fd": "E0", "of": "en.1", "name": "Premier League", "country": "England", "tz": "Europe/London"},
    {"id": "SP1", "fd": "SP1", "of": "es.1", "name": "La Liga", "country": "Spain", "tz": CENTRAL_EUROPE_TZ},
    {"id": "I1", "fd": "I1", "of": "it.1", "name": "Serie A", "country": "Italy", "tz": CENTRAL_EUROPE_TZ},
    {"id": "D1", "fd": "D1", "of": "de.1", "name": "Bundesliga", "country": "Germany", "tz": CENTRAL_EUROPE_TZ},
    {"id": "F1", "fd": "F1", "of": "fr.1", "name": "Ligue 1", "country": "France", "tz": CENTRAL_EUROPE_TZ},
    {"id": "N1", "fd": "N1", "of": "nl.1", "name": "Eredivisie", "country": "Netherlands", "tz": CENTRAL_EUROPE_TZ},
    {"id": "P1", "fd": "P1", "of": "pt.1", "name": "Primeira Liga", "country": "Portugal", "tz": "Europe/Lisbon"},
    {"id": "B1", "fd": "B1", "of": "be.1", "name": "Belgian Pro League", "country": "Belgium", "tz": CENTRAL_EUROPE_TZ},
    {"id": "T1", "fd": "T1", "of": "tr.1", "name": "Super Lig", "country": "Turkey", "tz": "Europe/Istanbul"},
    {"id": "G1", "fd": "G1", "of": "gr.1", "name": "Super League Greece", "country": "Greece", "tz": "Europe/Athens"},
    {"id": "SC0", "fd": "SC0", "of": "sco.1", "name": "Scottish Premiership", "country": "Scotland", "tz": "Europe/London"},
    {"id": "AT1", "fd": None, "of": "at.1", "name": "Austrian Bundesliga", "country": "Austria", "tz": CENTRAL_EUROPE_TZ},
]

TOURNAMENTS = {
    "UCL": "Champions League",
    "UEL": "Europa League",
    "UECL": "Conference League",
}

# openfootball/champions-league text files. Qualifiers included; they are
# the matches that tie smaller clubs into the shared pool.
CUP_FILES = {
    "cl.txt": "UCL",
    "clq.txt": "UCL",
    "el.txt": "UEL",
    "elq.txt": "UEL",
    "conf.txt": "UECL",
    "confq.txt": "UECL",
}

# football-data.org competition codes tried for the current season.
# The free tier always includes CL. EL / Conference may 403; that is handled.
FDORG_COMPETITIONS = {
    "CL": "UCL",
    "EL": "UEL",
    "ECL": "UECL",
}

FDORG_LEAGUE_CODES = {
    "PL": "E0",
    "PD": "SP1",
    "SA": "I1",
    "BL1": "D1",
    "FL1": "F1",
    "DED": "N1",
    "PPL": "P1",
}

ODDS_SPORTS = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    "soccer_uefa_europa_conference_league",
]

SLATE_DAYS = 16

# If the last result on file is older than this before the match, form and rest
# describe the file gap rather than the team. An international break is shorter.
STALE_RESULT_DAYS = 14


def is_mens_competition(name: str | None) -> bool:
    """True when a competition name is not a women's league or cup."""
    if not name:
        return True
    return _WOMENS_COMPETITION.search(name) is None


def season_start_year(day: date) -> int:
    """European season labelled by the year it starts. July is the boundary."""
    return day.year if day.month >= 7 else day.year - 1


def season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def tournament_filter_label(name: str, season: str | None, current: str) -> str:
    """Name a cup filter by the last season on file until the current one loads."""
    if season and season < current:
        return f"{name} {season} entrants"
    return name


def league_seed(league_id: str) -> float:
    """2021 starting Elo for a covered league, from the UEFA country coefficient."""
    coeff = UEFA_COEFFICIENT_2021.get(league_id)
    if coeff is None:
        return ELO_INITIAL
    mean = sum(UEFA_COEFFICIENT_2021.values()) / len(UEFA_COEFFICIENT_2021)
    return ELO_INITIAL + (coeff - mean) * ELO_PER_COEFFICIENT


def cup_anchor(league_average: float) -> float:
    """Where clubs outside the covered leagues are seeded and regressed."""
    return league_average - CUP_ELO_BELOW_LEAGUE


def current_season_start(today: date | None = None) -> int:
    return season_start_year(today or date.today())


def season_codes(today: date | None = None) -> list[int]:
    """Start years from 2021-22 through the season that contains today."""
    end = current_season_start(today)
    return list(range(ELO_START_SEASON, end + 1))
