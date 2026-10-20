"""Walk-forward check of the match model.

Each scored match is forecast from Elo and attack/defense fitted only on
earlier dates. The match itself, later matches, and other matches on the
same calendar day are not in that fit. Season rosters are the clubs who
appear in that season's file; results still enter only after they are played.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone

from src.config import DIXON_COLES_RHO, ELO_INITIAL, LEAGUES, season_label, season_start_year
from src.model.dixon_coles import score_grid, summarize
from src.model.elo import EloMatch, replay
from src.model.halves import fit_half_shares, scoring_share
from src.model.markets import build_markets, market_hit, market_label
from src.model.ratings import build_strengths
from src.track.settlement import brier

# First day of 2024-25. The replay still starts in 2021 so the ratings exist.
BACKTEST_FROM = date(2024, 7, 1)
BIN_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.01)
# Markets beyond the 1X2. Integer handicaps skip pushes via market_hit.
SCORED_MARKETS = (
    "over_2.5",
    "btts",
    "1h_home",
    "1h_draw",
    "1h_away",
    "1h_btts",
    "1h_over_0.5",
    "1h_over_1.5",
    "home_win_btts",
    "home_win_over_2.5",
    "btts_over_2.5",
    "dc_1x",
    "dc_1x_over_2.5",
    "ah_home_-1.5",
    "ah_home_-1",
)
LEAGUE_IDS = {league["id"] for league in LEAGUES}
LEAGUE_NAME = {league["id"]: league["name"] for league in LEAGUES}
# A gap this large, on a big sample, is the miscalibration note.
CALIBRATION_GAP = 0.03
CALIBRATION_MIN = 200


def devig(home: float, draw: float, away: float) -> tuple[float, float, float]:
    """Turn decimal prices into probabilities by stripping the overround."""
    inverse = (1.0 / home, 1.0 / draw, 1.0 / away)
    total = sum(inverse)
    return inverse[0] / total, inverse[1] / total, inverse[2] / total


def outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals == away_goals:
        return "draw"
    return "away"


def top_pick(p_home: float, p_draw: float, p_away: float) -> str:
    """Home wins an exact tie, then draw, then away."""
    if p_home >= p_draw and p_home >= p_away:
        return "home"
    if p_draw >= p_away:
        return "draw"
    return "away"


def log_loss(p_home: float, p_draw: float, p_away: float, home_goals: int, away_goals: int) -> float:
    chosen = {"home": p_home, "draw": p_draw, "away": p_away}[outcome(home_goals, away_goals)]
    return -math.log(max(chosen, 1e-15))


def ranked_probability_score(
    p_home: float, p_draw: float, p_away: float, home_goals: int, away_goals: int
) -> float:
    """Normalized RPS on the ordered outcomes home, draw, away. Lower is better."""
    if home_goals > away_goals:
        observed = (1.0, 1.0)
    elif home_goals == away_goals:
        observed = (0.0, 1.0)
    else:
        observed = (0.0, 0.0)
    cumulative = (p_home, p_home + p_draw)
    return 0.5 * sum((predicted - target) ** 2 for predicted, target in zip(cumulative, observed))


def _empty_counts() -> dict[str, int]:
    return {"home": 0, "draw": 0, "away": 0}


def _baseline(snapshot: dict[str, dict[str, int]], league: str) -> tuple[float, float, float]:
    """League result rates before this date, with one pseudo-count each."""
    counts = snapshot.get(league) or _empty_counts()
    home = counts["home"] + 1
    draw = counts["draw"] + 1
    away = counts["away"] + 1
    total = home + draw + away
    return home / total, draw / total, away / total


def _predict_row(
    match: EloMatch,
    elo: dict[str, float],
    book,
    half_book,
    rate_snapshot: dict[str, dict[str, int]],
    odds: tuple[float, float, float, str] | None,
) -> dict:
    elo_home = elo.get(match.home, ELO_INITIAL)
    elo_away = elo.get(match.away, ELO_INITIAL)
    lambdas = book.lambdas(
        match.home,
        match.away,
        elo_home,
        elo_away,
        match.competition_id,
        match.kind,
        match.neutral,
    )
    grid = score_grid(lambdas["lambda_home"], lambdas["lambda_away"], DIXON_COLES_RHO)
    summary = summarize(grid)
    share_home = scoring_share(half_book, match.home, match.competition_id)
    share_away = scoring_share(half_book, match.away, match.competition_id)
    first = score_grid(
        lambdas["lambda_home"] * share_home,
        lambdas["lambda_away"] * share_away,
        DIXON_COLES_RHO,
    )
    second = score_grid(
        lambdas["lambda_home"] * (1.0 - share_home),
        lambdas["lambda_away"] * (1.0 - share_away),
        DIXON_COLES_RHO,
    )
    priced = build_markets(grid, first, second)
    base_home, base_draw, base_away = _baseline(rate_snapshot, match.competition_id)
    book_probs = None
    book_name = None
    if odds is not None:
        book_probs = devig(odds[0], odds[1], odds[2])
        book_name = odds[3]
    hits = {}
    kept = {}
    for key in SCORED_MARKETS:
        if key not in priced:
            continue
        hit = market_hit(key, match.home_goals, match.away_goals, match.ht_home, match.ht_away)
        if hit is None and key.startswith("ah_"):
            # The stored price is the chance the handicap wins. A push is not a win.
            hit = 0.0
        elif hit is None:
            continue
        kept[key] = priced[key]
        hits[key] = hit
    return {
        "day": match.day.isoformat(),
        "season": season_label(season_start_year(match.day)),
        "competition_id": match.competition_id,
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "p_home": summary["home_win"],
        "p_draw": summary["draw"],
        "p_away": summary["away_win"],
        "base_home": base_home,
        "base_draw": base_draw,
        "base_away": base_away,
        "book_home": None if book_probs is None else book_probs[0],
        "book_draw": None if book_probs is None else book_probs[1],
        "book_away": None if book_probs is None else book_probs[2],
        "book": book_name,
        "markets": kept,
        "hits": hits,
    }


def forecast_matches(
    matches: list[EloMatch],
    eval_from: date,
    eval_to: date,
    odds: dict[tuple, tuple[float, float, float, str]] | None = None,
) -> list[dict]:
    """Forecast every covered league match in the window.

    `odds` maps (day, competition_id, home, away) to decimal closing prices
    and a book name. Missing keys are scored without a bookmaker line.
    """
    odds = odds or {}
    rows: list[dict] = []
    rates: dict[str, dict[str, int]] = {}
    state: dict = {"day": None, "elo": None, "rates": None, "book": None, "half": None, "month": None}

    def before_apply(ratings: dict[str, float], match: EloMatch) -> None:
        if match.day != state["day"]:
            state["day"] = match.day
            state["book"] = None
            state["half"] = None
            if eval_from <= match.day <= eval_to:
                # Copy. Later matches today must not move this morning's ratings.
                state["elo"] = dict(ratings)
                state["rates"] = {league: dict(counts) for league, counts in rates.items()}
                if state["month"] != (match.day.year, match.day.month):
                    state["month"] = (match.day.year, match.day.month)
                    print(f"  [backtest] {match.day.isoformat()}  scored {len(rows)}")
        in_window = (
            eval_from <= match.day <= eval_to
            and match.kind == "league"
            and match.competition_id in LEAGUE_IDS
        )
        if in_window:
            if state["book"] is None:
                prior = [earlier for earlier in matches if earlier.day < match.day]
                state["book"] = build_strengths(prior, match.day)
                state["half"] = fit_half_shares(prior)
            key = (match.day, match.competition_id, match.home, match.away)
            rows.append(
                _predict_row(
                    match,
                    state["elo"],
                    state["book"],
                    state["half"],
                    state["rates"],
                    odds.get(key),
                )
            )
        if match.kind == "league" and match.competition_id in LEAGUE_IDS:
            bucket = rates.setdefault(match.competition_id, _empty_counts())
            bucket[outcome(match.home_goals, match.away_goals)] += 1

    replay(matches, today=eval_to, before_apply=before_apply)
    return rows


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _probabilities(row: dict, source: str) -> tuple[float, float, float] | None:
    if source == "model":
        return row["p_home"], row["p_draw"], row["p_away"]
    if source == "rates":
        return row["base_home"], row["base_draw"], row["base_away"]
    if row["book_home"] is None:
        return None
    return row["book_home"], row["book_draw"], row["book_away"]


def _score_rows(rows: list[dict], source: str) -> dict[str, list[float]]:
    briers, losses, ranks, picks = [], [], [], []
    for row in rows:
        probs = _probabilities(row, source)
        if probs is None:
            continue
        home, draw, away = probs
        home_goals, away_goals = row["home_goals"], row["away_goals"]
        briers.append(brier(home, draw, away, home_goals, away_goals))
        losses.append(log_loss(home, draw, away, home_goals, away_goals))
        ranks.append(ranked_probability_score(home, draw, away, home_goals, away_goals))
        picked = top_pick(home, draw, away) == outcome(home_goals, away_goals)
        picks.append(1.0 if picked else 0.0)
    return {"brier": briers, "log_loss": losses, "rps": ranks, "accuracy": picks}


def _pack_scores(block: dict[str, list[float]], label: str) -> dict:
    return {
        f"{label}_brier": _round(_mean(block["brier"])),
        f"{label}_log_loss": _round(_mean(block["log_loss"])),
        f"{label}_rps": _round(_mean(block["rps"])),
        f"{label}_accuracy": _round(_mean(block["accuracy"])),
    }


def _bins(pairs: list[tuple[float, float]]) -> list[dict]:
    bins = []
    for low, high in zip(BIN_EDGES, BIN_EDGES[1:]):
        group = [(prob, hit) for prob, hit in pairs if low <= prob < high]
        if not group:
            bins.append({"from": low, "to": min(high, 1.0), "count": 0, "predicted": None, "actual": None})
            continue
        predicted = sum(prob for prob, _hit in group) / len(group)
        actual = sum(hit for _prob, hit in group) / len(group)
        bins.append(
            {
                "from": low,
                "to": min(high, 1.0),
                "count": len(group),
                "predicted": round(predicted, 3),
                "actual": round(actual, 3),
            }
        )
    return bins


def _market_summary(rows: list[dict], key: str, home_name: str = "Home", away_name: str = "Away") -> dict:
    if key == "home":
        pairs = [(row["p_home"], 1.0 if row["home_goals"] > row["away_goals"] else 0.0) for row in rows]
        label = "Home win"
    elif key == "draw":
        pairs = [(row["p_draw"], 1.0 if row["home_goals"] == row["away_goals"] else 0.0) for row in rows]
        label = "Draw"
    elif key == "away":
        pairs = [(row["p_away"], 1.0 if row["home_goals"] < row["away_goals"] else 0.0) for row in rows]
        label = "Away win"
    else:
        pairs = []
        for row in rows:
            if key in row["markets"] and key in row["hits"]:
                pairs.append((float(row["markets"][key]), float(row["hits"][key])))
        label = market_label(key, home_name, away_name)
    if not pairs:
        return {
            "market": key,
            "label": label,
            "count": 0,
            "predicted": None,
            "actual": None,
            "brier": None,
            "bins": _bins([]),
        }
    predicted = sum(prob for prob, _hit in pairs) / len(pairs)
    actual = sum(hit for _prob, hit in pairs) / len(pairs)
    score = sum((prob - hit) ** 2 for prob, hit in pairs) / len(pairs)
    return {
        "market": key,
        "label": label,
        "count": len(pairs),
        "predicted": round(predicted, 3),
        "actual": round(actual, 3),
        "brier": round(score, 4),
        "bins": _bins(pairs),
    }


def _slice_metrics(rows: list[dict]) -> dict:
    book_rows = [row for row in rows if row["book_home"] is not None]
    books: dict[str, int] = {}
    for row in book_rows:
        books[row["book"]] = books.get(row["book"], 0) + 1
    return {
        "matches": len(rows),
        **_pack_scores(_score_rows(rows, "model"), "model"),
        **_pack_scores(_score_rows(rows, "rates"), "rates"),
        "odds_matches": len(book_rows),
        "odds_books": books,
        **_pack_scores(_score_rows(book_rows, "model"), "model_on_odds"),
        **_pack_scores(_score_rows(book_rows, "book"), "book"),
    }


def _gap_sentence(label: str, predicted: float, actual: float) -> str:
    direction = "higher than the results" if predicted > actual else "lower than the results"
    return (
        f"{label} averages {predicted:.1%}, "
        f"and the results landed {actual:.1%}. The price is {direction}."
    )


def _calibration_notes(markets: list[dict]) -> list[str]:
    notes = []
    for market in markets:
        if market["count"] < CALIBRATION_MIN or market["predicted"] is None:
            continue
        gap = market["predicted"] - market["actual"]
        if abs(gap) >= CALIBRATION_GAP:
            notes.append(_gap_sentence(market["label"], market["predicted"], market["actual"]))
        for band in market["bins"]:
            if band["count"] < CALIBRATION_MIN or band["predicted"] is None or band["actual"] is None:
                continue
            if abs(band["predicted"] - band["actual"]) < 0.05:
                continue
            low = f"{band['from']:.0%}"
            high = f"{band['to']:.0%}"
            notes.append(
                _gap_sentence(
                    f"{market['label']} in the {low} to {high} band",
                    band["predicted"],
                    band["actual"],
                )
            )
    return notes


def summarize_forecasts(rows: list[dict], eval_from: date, eval_to: date) -> dict:
    """Aggregate a forecast list. This does not look at matches outside `rows`."""
    result_keys = ("home", "draw", "away")
    market_keys = result_keys + SCORED_MARKETS
    by_league = []
    for league in LEAGUES:
        group = [row for row in rows if row["competition_id"] == league["id"]]
        if not group:
            continue
        entry = {"id": league["id"], "name": league["name"], **_slice_metrics(group)}
        entry["markets"] = [
            {key: value for key, value in _market_summary(group, market).items() if key != "bins"}
            for market in ("over_2.5", "btts", "1h_btts", "1h_over_0.5", "btts_over_2.5")
        ]
        by_league.append(entry)
    seasons = []
    for label in sorted({row["season"] for row in rows}):
        seasons.append({"season": label, **_slice_metrics([row for row in rows if row["season"] == label])})
    markets = [_market_summary(rows, key) for key in market_keys]
    return {
        "from": eval_from.isoformat(),
        "through": eval_to.isoformat(),
        "seasons": [season_label(year) for year in range(2024, season_start_year(eval_to) + 1)],
        "rule": (
            "Each match uses Elo and attack/defense from earlier dates only. "
            "The match, later matches, and other matches on the same day are left out. "
            "League-average rates are that league's results before the date. "
            "Bookmaker figures are closing prices from football-data.co.uk, "
            "with the overround removed, on the matches that have them."
        ),
        "overall": _slice_metrics(rows),
        "by_league": by_league,
        "by_season": seasons,
        "markets": markets,
        "miscalibration": _calibration_notes(markets),
    }


def report_from_catalog(catalog, today: date) -> dict:
    """Walk the loaded catalog and summarize 2024-25 through `today`."""
    finished = [match for match in catalog if match.finished and match.day <= today]
    played = [match.to_elo() for match in finished]
    odds = {}
    for match in finished:
        if match.close_home is None or match.close_draw is None or match.close_away is None:
            continue
        odds[(match.day, match.competition_id, match.home, match.away)] = (
            float(match.close_home),
            float(match.close_draw),
            float(match.close_away),
            match.close_book,
        )
    print(f"Backtesting {BACKTEST_FROM.isoformat()} through {today.isoformat()}...")
    rows = forecast_matches(played, BACKTEST_FROM, today, odds)
    report = summarize_forecasts(rows, BACKTEST_FROM, today)
    report["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    overall = report["overall"]
    print(
        f"  {overall['matches']} matches  "
        f"Brier {overall['model_brier']}  "
        f"rates {overall['rates_brier']}  "
        f"book {overall['book_brier']} on {overall['odds_matches']}"
    )
    return report
