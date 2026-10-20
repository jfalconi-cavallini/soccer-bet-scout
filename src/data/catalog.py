"""Assemble one match list from every source."""

from __future__ import annotations

from datetime import date

from src.data.cache import HttpCache
from src.data.clubelo_compare import compare
from src.data.cups import load as load_cups
from src.data.fdorg import load as load_fdorg
from src.data.fduk import load_results
from src.data.models import CatalogMatch, prefer
from src.data.odds_times import load_kickoffs
from src.data.openfootball import load as load_openfootball


def load_catalog(today: date | None = None, cache: HttpCache | None = None) -> tuple[list[CatalogMatch], HttpCache]:
    today = today or date.today()
    cache = cache or HttpCache()
    print("Loading domestic results (football-data.co.uk)...")
    rows = load_results(cache, today)
    print("Loading openfootball fixtures and extra leagues...")
    rows.extend(load_openfootball(cache, today))
    print("Loading UEFA matches (openfootball text)...")
    rows.extend(load_cups(cache, today))
    print("Loading football-data.org current season...")
    rows.extend(load_fdorg(cache, today))

    merged: dict[tuple, CatalogMatch] = {}
    for match in rows:
        if match.home == match.away:
            continue
        key = (match.day, match.home, match.away)
        if key in merged:
            merged[key] = prefer(merged[key], match)
        else:
            merged[key] = match

    kickoffs = load_kickoffs(cache)
    for match in merged.values():
        override = kickoffs.get((match.day.isoformat(), match.home, match.away))
        if override:
            match.kickoff_utc = override

    ordered = sorted(merged.values(), key=lambda match: (match.day, match.competition_id, match.home, match.away))
    played = sum(1 for match in ordered if match.finished)
    print(f"Catalog: {len(ordered)} matches, {played} played")
    return ordered, cache


def clubelo_report(cache: HttpCache, ratings: dict[str, float], today: date | None = None) -> dict:
    print("Comparing top clubs with clubelo.com...")
    return compare(cache, ratings, today)
