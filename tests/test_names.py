"""Club spellings that must collapse before Elo and the goal model see them."""

from src.names import canonicalize, clean_display_name, has_void_tag


def test_bookmaker_and_openfootball_spellings_match():
    groups = [
        ("atletico madrid", ["Ath Madrid", "Club Atlético de Madrid", "Atlético Madrid"]),
        ("espanyol", ["Espanol", "RCD Espanyol de Barcelona"]),
        ("real sociedad", ["Sociedad", "Real Sociedad de Fútbol"]),
        ("frankfurt", ["Ein Frankfurt", "Eintracht Frankfurt"]),
        ("braga", ["Sp Braga", "Sporting Clube de Braga", "SC Braga"]),
        ("union sg", ["St. Gilloise", "Royale Union Saint-Gilloise"]),
        ("aek athens", ["AEK", "AEK Athen"]),
        ("aek larnaca", ["AEK Larnaca"]),
        ("dortmund", ["Dortmund", "Borussia Dortmund"]),
        ("inter", ["FC Internazionale Milano"]),
        ("inter descaldes", ["Inter Club d'Escaldes"]),
        ("brondby", ["Brøndby IF"]),
        ("kasimpasa", ["Kasımpaşa SK", "Kasimpasa"]),
        ("deportivo", ["La Coruna", "RC Deportivo La Coruña"]),
        ("rennes", ["Stade Rennais", "Stade Rennais FC 1901"]),
        ("sint truiden", ["St Truiden", "Sint-Truidense VV"]),
        ("ofi crete", ["OFI Crete", "OFI Heraklion"]),
        ("olympiacos", ["Olympiakos Piraeus", "PAE Olympiakos SFP"]),
        ("pafos", ["Pafos FC", "Paphos FC"]),
        ("ferencvaros", ["Ferencvárosi TC", "Ferencvaros"]),
        ("basel", ["FC Basel 1893", "FC Basel"]),
    ]
    for expected, spellings in groups:
        for spelling in spellings:
            assert canonicalize(spelling) == expected, spelling


def test_cancelled_tag_does_not_split_a_club():
    assert canonicalize("RB Leipzig [cancelled]") == canonicalize("RB Leipzig")
    assert clean_display_name("RB Leipzig [cancelled]") == "RB Leipzig"
    assert clean_display_name("Spartak Moskva (RUS) [cancelled]") == "Spartak Moskva"
    assert clean_display_name("Puskás FC [awarded]") == "Puskás FC"
    assert has_void_tag("RB Leipzig [cancelled]")
    assert has_void_tag("Match [Abandoned]")
    assert not has_void_tag("RB Leipzig")
    assert not has_void_tag("0-3 [awarded]")
