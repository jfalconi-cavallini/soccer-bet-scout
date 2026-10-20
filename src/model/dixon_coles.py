"""Dixon-Coles score grid.

Independent Poisson scores understate how often games finish 0-0 or 1-1.
The Dixon-Coles tau correction adjusts those four cells, then the 0-6 grid
is renormalized so the probabilities sum to 1.
"""

from __future__ import annotations

import math

from src.config import DIXON_COLES_RHO, SCORE_GRID_MAX


def tau(home_goals: int, away_goals: int, lam: float, mu: float, rho: float) -> float:
    """Low-score dependence factor from Dixon and Coles (1997).

    lam is the home mean, mu is the away mean, rho is the dependence
    parameter (typically a little below zero).
    """
    if home_goals == 0 and away_goals == 0:
        return 1.0 - (lam * mu * rho)
    if home_goals == 0 and away_goals == 1:
        return 1.0 + (lam * rho)
    if home_goals == 1 and away_goals == 0:
        return 1.0 + (mu * rho)
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def poisson_pmf_row(lam: float, max_goals: int) -> list[float]:
    """P(0)..P(max_goals) for a Poisson mean. Stable for small means."""
    lam = max(lam, 1e-9)
    probs = [math.exp(-lam)]
    for goals in range(1, max_goals + 1):
        probs.append(probs[-1] * lam / goals)
    return probs


def score_grid(
    lam: float,
    mu: float,
    rho: float = DIXON_COLES_RHO,
    max_goals: int = SCORE_GRID_MAX,
) -> list[list[float]]:
    """(max_goals+1) x (max_goals+1) joint distribution, rows home, cols away.

    The tail above max_goals is dropped and the remaining mass is scaled
    back to 1. Tau is floored at 0 so a wild rho cannot produce negatives.
    """
    home = poisson_pmf_row(lam, max_goals)
    away = poisson_pmf_row(mu, max_goals)
    raw: list[list[float]] = []
    total = 0.0
    for hg in range(max_goals + 1):
        row: list[float] = []
        for ag in range(max_goals + 1):
            cell = max(0.0, tau(hg, ag, lam, mu, rho)) * home[hg] * away[ag]
            row.append(cell)
            total += cell
        raw.append(row)
    if total <= 0:
        uniform = 1.0 / ((max_goals + 1) ** 2)
        return [[uniform for _ in range(max_goals + 1)] for _ in range(max_goals + 1)]
    return [[cell / total for cell in row] for row in raw]


def summarize(grid: list[list[float]]) -> dict:
    """Win/draw/loss, BTTS, clean sheets, totals, and the top scorelines."""
    max_goals = len(grid) - 1
    p_home = p_draw = p_away = 0.0
    btts = clean_home = clean_away = 0.0
    over = {1.5: 0.0, 2.5: 0.0, 3.5: 0.0, 4.5: 0.0}
    home_over = {0.5: 0.0, 1.5: 0.0, 2.5: 0.0}
    away_over = {0.5: 0.0, 1.5: 0.0, 2.5: 0.0}
    scorelines: list[dict] = []

    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            prob = grid[hg][ag]
            total_goals = hg + ag
            if hg > ag:
                p_home += prob
            elif hg == ag:
                p_draw += prob
            else:
                p_away += prob
            if hg > 0 and ag > 0:
                btts += prob
            if ag == 0:
                clean_home += prob
            if hg == 0:
                clean_away += prob
            for line, bucket in over.items():
                if total_goals > line:
                    over[line] = bucket + prob
            for line in home_over:
                if hg > line:
                    home_over[line] += prob
            for line in away_over:
                if ag > line:
                    away_over[line] += prob
            scorelines.append({"score": f"{hg}-{ag}", "home": hg, "away": ag, "prob": prob})

    scorelines.sort(key=lambda item: item["prob"], reverse=True)
    return {
        "home_win": p_home,
        "draw": p_draw,
        "away_win": p_away,
        "btts": btts,
        "clean_sheet_home": clean_home,
        "clean_sheet_away": clean_away,
        "over": over,
        "under": {line: 1.0 - prob for line, prob in over.items()},
        "home_over": home_over,
        "away_over": away_over,
        "top_scorelines": scorelines[:5],
    }
