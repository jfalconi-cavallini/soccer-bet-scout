"""Kickoff clocks. Stored instants are UTC. Reports use America/Chicago."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from src.config import CHICAGO_TZ, KICKOFF_SOURCE_TZ

CHICAGO = ZoneInfo(CHICAGO_TZ)
LONDON = ZoneInfo(KICKOFF_SOURCE_TZ)


def parse_utc(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def london_kickoff(day: date, hhmm: str | None) -> datetime:
    """football-data.co.uk and openfootball list kickoffs in UK local time."""
    hour, minute = 15, 0
    if hhmm and ":" in hhmm:
        parts = hhmm.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=LONDON)
    return local.astimezone(timezone.utc)


def format_kickoff(utc_iso: str) -> str:
    """Example: Sat, Oct 24, 2026, 2:30 PM CDT."""
    local = parse_utc(utc_iso).astimezone(CHICAGO)
    clock = local.strftime("%a, %b {day}, %Y, {hour}:%M %p %Z")
    hour = local.strftime("%I").lstrip("0") or "0"
    return clock.format(day=local.day, hour=hour)
