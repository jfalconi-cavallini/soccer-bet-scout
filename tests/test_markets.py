"""Market prices from a score grid, including pushes and the ranked panel."""

from src.model.markets import build_markets, market_hit, market_label, price_full, rank_markets


def _certain(home: int, away: int) -> list[list[float]]:
    grid = [[0.0 for _ in range(max(home, away) + 1)] for _ in range(max(home, away) + 1)]
    grid[home][away] = 1.0
    return grid


def test_integer_handicap_push_is_not_a_win():
    priced = price_full(_certain(1, 0))
    assert priced["ah_home_-1.5"] == 0
    assert priced["ah_home_-1"] == 0
    assert priced["ah_home_+1"] == 1
    assert priced["ah_home_+1.5"] == 1
    assert priced["ah_away_-1.5"] == 0
    assert market_hit("ah_home_-1", 1, 0) is None
    assert market_hit("ah_home_-1.5", 1, 0) == 0
    assert market_hit("ah_home_+1", 1, 0) == 1
    assert market_hit("ah_home_+1", 0, 1) is None
    assert market_hit("ah_home_-1", 2, 0) == 1
    assert market_hit("ah_away_-1.5", 0, 2) == 1
    assert market_hit("ah_away_+1.5", 2, 0) == 0


def test_combos_and_half_scores_follow_the_grid():
    priced = price_full(_certain(2, 1))
    assert priced["btts"] == 1
    assert priced["over_2.5"] == 1
    assert priced["home_win_btts"] == 1
    assert priced["home_win_over_2.5"] == 1
    assert priced["btts_over_2.5"] == 1
    assert priced["draw_btts"] == 0
    assert priced["dc_1x_over_2.5"] == 1
    assert priced["dc_x2_over_2.5"] == 0
    assert priced["home_over_0.5"] == 1
    assert priced["away_under_1.5"] == 1
    assert market_hit("home_win_btts", 2, 1) == 1
    assert market_hit("btts_no_under_2.5", 2, 0) == 1
    assert market_hit("1h_btts", 2, 1) is None
    assert market_hit("1h_over_0.5", 2, 1, ht_home=1, ht_away=0) == 1
    assert market_hit("1h_btts", 2, 1, 1, 0) == 0
    assert market_hit("2h_btts", 2, 1, 1, 0) == 1
    assert market_hit("2h_over_0.5", 2, 0, 1, 0) == 1
    assert market_hit("2h_home", 3, 1, 1, 1) == 1
    assert market_hit("2h_over_0.5", 1, 0, 2, 0) is None


def test_most_likely_ranks_by_model_probability():
    ranked = rank_markets(
        {"under_4.5": 0.91, "btts": 0.55, "over_4.5": 0.09},
        "Alpha",
        "Beta",
        limit=2,
    )
    assert [item["key"] for item in ranked] == ["under_4.5", "btts"]
    assert ranked[0]["pct"] == 91.0
    assert ranked[0]["label"] == "Under 4.5"
    assert market_label("ah_home_-1.5", "Alpha", "Beta") == "Alpha -1.5"
    assert market_label("dc_1x_under_2.5", "Alpha", "Beta") == "Alpha or draw and under 2.5"
    assert market_label("1h_home_over_0.5", "Alpha", "Beta") == "1H Alpha over 0.5"
    markets = build_markets(_certain(1, 0), _certain(1, 0), _certain(0, 0))
    top = rank_markets(markets, "Alpha", "Beta")
    assert top[0]["pct"] >= top[-1]["pct"]
    assert len(top) == 8
