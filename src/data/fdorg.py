"""football-data.org for current-season UEFA matches and UTC kickoffs.

The free tier is 10 requests per minute. This module sleeps between calls
and caches the body. Cups that the plan does not include are skipped.
Keys are read from FOOTBALL_DATA_API_KEY, with FOOTBALL_DATA_KEY as a
legacy alias. Nothing is written except the cache file.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone

from src.config import (
    FDORG_COMPETITIONS,
    FDORG_LEAGUE_CODES,
    LEAGUES,
    SLATE_DAYS,
    TOURNAMENTS,
    season_label,
)
from src.data.cache import CURRENT_TTL, HttpCache
from src.data.models import CatalogMatch
from src.names import canonicalize

BASE = "https://api.football-data.org/v4"
LEAGUE_BY_ID = {league["id"]: league for league in LEAGUES}


def api_key() -> str | None:
    return os.getenv("FOOTBALL_DATA_API_KEY") or os.getenv("FOOTBALL_DATA_KEY") or None


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_fdorg_match(row: dict, competition_id: str, competition: str, kind: str) -> CatalogMatch | None:
    kick = _parse_utc(row.get("utcDate") or "")
    if kick is None:
        return None
    home = canonicalize((row.get("homeTeam") or {}).get("name"))
    away = canonicalize((row.get("awayTeam") or {}).get("name"))
    if not home or not away or home == away:
        return None
    full = ((row.get("score") or {}).get("fullTime") or {})
    status = (row.get("status") or "").upper()
    home_goals = away_goals = None
    if status == "FINISHED":
        try:
            if full.get("home") is not None and full.get("away") is not None:
                home_goals = int(full["home"])
                away_goals = int(full["away"])
        except (TypeError, ValueError):
            home_goals = away_goals = None
    stage = (row.get("stage") or "").upper()
    neutral = stage in {"FINAL", "THIRD_PLACE"}
    return CatalogMatch(
        day=kick.date(),
        home=home,
        away=away,
        home_name=(row.get("homeTeam") or {}).get("name") or home,
        away_name=(row.get("awayTeam") or {}).get("name") or away,
        home_goals=home_goals,
        away_goals=away_goals,
        competition_id=competition_id,
        competition=competition,
        kind=kind,
        neutral=neutral,
        kickoff_utc=kick.isoformat(),
        source="football-data.org",
    )


def _get_json(cache: HttpCache, path: str, params: dict, key: str) -> dict | None:
    text = cache.fetch(
        f"{BASE}{path}",
        ttl_seconds=CURRENT_TTL,
        headers={"X-Auth-Token": key, "User-Agent": "soccer-bet-scout"},
        params=params,
        fdorg=True,
        polite_gap=0,
    )
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load(cache: HttpCache, today: date | None = None) -> list[CatalogMatch]:
    key = api_key()
    if not key:
        print("  [fdorg] FOOTBALL_DATA_API_KEY not set, skipping live cup/fixture sync")
        return []
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    found: list[CatalogMatch] = []

    for code, tournament_id in FDORG_COMPETITIONS.items():
        payload = _get_json(cache, f"/competitions/{code}/matches", {"season": start}, key)
        if not payload:
            print(f"  [fdorg] {code} unavailable on this key")
            continue
        rows = payload.get("matches") or []
        batch = []
        for row in rows:
            match = parse_fdorg_match(row, tournament_id, TOURNAMENTS[tournament_id], "cup")
            if match:
                batch.append(match)
        print(f"  [fdorg] {code} {season_label(start)}: {len(batch)}")
        found.extend(batch)

    # football-data.co.uk's La Liga file lags the calendar. The free plan
    # includes the current Primera Division season, finished and scheduled.
    liga = LEAGUE_BY_ID["SP1"]
    payload = _get_json(cache, "/competitions/PD/matches", {"season": start}, key)
    if not payload:
        print("  [fdorg] PD unavailable on this key")
    else:
        batch = []
        for row in payload.get("matches") or []:
            match = parse_fdorg_match(row, "SP1", liga["name"], "league")
            if match:
                batch.append(match)
        played = sum(1 for match in batch if match.finished)
        print(f"  [fdorg] PD {season_label(start)}: {played} played / {len(batch)} rows")
        found.extend(batch)

    date_to = (today + timedelta(days=SLATE_DAYS)).isoformat()
    codes = ",".join(["PL", "PD", "SA", "BL1", "FL1", "DED", "PPL", "CL", "EL"])
    payload = _get_json(
        cache,
        "/matches",
        {"competitions": codes, "dateFrom": today.isoformat(), "dateTo": date_to},
        key,
    )
    if payload:
        for row in payload.get("matches") or []:
            comp = (row.get("competition") or {}).get("code") or ""
            if comp in FDORG_COMPETITIONS:
                tournament_id = FDORG_COMPETITIONS[comp]
                match = parse_fdorg_match(row, tournament_id, TOURNAMENTS[tournament_id], "cup")
            elif comp in FDORG_LEAGUE_CODES:
                league_id = FDORG_LEAGUE_CODES[comp]
                league = LEAGUE_BY_ID[league_id]
                match = parse_fdorg_match(row, league_id, league["name"], "league")
            else:
                continue
            if match and not match.finished:
                found.append(match)
        print(f"  [fdorg] slate window returned {len(payload.get('matches') or [])} rows")
    return found
