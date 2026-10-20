"""Log pre-match probabilities and score them once the result is in.

Probabilities are stored as fractions. The score is the multiclass Brier
score: the sum of squared errors on home, draw, and away. Lower is better.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    return {
        "p_home": prediction["p_home"],
        "p_draw": prediction["p_draw"],
        "p_away": prediction["p_away"],
        "xg_home": prediction.get("xg_home"),
        "xg_away": prediction.get("xg_away"),
    }


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
    if existing.get("refresh"):
        return
    kickoff = _parse(existing.get("kickoff_utc") or prediction.get("kickoff_utc"))
    if kickoff is None:
        return
    remaining = kickoff - moment.astimezone(timezone.utc)
    if timedelta(0) <= remaining <= REFRESH_BEFORE:
        existing["refresh"] = {"logged_at": _stamp(moment), **_probs(prediction)}


def _scored(row: dict) -> dict:
    """The refresh is the call closest to kickoff. The original row stays beside it."""
    return row["refresh"] if row.get("refresh") else row


def settle(log: dict, results: dict[str, tuple[int, int]]) -> int:
    """Fill results for logged matches. `results` maps match_id -> (home, away)."""
    updated = 0
    for row in log.get("predictions", []):
        if row.get("result"):
            continue
        score = results.get(row["match_id"])
        if score is None:
            continue
        home_goals, away_goals = score
        scored = _scored(row)
        row["result"] = {"home_goals": home_goals, "away_goals": away_goals}
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


def calibration(log: dict) -> dict:
    settled = [row for row in log.get("predictions", []) if row.get("result")]
    empty = {
        "settled": 0,
        "pending": len(log.get("predictions", [])),
        "brier": None,
        "bins": [],
        "draw_bins": [],
        "away_bins": [],
        "note": "No settled predictions yet. The next rebuild scores matches once they are played.",
    }
    if not settled:
        return empty
    total = sum(row["brier"] for row in settled) / len(settled)
    return {
        "settled": len(settled),
        "pending": len(log.get("predictions", [])) - len(settled),
        "brier": round(total, 4),
        "bins": _bins(settled, "p_home", lambda row: row["result"]["home_goals"] > row["result"]["away_goals"]),
        "draw_bins": _bins(settled, "p_draw", lambda row: row["result"]["home_goals"] == row["result"]["away_goals"]),
        "away_bins": _bins(settled, "p_away", lambda row: row["result"]["home_goals"] < row["result"]["away_goals"]),
        "note": "Multiclass Brier score on home/draw/away. A coin-flip 1/3 each scores about 0.667.",
    }
