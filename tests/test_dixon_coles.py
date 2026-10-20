"""Score grid and the Dixon-Coles low-score correction."""

from src.model.dixon_coles import score_grid, summarize, tau


def test_score_grid_sums_to_one():
    grid = score_grid(1.55, 1.05, rho=-0.1)
    total = sum(sum(row) for row in grid)
    assert abs(total - 1.0) < 1e-9
    assert len(grid) == 7
    assert len(grid[0]) == 7


def test_tau_matches_dixon_coles_cases():
    lam, mu, rho = 1.4, 0.9, -0.13
    assert tau(0, 0, lam, mu, rho) == 1 - (lam * mu * rho)
    assert tau(0, 1, lam, mu, rho) == 1 + (lam * rho)
    assert tau(1, 0, lam, mu, rho) == 1 + (mu * rho)
    assert tau(1, 1, lam, mu, rho) == 1 - rho
    assert tau(2, 2, lam, mu, rho) == 1
    assert tau(3, 0, lam, mu, rho) == 1


def test_negative_rho_lifts_nil_nil_relative_to_independence():
    independent = score_grid(1.5, 1.2, rho=0.0)
    corrected = score_grid(1.5, 1.2, rho=-0.1)
    assert corrected[0][0] > independent[0][0]
    assert corrected[1][1] > independent[1][1]


def test_summary_probabilities_cover_the_result():
    summary = summarize(score_grid(1.3, 1.1, rho=-0.1))
    total = summary["home_win"] + summary["draw"] + summary["away_win"]
    assert abs(total - 1.0) < 1e-9
    assert 0 < summary["btts"] < 1
    assert len(summary["top_scorelines"]) == 5
    assert summary["over"][2.5] + summary["under"][2.5] == 1 or abs(
        summary["over"][2.5] + summary["under"][2.5] - 1
    ) < 1e-9
