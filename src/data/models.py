"""One match shape shared by the loaders, the Elo replay, and the slate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.model.elo import EloMatch
from src.names import slugify


@dataclass
class CatalogMatch:
    day: date
    home: str
    away: str
    home_name: str
    away_name: str
    home_goals: int | None
    away_goals: int | None
    competition_id: str
    competition: str
    kind: str
    neutral: bool = False
    xg_home: float | None = None
    xg_away: float | None = None
    kickoff_utc: str | None = None
    source: str = ""
    ht_home: int | None = None
    ht_away: int | None = None
    close_home: float | None = None
    close_draw: float | None = None
    close_away: float | None = None
    close_book: str = ""

    @property
    def finished(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def id(self) -> str:
        return f"{self.day.isoformat()}-{slugify(self.home)}-{slugify(self.away)}"

    def to_elo(self) -> EloMatch:
        if not self.finished:
            raise ValueError("unfinished match cannot update Elo")
        return EloMatch(
            day=self.day,
            home=self.home,
            away=self.away,
            home_goals=int(self.home_goals),
            away_goals=int(self.away_goals),
            competition_id=self.competition_id,
            kind=self.kind,
            neutral=self.neutral,
            xg_home=self.xg_home,
            xg_away=self.xg_away,
            ht_home=self.ht_home,
            ht_away=self.ht_away,
        )


def _adopt_kickoff(existing: CatalogMatch, incoming: CatalogMatch) -> None:
    """football-data.org sends a real UTC instant. Other files send a local clock."""
    if not incoming.kickoff_utc:
        return
    if not existing.kickoff_utc or incoming.source == "football-data.org":
        existing.kickoff_utc = incoming.kickoff_utc


def _adopt_halves(kept: CatalogMatch, other: CatalogMatch) -> None:
    """Half-time scores are optional. Keep them from whichever source has them."""
    if kept.ht_home is None and other.ht_home is not None and other.ht_away is not None:
        kept.ht_home = other.ht_home
        kept.ht_away = other.ht_away


def _adopt_close(kept: CatalogMatch, other: CatalogMatch) -> None:
    """Closing prices are optional. Keep them from whichever file has them."""
    if kept.close_home is None and other.close_home is not None:
        kept.close_home = other.close_home
        kept.close_draw = other.close_draw
        kept.close_away = other.close_away
        kept.close_book = other.close_book


def prefer(existing: CatalogMatch, incoming: CatalogMatch) -> CatalogMatch:
    """Keep the richer record when two sources describe the same match."""
    if incoming.finished and not existing.finished:
        _adopt_halves(incoming, existing)
        _adopt_close(incoming, existing)
        return incoming
    if existing.finished and not incoming.finished:
        _adopt_kickoff(existing, incoming)
        _adopt_halves(existing, incoming)
        _adopt_close(existing, incoming)
        return existing
    if incoming.xg_home is not None and existing.xg_home is None:
        _adopt_halves(incoming, existing)
        _adopt_close(incoming, existing)
        _adopt_kickoff(incoming, existing)
        return incoming
    _adopt_kickoff(existing, incoming)
    _adopt_halves(existing, incoming)
    _adopt_close(existing, incoming)
    if len(incoming.home_name) > len(existing.home_name):
        existing.home_name = incoming.home_name
        existing.away_name = incoming.away_name
    return existing
