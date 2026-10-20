"""Binary markets priced from a score grid, ranked by model probability.

These are model probabilities, not bookmaker prices. An integer handicap
that lands on a push is not counted as a win.
"""

from __future__ import annotations

FT_LINES = (0.5, 1.5, 2.5, 3.5, 4.5)
TEAM_LINES = FT_LINES
DC_LINES = (1.5, 2.5, 3.5)
# Handicap applied to that side. Half-lines never push; integer lines do.
AH_LINES = (-1.5, -1.0, 1.0, 1.5)
MOST_LIKELY_LIMIT = 8


def _tag(line: float) -> str:
    return f"{line:.1f}"


def _signed(line: float) -> str:
    if float(line).is_integer():
        return f"{int(line):+d}"
    return f"{line:+.1f}"


def _walk(grid):
    for home_goals, row in enumerate(grid):
        for away_goals, prob in enumerate(row):
            if prob:
                yield home_goals, away_goals, prob


def price_full(grid: list[list[float]]) -> dict[str, float]:
    """Full-time BTTS, totals, double chance, handicaps, and the listed combos."""
    acc: dict[str, float] = {}

    def add(key: str, prob: float, when: bool) -> None:
        acc[key] = acc.get(key, 0.0) + (prob if when else 0.0)

    for line in FT_LINES:
        tag = _tag(line)
        acc[f"over_{tag}"] = 0.0
        acc[f"under_{tag}"] = 0.0
    for line in TEAM_LINES:
        tag = _tag(line)
        for side in ("home", "away"):
            acc[f"{side}_over_{tag}"] = 0.0
            acc[f"{side}_under_{tag}"] = 0.0
    for side in ("home", "away"):
        for line in AH_LINES:
            acc[f"ah_{side}_{_signed(line)}"] = 0.0
    for result in ("home_win", "draw", "away_win"):
        acc[f"{result}_btts"] = 0.0
        acc[f"{result}_btts_no"] = 0.0
        acc[f"{result}_over_2.5"] = 0.0
        acc[f"{result}_under_2.5"] = 0.0
    for flag in ("btts_over_2.5", "btts_under_2.5", "btts_no_over_2.5", "btts_no_under_2.5"):
        acc[flag] = 0.0
    for name in ("1x", "x2", "12"):
        acc[f"dc_{name}"] = 0.0
        for line in DC_LINES:
            tag = _tag(line)
            acc[f"dc_{name}_over_{tag}"] = 0.0
            acc[f"dc_{name}_under_{tag}"] = 0.0
    acc["btts"] = 0.0
    acc["btts_no"] = 0.0

    for home_goals, away_goals, prob in _walk(grid):
        total = home_goals + away_goals
        margin = home_goals - away_goals
        both = home_goals > 0 and away_goals > 0
        if home_goals > away_goals:
            result = "home_win"
        elif home_goals == away_goals:
            result = "draw"
        else:
            result = "away_win"
        add("btts", prob, both)
        add("btts_no", prob, not both)
        for line in FT_LINES:
            tag = _tag(line)
            add(f"over_{tag}", prob, total > line)
            add(f"under_{tag}", prob, total < line)
        for line in TEAM_LINES:
            tag = _tag(line)
            add(f"home_over_{tag}", prob, home_goals > line)
            add(f"home_under_{tag}", prob, home_goals < line)
            add(f"away_over_{tag}", prob, away_goals > line)
            add(f"away_under_{tag}", prob, away_goals < line)
        add("dc_1x", prob, home_goals >= away_goals)
        add("dc_x2", prob, away_goals >= home_goals)
        add("dc_12", prob, home_goals != away_goals)
        for side, side_margin in (("home", margin), ("away", -margin)):
            for line in AH_LINES:
                # A push (adjusted margin of exactly 0) is not a win.
                add(f"ah_{side}_{_signed(line)}", prob, side_margin + line > 0)
        add(f"{result}_btts", prob, both)
        add(f"{result}_btts_no", prob, not both)
        add(f"{result}_over_2.5", prob, total > 2.5)
        add(f"{result}_under_2.5", prob, total < 2.5)
        add("btts_over_2.5", prob, both and total > 2.5)
        add("btts_under_2.5", prob, both and total < 2.5)
        add("btts_no_over_2.5", prob, (not both) and total > 2.5)
        add("btts_no_under_2.5", prob, (not both) and total < 2.5)
        for name, covered in (
            ("1x", home_goals >= away_goals),
            ("x2", away_goals >= home_goals),
            ("12", home_goals != away_goals),
        ):
            for line in DC_LINES:
                tag = _tag(line)
                add(f"dc_{name}_over_{tag}", prob, covered and total > line)
                add(f"dc_{name}_under_{tag}", prob, covered and total < line)
    return acc


def price_half(grid: list[list[float]], prefix: str) -> dict[str, float]:
    """The cheap half set: result, BTTS, 0.5/1.5, and each side over 0.5."""
    keys = [
        "btts",
        "btts_no",
        "over_0.5",
        "under_0.5",
        "over_1.5",
        "under_1.5",
        "home",
        "draw",
        "away",
        "home_over_0.5",
        "away_over_0.5",
    ]
    acc = {f"{prefix}_{key}": 0.0 for key in keys}
    for home_goals, away_goals, prob in _walk(grid):
        total = home_goals + away_goals
        both = home_goals > 0 and away_goals > 0
        acc[f"{prefix}_btts"] += prob if both else 0.0
        acc[f"{prefix}_btts_no"] += 0.0 if both else prob
        for line in (0.5, 1.5):
            tag = _tag(line)
            if total > line:
                acc[f"{prefix}_over_{tag}"] += prob
            else:
                acc[f"{prefix}_under_{tag}"] += prob
        if home_goals > away_goals:
            acc[f"{prefix}_home"] += prob
        elif home_goals == away_goals:
            acc[f"{prefix}_draw"] += prob
        else:
            acc[f"{prefix}_away"] += prob
        if home_goals > 0.5:
            acc[f"{prefix}_home_over_0.5"] += prob
        if away_goals > 0.5:
            acc[f"{prefix}_away_over_0.5"] += prob
    return acc


def build_markets(
    full_grid: list[list[float]],
    first_grid: list[list[float]],
    second_grid: list[list[float]],
) -> dict[str, float]:
    raw: dict[str, float] = {}
    raw.update(price_full(full_grid))
    raw.update(price_half(first_grid, "1h"))
    raw.update(price_half(second_grid, "2h"))
    return {key: round(min(1.0, max(0.0, value)), 4) for key, value in raw.items()}


def market_label(key: str, home: str, away: str) -> str:
    period = ""
    bare = key
    if key.startswith("1h_"):
        period, bare = "1H ", key[3:]
    elif key.startswith("2h_"):
        period, bare = "2H ", key[3:]

    simple = {
        "btts": "Both teams to score",
        "btts_no": "Not both teams to score",
        "home": f"{home} win",
        "draw": "Draw",
        "away": f"{away} win",
        "dc_1x": f"{home} or draw",
        "dc_x2": f"{away} or draw",
        "dc_12": f"{home} or {away}",
        "btts_over_2.5": "Both teams to score and over 2.5",
        "btts_under_2.5": "Both teams to score and under 2.5",
        "btts_no_over_2.5": "Not both teams to score and over 2.5",
        "btts_no_under_2.5": "Not both teams to score and under 2.5",
    }
    if bare in simple:
        return period + simple[bare]
    if bare.startswith("over_"):
        return f"{period}Over {bare.removeprefix('over_')}"
    if bare.startswith("under_"):
        return f"{period}Under {bare.removeprefix('under_')}"
    if bare.startswith("ah_"):
        side, line = bare[3:].split("_", 1)
        name = home if side == "home" else away
        return f"{period}{name} {line}"
    for side, name in (("home", home), ("away", away)):
        for kind in ("over", "under"):
            prefix = f"{side}_{kind}_"
            if bare.startswith(prefix):
                return f"{period}{name} {kind} {bare[len(prefix):]}"
    result_names = (
        ("home_win", f"{home} win"),
        ("away_win", f"{away} win"),
        ("draw", "Draw"),
    )
    for result, label in result_names:
        if bare == f"{result}_btts":
            return f"{period}{label} and both teams to score"
        if bare == f"{result}_btts_no":
            return f"{period}{label} and not both teams to score"
        if bare.startswith(f"{result}_over_"):
            return f"{period}{label} and over {bare.split('_over_', 1)[1]}"
        if bare.startswith(f"{result}_under_"):
            return f"{period}{label} and under {bare.split('_under_', 1)[1]}"
    if bare.startswith("dc_"):
        parts = bare.split("_")
        if len(parts) == 4:
            cover = {
                "1x": f"{home} or draw",
                "x2": f"{away} or draw",
                "12": f"{home} or {away}",
            }[parts[1]]
            return f"{period}{cover} and {parts[2]} {parts[3]}"
    return period + bare.replace("_", " ")


def rank_markets(markets: dict[str, float], home: str, away: str, limit: int = MOST_LIKELY_LIMIT) -> list[dict]:
    ordered = sorted(markets.items(), key=lambda item: (-item[1], item[0]))
    return [
        {
            "key": key,
            "label": market_label(key, home, away),
            "pct": round(prob * 100.0, 1),
        }
        for key, prob in ordered[:limit]
    ]


def _split_period(key: str, home_goals: int, away_goals: int, ht_home: int | None, ht_away: int | None):
    if key.startswith("1h_"):
        if ht_home is None or ht_away is None:
            return None
        return key[3:], int(ht_home), int(ht_away)
    if key.startswith("2h_"):
        if ht_home is None or ht_away is None:
            return None
        if home_goals < ht_home or away_goals < ht_away:
            return None
        return key[3:], home_goals - ht_home, away_goals - ht_away
    return key, home_goals, away_goals


def _line_of(prefix: str, bare: str) -> float | None:
    if not bare.startswith(prefix):
        return None
    try:
        return float(bare[len(prefix):])
    except ValueError:
        return None


def market_hit(
    key: str,
    home_goals: int,
    away_goals: int,
    ht_home: int | None = None,
    ht_away: int | None = None,
) -> float | None:
    """1 if the score wins the market, 0 if it loses, None if it cannot be scored.

    Integer handicaps return None on a push. Half markets return None when
    the half-time score is missing or exceeds the full-time score.
    """
    parsed = _split_period(key, home_goals, away_goals, ht_home, ht_away)
    if parsed is None:
        return None
    bare, home, away = parsed
    total = home + away
    margin = home - away
    both = home > 0 and away > 0

    if bare == "btts":
        return 1.0 if both else 0.0
    if bare == "btts_no":
        return 0.0 if both else 1.0
    if bare == "home":
        return 1.0 if home > away else 0.0
    if bare == "draw":
        return 1.0 if home == away else 0.0
    if bare == "away":
        return 1.0 if home < away else 0.0
    if bare == "dc_1x":
        return 1.0 if home >= away else 0.0
    if bare == "dc_x2":
        return 1.0 if away >= home else 0.0
    if bare == "dc_12":
        return 1.0 if home != away else 0.0

    over_line = _line_of("over_", bare)
    if over_line is not None:
        return 1.0 if total > over_line else 0.0
    under_line = _line_of("under_", bare)
    if under_line is not None:
        return 1.0 if total < under_line else 0.0

    if bare.startswith("ah_"):
        side, line_text = bare[3:].split("_", 1)
        line = float(line_text)
        side_margin = margin if side == "home" else -margin
        adjusted = side_margin + line
        if abs(adjusted) < 1e-9:
            return None
        return 1.0 if adjusted > 0 else 0.0

    for side, goals in (("home", home), ("away", away)):
        over_side = _line_of(f"{side}_over_", bare)
        if over_side is not None:
            return 1.0 if goals > over_side else 0.0
        under_side = _line_of(f"{side}_under_", bare)
        if under_side is not None:
            return 1.0 if goals < under_side else 0.0

    if bare in ("btts_over_2.5", "btts_under_2.5", "btts_no_over_2.5", "btts_no_under_2.5"):
        want_both = bare.startswith("btts_over") or bare.startswith("btts_under")
        want_over = "over" in bare
        scored_both = both if want_both else not both
        scored_total = total > 2.5 if want_over else total < 2.5
        return 1.0 if scored_both and scored_total else 0.0

    for result, happened in (
        ("home_win", home > away),
        ("draw", home == away),
        ("away_win", home < away),
    ):
        if bare == f"{result}_btts":
            return 1.0 if happened and both else 0.0
        if bare == f"{result}_btts_no":
            return 1.0 if happened and not both else 0.0
        over_combo = _line_of(f"{result}_over_", bare)
        if over_combo is not None:
            return 1.0 if happened and total > over_combo else 0.0
        under_combo = _line_of(f"{result}_under_", bare)
        if under_combo is not None:
            return 1.0 if happened and total < under_combo else 0.0

    if bare.startswith("dc_"):
        parts = bare.split("_")
        if len(parts) == 4:
            covered = {
                "1x": home >= away,
                "x2": away >= home,
                "12": home != away,
            }[parts[1]]
            line = float(parts[3])
            total_ok = total > line if parts[2] == "over" else total < line
            return 1.0 if covered and total_ok else 0.0
    return None
