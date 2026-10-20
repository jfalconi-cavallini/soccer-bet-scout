"""Log pre-match probabilities and score them once the result is in.

Probabilities are stored as fractions. The score is the multiclass Brier
score: the sum of squared errors on home, draw, and away. Lower is better.
"""

from __future__ import annotations

from datetime import datetime, timezone


def brier(p_home: float, p_draw: float, p_away: float, home_goals: int, away_goals: int) -> float:
    y_home = 1.0 if home_goals > away_goals else 0.0
    y_draw = 1.0 if home_goals == away_goals else 0.0
    y_away = 1.0 if home_goals < away_goals else 0.0
    return (p_home - y_home) ** 2 + (p_draw - y_draw) ** 2 + (p_away - y_away) ** 2


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def upsert_prediction(log: dict, prediction: dict) -> None:
    """Keep the first logged probability for a match. Later rebuilds do not rewrite it."""
    rows = log.setdefault("predictions", [])
    if any(row["match_id"] == prediction["match_id"] for row in rows):
        return
    rows.append(
        {
            "match_id": prediction["match_id"],
            "logged_at": _now(),
            "kickoff_utc": prediction.get("kickoff_utc"),
            "home": prediction["home"],
            "away": prediction["away"],
            "home_name": prediction.get("home_name"),
            "away_name": prediction.get("away_name"),
            "p_home": prediction["p_home"],
            "p_draw": prediction["p_draw"],
            "p_away": prediction["p_away"],
            "xg_home": prediction.get("xg_home"),
            "xg_away": prediction.get("xg_away"),
            "result": None,
            "settled_at": None,
            "brier": None,
        }
    )


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
        row["result"] = {"home_goals": home_goals, "away_goals": away_goals}
        row["settled_at"] = _now()
        row["brier"] = round(
            brier(row["p_home"], row["p_draw"], row["p_away"], home_goals, away_goals),
            4,
        )
        updated += 1
    return updated


def calibration(log: dict) -> dict:
    settled = [row for row in log.get("predictions", []) if row.get("result")]
    if not settled:
        return {
            "settled": 0,
            "pending": len(log.get("predictions", [])),
            "brier": None,
            "bins": [],
            "note": "No settled predictions yet. The next rebuild scores matches once they are played.",
        }
    total = sum(row["brier"] for row in settled) / len(settled)
    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    bins = []
    for low, high in zip(edges, edges[1:]):
        group = [row for row in settled if low <= row["p_home"] < high]
        if not group:
            bins.append({"from": low, "to": min(high, 1.0), "count": 0, "predicted": None, "actual": None})
            continue
        predicted = sum(row["p_home"] for row in group) / len(group)
        actual = sum(1 for row in group if row["result"]["home_goals"] > row["result"]["away_goals"]) / len(group)
        bins.append(
            {
                "from": low,
                "to": min(high, 1.0),
                "count": len(group),
                "predicted": round(predicted, 3),
                "actual": round(actual, 3),
            }
        )
    return {
        "settled": len(settled),
        "pending": len(log.get("predictions", [])) - len(settled),
        "brier": round(total, 4),
        "bins": bins,
        "note": "Multiclass Brier score on home/draw/away. A coin-flip 1/3 each scores about 0.667.",
    }
