"""Optional kickoff times from The Odds API.

The scout does not price bets. If ODDS_API_KEY is set, the daily build
reads commence_time so Chicago clocks line up with the bookmaker feed.
Responses are cached. Odds themselves are not stored.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from src.config import ODDS_SPORTS
from src.data.cache import CURRENT_TTL, HttpCache
from src.names import canonicalize

BASE = "https://api.the-odds-api.com/v4"


def load_kickoffs(cache: HttpCache) -> dict[tuple[str, str, str], str]:
    """Map (date, home, away) -> UTC ISO kickoff."""
    key = os.getenv("ODDS_API_KEY")
    if not key:
        print("  [odds] ODDS_API_KEY not set, using source kickoff times")
        return {}
    found: dict[tuple[str, str, str], str] = {}
    for sport in ODDS_SPORTS:
        text = cache.fetch(
            f"{BASE}/sports/{sport}/odds",
            ttl_seconds=CURRENT_TTL,
            params={
                "apiKey": key,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal",
            },
            polite_gap=0.5,
        )
        if not text:
            continue
        try:
            events = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(events, list):
            continue
        for event in events:
            commence = event.get("commence_time")
            home = canonicalize(event.get("home_team"))
            away = canonicalize(event.get("away_team"))
            if not commence or not home or not away:
                continue
            try:
                kick = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            except ValueError:
                continue
            if kick.tzinfo is None:
                kick = kick.replace(tzinfo=timezone.utc)
            day = kick.astimezone(timezone.utc).date().isoformat()
            found[(day, home, away)] = kick.astimezone(timezone.utc).isoformat()
        print(f"  [odds] {sport}: {len(events)} events (times only)")
    return found
