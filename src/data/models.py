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
        )


def prefer(existing: CatalogMatch, incoming: CatalogMatch) -> CatalogMatch:
    """Keep the richer record when two sources describe the same match."""
    if incoming.finished and not existing.finished:
        return incoming
    if existing.finished and not incoming.finished:
        # Still take a better kickoff if we only had a date.
        if incoming.kickoff_utc and not existing.kickoff_utc:
            existing.kickoff_utc = incoming.kickoff_utc
        return existing
    if incoming.xg_home is not None and existing.xg_home is None:
        return incoming
    if incoming.kickoff_utc and not existing.kickoff_utc:
        existing.kickoff_utc = incoming.kickoff_utc
    if len(incoming.home_name) > len(existing.home_name):
        existing.home_name = incoming.home_name
        existing.away_name = incoming.away_name
    return existing
