"""Compare our top clubs with clubelo.com.

Scales differ (we seed 2021 at 1500; ClubElo has a longer history), so the
check is rank order among clubs we can name-match, not the raw number.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from src.data.cache import CURRENT_TTL, HttpCache
from src.names import canonicalize

try:
    from thefuzz import fuzz
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    fuzz = None


def _spearman(left: list[float], right: list[float]) -> float | None:
    n = len(left)
    if n < 5:
        return None

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda index: values[index], reverse=True)
        out = [0.0] * n
        for rank, index in enumerate(order, start=1):
            out[index] = float(rank)
        return out

    ra, rb = ranks(left), ranks(right)
    mean_a = sum(ra) / n
    mean_b = sum(rb) / n
    num = sum((a - mean_a) * (b - mean_b) for a, b in zip(ra, rb))
    den_a = sum((a - mean_a) ** 2 for a in ra) ** 0.5
    den_b = sum((b - mean_b) ** 2 for b in rb) ** 0.5
    if den_a == 0 or den_b == 0:
        return None
    return num / (den_a * den_b)


def _match_name(club: str, ours: dict[str, float]) -> str | None:
    key = canonicalize(club)
    if key in ours:
        return key
    if fuzz is None or not key:
        return None
    best = None
    best_score = 0
    for candidate in ours:
        score = fuzz.token_set_ratio(key, candidate)
        if score > best_score:
            best_score = score
            best = candidate
    if best is not None and best_score >= 92:
        return best
    return None


def compare(cache: HttpCache, ratings: dict[str, float], today: date | None = None) -> dict:
    today = today or date.today()
    url = f"http://api.clubelo.com/{today.isoformat()}"
    text = cache.fetch(
        url,
        ttl_seconds=CURRENT_TTL,
        headers={"User-Agent": "Mozilla/5.0 soccer-bet-scout"},
        polite_gap=0,
    )
    if not text or "Club" not in text.splitlines()[0]:
        return {
            "available": False,
            "reason": "clubelo.com did not return a rating table on this run",
            "url": url,
        }
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        club = row.get("Club") or row.get("club")
        elo = row.get("Elo") or row.get("elo")
        level = row.get("Level") or row.get("level") or "1"
        country = row.get("Country") or row.get("country") or ""
        if not club or not elo:
            continue
        try:
            elo_value = float(elo)
            level_value = int(float(level))
        except ValueError:
            continue
        if level_value != 1:
            continue
        rows.append({"club": club, "elo": elo_value, "country": country})
    rows.sort(key=lambda item: item["elo"], reverse=True)

    paired = []
    for row in rows:
        key = _match_name(row["club"], ratings)
        if key is None:
            continue
        paired.append(
            {
                "club": row["club"],
                "clubelo": round(row["elo"], 1),
                "ours": round(ratings[key], 1),
                "country": row["country"],
            }
        )
        if len(paired) >= 25:
            break

    coefficient = _spearman(
        [item["ours"] for item in paired],
        [item["clubelo"] for item in paired],
    )
    return {
        "available": True,
        "url": url,
        "matched": len(paired),
        "spearman": None if coefficient is None else round(coefficient, 3),
        "note": (
            "Spearman is the rank correlation between our rating and ClubElo "
            "on the matched top-division clubs. Absolute points are not comparable."
        ),
        "top": paired[:15],
    }
