"""The catalog refuses women's competitions even if a file contains them."""

from datetime import date

from src.config import LEAGUES, TOURNAMENTS, is_mens_competition
from src.data.catalog import mens_only
from src.data.models import CatalogMatch


def _match(competition: str) -> CatalogMatch:
    return CatalogMatch(
        day=date(2026, 10, 1),
        home="alpha",
        away="beta",
        home_name="Alpha",
        away_name="Beta",
        home_goals=1,
        away_goals=0,
        competition_id="X",
        competition=competition,
        kind="league",
    )


def test_womens_names_are_rejected_and_configured_leagues_pass():
    assert is_mens_competition("Premier League")
    assert is_mens_competition("Champions League")
    assert not is_mens_competition("Frauen-Bundesliga")
    assert not is_mens_competition("Women's Super League")
    assert not is_mens_competition("Liga Femenina")
    assert not is_mens_competition("Dames Eredivisie")
    for league in LEAGUES:
        assert is_mens_competition(league["name"])
    for name in TOURNAMENTS.values():
        assert is_mens_competition(name)
    kept = mens_only([_match("Premier League"), _match("Frauen-Bundesliga")])
    assert [match.competition for match in kept] == ["Premier League"]
