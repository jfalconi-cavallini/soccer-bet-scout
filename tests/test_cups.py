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
