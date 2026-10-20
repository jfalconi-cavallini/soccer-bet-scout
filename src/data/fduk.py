"""Historical results from football-data.co.uk CSV files.

These files are the domestic backbone: full-time score, and on recent
seasons the HxG / AxG columns the goal model blends in.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

from src.config import LEAGUES, season_codes, season_label
from src.data.cache import CURRENT_TTL, PAST_TTL, HttpCache
from src.data.models import CatalogMatch
from src.names import canonicalize
from src.report.timeutil import london_kickoff

BASE = "https://www.football-data.co.uk/mmz4281"


def _parse_day(value: str) -> date | None:
    value = (value or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _float(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int(value: str) -> int | None:
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_csv(text: str, league: dict) -> list[CatalogMatch]:
    if not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    matches: list[CatalogMatch] = []
    for row in reader:
        day = _parse_day(row.get("Date") or "")
        home_raw = (row.get("HomeTeam") or "").strip()
        away_raw = (row.get("AwayTeam") or "").strip()
        home = canonicalize(home_raw)
        away = canonicalize(away_raw)
        if day is None or not home or not away or home == away:
            continue
        kickoff = london_kickoff(day, (row.get("Time") or "").strip() or None).isoformat()
        matches.append(
            CatalogMatch(
                day=day,
                home=home,
                away=away,
                home_name=home_raw,
                away_name=away_raw,
                home_goals=_int(row.get("FTHG") or ""),
                away_goals=_int(row.get("FTAG") or ""),
                competition_id=league["id"],
                competition=league["name"],
                kind="league",
                xg_home=_float(row.get("HxG") or ""),
                xg_away=_float(row.get("AxG") or ""),
                kickoff_utc=kickoff,
                source="football-data.co.uk",
            )
        )
    return matches


def load_results(cache: HttpCache, today: date | None = None) -> list[CatalogMatch]:
    today = today or date.today()
    current = season_codes(today)[-1]
    found: list[CatalogMatch] = []
    for start in season_codes(today):
        code = f"{str(start)[2:]}{str(start + 1)[2:]}"
        ttl = CURRENT_TTL if start == current else PAST_TTL
        for league in LEAGUES:
            if not league["fd"]:
                continue
            url = f"{BASE}/{code}/{league['fd']}.csv"
            text = cache.fetch(url, ttl_seconds=ttl, headers={"User-Agent": "soccer-bet-scout"})
            if not text:
                continue
            batch = [match for match in parse_csv(text, league) if match.finished]
            print(f"  [fduk] {league['id']} {season_label(start)}: {len(batch)} played")
            found.extend(batch)
    return found
