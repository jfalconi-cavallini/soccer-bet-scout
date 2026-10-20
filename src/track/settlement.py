"""Log pre-match probabilities and score them once the result is in.

Probabilities are stored as fractions. The score is the multiclass Brier
score: the sum of squared errors on home, draw, and away. Lower is better.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.model.markets import market_hit

# A rebuild inside this window writes a second probability and then stops.
REFRESH_BEFORE = timedelta(hours=24)


def brier(p_home: float, p_draw: float, p_away: float, home_goals: int, away_goals: int) -> float:
    y_home = 1.0 if home_goals > away_goals else 0.0
    y_draw = 1.0 if home_goals == away_goals else 0.0
    y_away = 1.0 if home_goals < away_goals else 0.0
    return (p_home - y_home) ** 2 + (p_draw - y_draw) ** 2 + (p_away - y_away) ** 2


def _stamp(moment: datetime | None = None) -> str:
    when = moment or datetime.now(timezone.utc)
    return when.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _probs(prediction: dict) -> dict:
    payload = {
        "p_home": prediction["p_home"],
        "p_draw": prediction["p_draw"],
        "p_away": prediction["p_away"],
        "xg_home": prediction.get("xg_home"),
        "xg_away": prediction.get("xg_away"),
    }
    if prediction.get("markets"):
        payload["markets"] = prediction["markets"]
    return payload


def _attach_markets(record: dict, prediction: dict) -> None:
    """Fill markets once, on the call that settlement will score."""
    markets = prediction.get("markets")
    if markets and not record.get("markets"):
        record["markets"] = markets


def upsert_prediction(log: dict, prediction: dict, now: datetime | None = None) -> None:
    """Keep the first probability. Write one refresh inside the day before kickoff."""
    rows = log.setdefault("predictions", [])
    existing = next((row for row in rows if row["match_id"] == prediction["match_id"]), None)
    moment = now or datetime.now(timezone.utc)
    if existing is None:
        rows.append(
            {
                "match_id": prediction["match_id"],
                "logged_at": _stamp(moment),
                "kickoff_utc": prediction.get("kickoff_utc"),
                "home": prediction["home"],
                "away": prediction["away"],
                "home_name": prediction.get("home_name"),
                "away_name": prediction.get("away_name"),
                **_probs(prediction),
                "refresh": None,
                "result": None,
                "settled_at": None,
                "brier": None,
            }
        )
        return
    # The 1X2 call is frozen. Markets can still be attached to the scored row.
    if existing.get("refresh"):
        _attach_markets(existing["refresh"], prediction)
        return
    kickoff = _parse(existing.get("kickoff_utc") or prediction.get("kickoff_utc"))
    if kickoff is None:
        _attach_markets(existing, prediction)
        return
    remaining = kickoff - moment.astimezone(timezone.utc)
    if timedelta(0) <= remaining <= REFRESH_BEFORE:
        existing["refresh"] = {"logged_at": _stamp(moment), **_probs(prediction)}
        return
    _attach_markets(existing, prediction)


def _scored(row: dict) -> dict:
    """The refresh is the call closest to kickoff. The original row stays beside it."""
    return row["refresh"] if row.get("refresh") else row


def _unpack(score) -> tuple[int, int, int | None, int | None]:
    if isinstance(score, dict):
        return (
            int(score["home_goals"]),
            int(score["away_goals"]),
            score.get("ht_home"),
            score.get("ht_away"),
        )
    return int(score[0]), int(score[1]), None, None


def settle(log: dict, results: dict) -> int:
    """Fill results for logged matches.

    `results` maps match_id to (home, away) or a dict with optional ht_home
    and ht_away. Half markets without a half-time score are left unscored.
    """
    updated = 0
    for row in log.get("predictions", []):
        if row.get("result"):
            continue
        score = results.get(row["match_id"])
        if score is None:
            continue
        home_goals, away_goals, ht_home, ht_away = _unpack(score)
        scored = _scored(row)
        result = {"home_goals": home_goals, "away_goals": away_goals}
        if ht_home is not None and ht_away is not None:
            result["ht_home"] = int(ht_home)
            result["ht_away"] = int(ht_away)
        row["result"] = result
        row["settled_at"] = _stamp()
        row["brier"] = round(
            brier(scored["p_home"], scored["p_draw"], scored["p_away"], home_goals, away_goals),
            4,
        )
        if row.get("refresh"):
            row["brier_first"] = round(
                brier(row["p_home"], row["p_draw"], row["p_away"], home_goals, away_goals),
                4,
            )
        hits: dict[str, float] = {}
        errors: list[float] = []
        for key, prob in (scored.get("markets") or {}).items():
            hit = market_hit(key, home_goals, away_goals, ht_home, ht_away)
            if hit is None:
                continue
            hits[key] = hit
            errors.append((float(prob) - hit) ** 2)
        if hits:
            row["market_hits"] = hits
            row["market_brier"] = round(sum(errors) / len(errors), 4)
        updated += 1
    return updated


def _bins(settled: list[dict], key: str, happened) -> list[dict]:
    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    bins = []
    for low, high in zip(edges, edges[1:]):
        group = [row for row in settled if low <= _scored(row)[key] < high]
        if not group:
            bins.append({"from": low, "to": min(high, 1.0), "count": 0, "predicted": None, "actual": None})
            continue
        predicted = sum(_scored(row)[key] for row in group) / len(group)
        actual = sum(1 for row in group if happened(row)) / len(group)
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


def _market_pairs(settled: list[dict], key: str) -> list[tuple[float, float]]:
    pairs = []
    for row in settled:
        probs = (_scored(row).get("markets") or {})
        hits = row.get("market_hits") or {}
        if key not in probs or key not in hits:
            continue
        pairs.append((float(probs[key]), float(hits[key])))
    return pairs


def _market_bins(settled: list[dict], key: str) -> list[dict]:
    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    bins = []
    pairs = _market_pairs(settled, key)
    for low, high in zip(edges, edges[1:]):
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


def _market_report(settled: list[dict]) -> list[dict]:
    keys: set[str] = set()
    for row in settled:
        keys.update((row.get("market_hits") or {}).keys())
    report = []
    for key in sorted(keys):
        pairs = _market_pairs(settled, key)
        if not pairs:
            continue
        predicted = sum(prob for prob, _hit in pairs) / len(pairs)
        actual = sum(hit for _prob, hit in pairs) / len(pairs)
        score = sum((prob - hit) ** 2 for prob, hit in pairs) / len(pairs)
        report.append(
            {
                "market": key,
                "count": len(pairs),
                "predicted": round(predicted, 3),
                "actual": round(actual, 3),
                "brier": round(score, 4),
            }
        )
    return report


def calibration(log: dict) -> dict:
    settled = [row for row in log.get("predictions", []) if row.get("result")]
    empty = {
        "settled": 0,
        "pending": len(log.get("predictions", [])),
        "brier": None,
        "bins": [],
        "draw_bins": [],
        "away_bins": [],
        "markets": [],
        "market_bins": {},
        "note": "No settled predictions yet. The next rebuild scores matches once they are played.",
    }
    if not settled:
        return empty
    total = sum(row["brier"] for row in settled) / len(settled)
    watched = ("btts", "over_2.5", "1h_btts", "1h_over_0.5")
    return {
        "settled": len(settled),
        "pending": len(log.get("predictions", [])) - len(settled),
        "brier": round(total, 4),
        "bins": _bins(settled, "p_home", lambda row: row["result"]["home_goals"] > row["result"]["away_goals"]),
        "draw_bins": _bins(settled, "p_draw", lambda row: row["result"]["home_goals"] == row["result"]["away_goals"]),
        "away_bins": _bins(settled, "p_away", lambda row: row["result"]["home_goals"] < row["result"]["away_goals"]),
        "markets": _market_report(settled),
        "market_bins": {key: _market_bins(settled, key) for key in watched},
        "note": "Multiclass Brier score on home/draw/away. A coin-flip 1/3 each scores about 0.667. Market Brier is the average squared error on each logged price.",
    }
