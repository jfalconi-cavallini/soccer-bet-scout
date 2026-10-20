"""openfootball JSON for leagues that football-data.co.uk does not cover,
plus scheduled fixtures (full-season files include dates that have not been played).

A dict score with an `ft` pair is a result. A bare list such as [0, 0] is the
placeholder openfootball uses for an unplayed match, not a real 0-0.
"""

from __future__ import annotations

import json
from datetime import date

from src.config import LEAGUES, season_codes, season_label
from src.data.cache import CURRENT_TTL, PAST_TTL, HttpCache
from src.data.models import CatalogMatch
from src.names import canonicalize
from src.report.timeutil import london_kickoff

BASE = "https://raw.githubusercontent.com/openfootball/football.json/master"


def parse_document(payload: dict, league: dict, source: str) -> list[CatalogMatch]:
    matches: list[CatalogMatch] = []
    for row in payload.get("matches") or []:
        raw_day = row.get("date")
        if not raw_day:
            continue
        try:
            day = date.fromisoformat(raw_day)
        except ValueError:
            continue
        home = canonicalize(row.get("team1"))
        away = canonicalize(row.get("team2"))
        if not home or not away or home == away:
            continue
        home_goals, away_goals = _score(row.get("score"))
        kickoff = london_kickoff(day, row.get("time")).isoformat()
        matches.append(
            CatalogMatch(
                day=day,
                home=home,
                away=away,
                home_name=str(row.get("team1") or home),
                away_name=str(row.get("team2") or away),
                home_goals=home_goals,
                away_goals=away_goals,
                competition_id=league["id"],
                competition=league["name"],
                kind="league",
                kickoff_utc=kickoff,
                source=source,
            )
        )
    return matches


def _score(score) -> tuple[int | None, int | None]:
    if isinstance(score, dict):
        ft = score.get("ft")
        if isinstance(ft, (list, tuple)) and len(ft) == 2 and ft[0] is not None and ft[1] is not None:
            try:
                return int(ft[0]), int(ft[1])
            except (TypeError, ValueError):
                return None, None
    return None, None


def load(cache: HttpCache, today: date | None = None) -> list[CatalogMatch]:
    """Fixtures for every tracked league, plus results for leagues without a CSV."""
    today = today or date.today()
    current = season_codes(today)[-1]
    found: list[CatalogMatch] = []
    for start in season_codes(today):
        folder = f"{start}-{str(start + 1)[-2:]}"
        ttl = CURRENT_TTL if start == current else PAST_TTL
        for league in LEAGUES:
            url = f"{BASE}/{folder}/{league['of']}.json"
            text = cache.fetch(url, ttl_seconds=ttl, headers={"User-Agent": "soccer-bet-scout"})
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            batch = parse_document(payload, league, "openfootball")
            if league["fd"]:
                # CSV is the result of record. Keep JSON rows only as fixtures.
                batch = [match for match in batch if not match.finished]
            print(f"  [openfootball] {league['id']} {season_label(start)}: {len(batch)}")
            found.extend(batch)
    return found
