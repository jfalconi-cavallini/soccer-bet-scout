"""90-minute scores from openfootball cup text, penalties excluded."""

from src.data.cups import parse_cup_text, parse_score


def test_penalty_line_uses_ninety_minutes():
    assert parse_score("1-4 pen. 0-1 a.e.t. (0-1, 0-1)") == (0, 1)
    assert parse_score("2-1 a.e.t. (1-1, 1-1)") == (1, 1)
    assert parse_score("0-3 (0-2)") == (0, 3)
    assert parse_score("1-1") == (1, 1)


def test_cup_text_marks_only_the_final_as_neutral():
    text = """
= UEFA Champions League 2024/25

▪ League, Matchday 1
  Tue Sep 17 2024
    18:45  Arsenal FC (ENG)    v RC Lens (FRA)     2-0 (1-0)

▪ Finals, Quarterfinals
  Tue Apr 8 2025
    21:00  Arsenal FC (ENG)    v Real Madrid CF (ESP)   3-0 (0-0)

▪ Finals, Final
  Sat May 31 2025
    21:00  Paris Saint-Germain FC (FRA) v FC Internazionale Milano (ITA)  5-0 (2-0)
"""
    matches = parse_cup_text(text, "UCL", 2024)
    assert len(matches) == 3
    assert matches[0].neutral is False
    assert matches[1].neutral is False
    assert matches[2].neutral is True
    assert matches[2].home_goals == 5
    assert matches[0].home == "arsenal"
    assert matches[2].away == "inter"


def test_cancelled_cup_line_is_not_a_match():
    text = """
  Thu Mar 10 2022
           RB Leipzig (GER)        v Spartak Moskva (RUS)     [cancelled]
    18:45  Sevilla FC (ESP)        v West Ham United (ENG)    1-0 (0-0)
  Thu Mar 17 2022
           Spartak Moskva (RUS)    v RB Leipzig (GER)         [cancelled]
           Tottenham Hotspur (ENG) v Stade Rennais (FRA)      0-3    [awarded]
"""
    matches = parse_cup_text(text, "UEL", 2021)
    assert [match.home for match in matches] == ["sevilla", "tottenham"]
    assert all(match.finished for match in matches)
    assert matches[0].away_name == "West Ham United"
    assert matches[1].home_goals == 0 and matches[1].away_goals == 3
    assert "[" not in matches[1].home_name and "[" not in matches[1].away_name
    assert all(not match.finished or match.home != "rb leipzig" for match in matches)
