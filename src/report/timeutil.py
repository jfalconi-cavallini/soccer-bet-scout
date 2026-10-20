"""Kickoff clocks. Stored instants are UTC. Reports use America/Chicago."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from src.config import CENTRAL_EUROPE_TZ, CHICAGO_TZ, KICKOFF_SOURCE_TZ

CHICAGO = ZoneInfo(CHICAGO_TZ)
LONDON = ZoneInfo(KICKOFF_SOURCE_TZ)
CENTRAL_EUROPE = ZoneInfo(CENTRAL_EUROPE_TZ)


def parse_utc(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def kickoff_in_zone(day: date, hhmm: str | None, zone: ZoneInfo) -> datetime:
    """Treat a wall clock as local to `zone`, then store UTC."""
    hour, minute = 15, 0
    if hhmm and ":" in hhmm:
        parts = hhmm.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
    return local.astimezone(timezone.utc)


def london_kickoff(day: date, hhmm: str | None) -> datetime:
    """football-data.co.uk lists every league's kickoff in UK local time."""
    return kickoff_in_zone(day, hhmm, LONDON)


def central_european_kickoff(day: date, hhmm: str | None) -> datetime:
    """openfootball UEFA text uses the Central European slots (18:45 and 21:00)."""
    return kickoff_in_zone(day, hhmm, CENTRAL_EUROPE)


def format_kickoff(utc_iso: str) -> str:
    """Example: Sat, Oct 24, 2026, 2:30 PM CDT."""
    local = parse_utc(utc_iso).astimezone(CHICAGO)
    clock = local.strftime("%a, %b {day}, %Y, {hour}:%M %p %Z")
    hour = local.strftime("%I").lstrip("0") or "0"
    return clock.format(day=local.day, hour=hour)
