"""UEFA club matches from the openfootball champions-league text files.

The text format carries the 90-minute score, and sometimes extra time and
penalties. Elo uses the 90-minute score so a shootout is a draw.
"""

from __future__ import annotations

import re
from datetime import date

from src.config import CUP_FILES, TOURNAMENTS, season_codes, season_label
from src.data.cache import CURRENT_TTL, PAST_TTL, HttpCache
from src.data.models import CatalogMatch
from src.names import canonicalize
from src.report.timeutil import london_kickoff

BASE = "https://raw.githubusercontent.com/openfootball/champions-league/master"
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
_DATE = re.compile(
    r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$"
)
_SCORE = re.compile(r"(\d+)\s*-\s*(\d+)")


def parse_score(blob: str) -> tuple[int, int] | None:
    """90-minute score, ignoring penalty shootouts.

    `1-4 pen. 0-1 a.e.t. (0-1, 0-1)` -> (0, 1)
    `2-1 a.e.t. (1-1, 1-1)` -> (1, 1)
    `0-3 (0-2)` -> (0, 3)
    """
    text = blob.strip()
    if not text or text.lower().startswith("postponed") or "v" in text.lower() and "awarded" in text.lower():
        return None
    paren = re.search(r"\(([^)]*)\)", text)
    if paren and "," in paren.group(1):
        full_time = paren.group(1).split(",")[-1]
        found = _SCORE.search(full_time)
        if found:
            return int(found.group(1)), int(found.group(2))
    without_pen = re.sub(r"\d+\s*-\s*\d+\s+pen\.\s*", "", text)
    without_extra = re.sub(r"\d+\s*-\s*\d+\s+a\.e\.t\.\s*", "", without_pen)
    found = _SCORE.search(without_extra)
    if found:
        return int(found.group(1)), int(found.group(2))
    return None


def parse_cup_text(text: str, tournament_id: str, season_start: int) -> list[CatalogMatch]:
    current: date | None = None
    year_hint = season_start
    neutral = False
    matches: list[CatalogMatch] = []
    name = TOURNAMENTS[tournament_id]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("="):
            continue
        if line.startswith("▪") or line.startswith("»"):
            stage = line.lstrip("▪» ").strip()
            # "Finals, Final" is the one-off neutral final. Quarterfinals are not.
            neutral = bool(re.search(r"(^|,\s*)Final$", stage))
            continue
        date_match = _DATE.match(line)
        if date_match and " v " not in line:
            month = _MONTHS[date_match.group(1)]
            day_num = int(date_match.group(2))
            explicit = date_match.group(3)
            if explicit:
                year = int(explicit)
            else:
                year = year_hint
                if current and month + 6 < current.month:
                    year = current.year + 1
                elif current:
                    year = current.year
            try:
                current = date(year, month, day_num)
            except ValueError:
                continue
            year_hint = current.year
            continue
        if " v " not in line or current is None:
            continue
        left, right = line.split(" v ", 1)
        time_match = re.match(r"(\d{1,2}:\d{2})\s+(.*)", left)
        if time_match:
            kick_hm = time_match.group(1)
            home_raw = time_match.group(2).strip()
        else:
            kick_hm = None
            home_raw = left.strip()
        score_match = re.search(r"\s(\d+\s*-\s*\d+.*)$", right)
        if score_match:
            away_raw = right[: score_match.start()].strip()
            parsed = parse_score(score_match.group(1))
        else:
            away_raw = right.strip()
            parsed = None
        home = canonicalize(home_raw)
        away = canonicalize(away_raw)
        if not home or not away or home == away:
            continue
        home_goals = away_goals = None
        if parsed:
            home_goals, away_goals = parsed
        matches.append(
            CatalogMatch(
                day=current,
                home=home,
                away=away,
                home_name=re.sub(r"\s*\([A-Z]{3}\)\s*", " ", home_raw).strip(),
                away_name=re.sub(r"\s*\([A-Z]{3}\)\s*", " ", away_raw).strip(),
                home_goals=home_goals,
                away_goals=away_goals,
                competition_id=tournament_id,
                competition=name,
                kind="cup",
                neutral=neutral,
                kickoff_utc=london_kickoff(current, kick_hm).isoformat(),
                source="openfootball-cup",
            )
        )
    return matches


def load(cache: HttpCache, today: date | None = None) -> list[CatalogMatch]:
    today = today or date.today()
    current = season_codes(today)[-1]
    found: list[CatalogMatch] = []
    for start in season_codes(today):
        folder = season_label(start)
        ttl = CURRENT_TTL if start == current else PAST_TTL
        for filename, tournament_id in CUP_FILES.items():
            url = f"{BASE}/{folder}/{filename}"
            text = cache.fetch(url, ttl_seconds=ttl, headers={"User-Agent": "soccer-bet-scout"})
            if not text:
                continue
            batch = parse_cup_text(text, tournament_id, start)
            played = sum(1 for match in batch if match.finished)
            print(f"  [cups] {tournament_id} {folder} {filename}: {played} played / {len(batch)} rows")
            found.extend(batch)
    return found
