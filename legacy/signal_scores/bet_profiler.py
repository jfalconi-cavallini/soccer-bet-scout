"""
bet_profiler.py

Scores each matched game across 4 bet types based on team stats.
Each bet type returns a score 0-100 and a confidence level.

Bet types:
  AWAY_WIN      - Away team to win outright
  AWAY_MINUS15  - Away team to win by 2+ goals
  WIN_OVER25    - Stronger team wins + over 2.5 total goals
  WIN_BTTS      - Stronger team wins + both teams score

Usage:
  from src.strategy.bet_profiler import profile_bets
  bets = profile_bets(home_profile, away_profile, h2h, stats_score)
"""

from dataclasses import dataclass


@dataclass
class BetProfile:
    bet_type:   str    # "AWAY_WIN", "AWAY_MINUS15", "WIN_OVER25", "WIN_BTTS"
    team:       str    # Which team we're backing e.g. "Manchester City FC"
    score:      float  # 0-100, how strong this bet looks
    confidence: int    # 0-100, how much data we have
    reasoning:  list   # List of strings explaining the score


def profile_bets(
    home_name:    str,
    away_name:    str,
    home_profile: dict,
    away_profile: dict,
    h2h:          dict,
    stats_score:  dict,
) -> list[BetProfile]:
    """
    Score all 4 bet types for a given match.

    Parameters:
        home_name    : Home team name string
        away_name    : Away team name string
        home_profile : From get_team_profile() for home team
        away_profile : From get_team_profile() for away team
        h2h          : From get_h2h()
        stats_score  : From compute_stats_score()

    Returns:
        List of BetProfile objects sorted by score descending
    """
    bets = []

    bets.append(_score_away_win(away_name, home_profile, away_profile, h2h, stats_score))
    bets.append(_score_away_minus15(away_name, home_profile, away_profile, h2h, stats_score))
    bets.append(_score_win_over25(home_name, away_name, home_profile, away_profile, h2h, stats_score))
    bets.append(_score_win_btts(home_name, away_name, home_profile, away_profile, h2h, stats_score))

    return sorted(bets, key=lambda b: b.score, reverse=True)


def _clamp(val, lo=0, hi=100):
    return max(lo, min(hi, val))


def _score_away_win(away_name, home_p, away_p, h2h, stats):
    """
    AWAY WIN
    Away team wins outright. Good when:
    - Away team has strong away form
    - Home team has weak home record
    - H2H favors away team
    - Stats say away team is clearly stronger
    """
    reasons = []
    score   = 0.0

    # Away form (40%) — how well do they perform on the road?
    af = away_p["away_form_score"]
    contribution = af * 0.40
    score += contribution
    reasons.append(f"Away form {af}/100 → +{contribution:.1f}pts")

    # Home team weakness at home (30%)
    # Invert home_form_score — bad home team = good for away bet
    home_weakness = 100 - home_p["home_form_score"]
    contribution  = home_weakness * 0.30
    score += contribution
    reasons.append(f"Home team home weakness {home_weakness}/100 → +{contribution:.1f}pts")

    # H2H favoring away team (15%)
    # weighted_score is from home team's perspective, so invert for away
    h2h_away = 100 - h2h["weighted_score"]
    contribution = h2h_away * 0.15
    score += contribution
    reasons.append(f"H2H (away perspective) {h2h_away:.0f}/100 → +{contribution:.1f}pts")

    # Stats say away team is stronger (15%)
    away_win_prob = stats["away_win_prob"]
    contribution  = away_win_prob * 0.15
    score += contribution
    reasons.append(f"Stats away win prob {away_win_prob}% → +{contribution:.1f}pts")

    confidence = min(100, away_p["away_games"] * 15 + h2h["confidence"] // 4)

    return BetProfile(
        bet_type="AWAY_WIN",
        team=away_name,
        score=round(_clamp(score), 1),
        confidence=confidence,
        reasoning=reasons,
    )


def _score_away_minus15(away_name, home_p, away_p, h2h, stats):
    """
    AWAY -1.5 (win by 2+)
    Stricter than away win. Good when:
    - Away team scores a lot on the road
    - Home team concedes a lot at home
    - Away team is significantly stronger (big gap in stats)
    - H2H games have been one-sided
    """
    reasons = []
    score   = 0.0

    # Away scoring rate (35%) — do they score 1.5+ per game away?
    # Normalize: 0 goals/g = 0, 2.5+ goals/g = 100
    agpg         = away_p["away_goals_pg"]
    scoring_norm = _clamp((agpg / 2.5) * 100)
    contribution = scoring_norm * 0.35
    score += contribution
    reasons.append(f"Away goals/game {agpg} → scoring score {scoring_norm:.0f}/100 → +{contribution:.1f}pts")

    # Home defensive weakness (35%) — do they concede a lot at home?
    # Normalize: 0 conceded/g = 0 (strong), 2.5+ = 100 (very weak)
    hcpg         = home_p["home_conceded_pg"]
    def_weakness = _clamp((hcpg / 2.5) * 100)
    contribution = def_weakness * 0.35
    score += contribution
    reasons.append(f"Home conceded/game {hcpg} → defensive weakness {def_weakness:.0f}/100 → +{contribution:.1f}pts")

    # Away form score (20%)
    af           = away_p["away_form_score"]
    contribution = af * 0.20
    score += contribution
    reasons.append(f"Away form {af}/100 → +{contribution:.1f}pts")

    # H2H margin — did away team win big historically? (10%)
    # Use H2H weighted score inverted (away perspective) as proxy
    h2h_away     = 100 - h2h["weighted_score"]
    contribution = h2h_away * 0.10
    score += contribution
    reasons.append(f"H2H dominance (away) {h2h_away:.0f}/100 → +{contribution:.1f}pts")

    confidence = min(100, away_p["away_games"] * 15 + h2h["confidence"] // 4)

    return BetProfile(
        bet_type="AWAY_MINUS15",
        team=away_name,
        score=round(_clamp(score), 1),
        confidence=confidence,
        reasoning=reasons,
    )


def _score_win_over25(home_name, away_name, home_p, away_p, h2h, stats):
    """
    WIN + OVER 2.5 GOALS
    Back the stronger team AND expect 3+ goals. Good when:
    - Both teams score and/or concede a lot
    - H2H games tend to be high scoring
    - One team is clearly dominant (likely to score 2+)
    - Neither team keeps many clean sheets
    """
    reasons = []
    score   = 0.0

    # Combined goals environment (40%)
    # Average of (home goals/g + away goals/g + home conceded/g + away conceded/g) / 4
    avg_goals_env = (
        home_p["goals_pg"] + away_p["goals_pg"] +
        home_p["conceded_pg"] + away_p["conceded_pg"]
    ) / 4
    # Normalize: 1.0 avg = 40, 2.0 avg = 80, 2.5+ = 100
    goals_norm   = _clamp((avg_goals_env / 2.0) * 80)
    contribution = goals_norm * 0.40
    score += contribution
    reasons.append(f"Goals environment avg {avg_goals_env:.2f}/g → {goals_norm:.0f}/100 → +{contribution:.1f}pts")

    # H2H avg goals (20%)
    h2h_goals_norm = _clamp((h2h["avg_goals"] / 3.0) * 100)
    contribution   = h2h_goals_norm * 0.20
    score += contribution
    reasons.append(f"H2H avg goals {h2h['avg_goals']} → {h2h_goals_norm:.0f}/100 → +{contribution:.1f}pts")

    # Stronger team form (30%) — pick the team more likely to win
    home_win_prob = stats["home_win_prob"]
    away_win_prob = stats["away_win_prob"]
    if home_win_prob >= away_win_prob:
        backing       = home_name
        stronger_form = home_p["form_score"]
    else:
        backing       = away_name
        stronger_form = away_p["form_score"]
    contribution = stronger_form * 0.30
    score += contribution
    reasons.append(f"Backing {backing} form {stronger_form}/100 → +{contribution:.1f}pts")

    # Low clean sheet rate from both teams (10%)
    avg_cs_rate   = (home_p["clean_sheet_rate"] + away_p["clean_sheet_rate"]) / 2
    no_cs_score   = 100 - avg_cs_rate  # Low CS = more goals expected
    contribution  = no_cs_score * 0.10
    score += contribution
    reasons.append(f"Avg clean sheet rate {avg_cs_rate:.0f}% → no-CS score {no_cs_score:.0f}/100 → +{contribution:.1f}pts")

    confidence = min(100, home_p["games"] * 8 + away_p["games"] * 8 + h2h["confidence"] // 5)

    return BetProfile(
        bet_type="WIN_OVER25",
        team=backing,
        score=round(_clamp(score), 1),
        confidence=confidence,
        reasoning=reasons,
    )


def _score_win_btts(home_name, away_name, home_p, away_p, h2h, stats):
    """
    WIN + BOTH TEAMS TO SCORE
    Back the stronger team AND both teams score. Good when:
    - Both teams have high individual BTTS rates
    - H2H games frequently see both teams score
    - Neither team has a dominant clean sheet record
    - Game is competitive (not a complete mismatch)
    """
    reasons = []
    score   = 0.0

    # Both teams' individual BTTS rate (40%)
    avg_btts     = (home_p["btts_rate"] + away_p["btts_rate"]) / 2
    contribution = avg_btts * 0.40
    score += contribution
    reasons.append(f"Avg team BTTS rate {avg_btts:.0f}% → +{contribution:.1f}pts")

    # Neither team keeps clean sheets (30%)
    avg_cs        = (home_p["clean_sheet_rate"] + away_p["clean_sheet_rate"]) / 2
    no_cs_score   = 100 - avg_cs
    contribution  = no_cs_score * 0.30
    score += contribution
    reasons.append(f"No-clean-sheet score {no_cs_score:.0f}/100 → +{contribution:.1f}pts")

    # H2H BTTS rate (20%)
    contribution = h2h["btts_rate"] * 0.20
    score += contribution
    reasons.append(f"H2H BTTS rate {h2h['btts_rate']}% → +{contribution:.1f}pts")

    # Competitiveness (10%) — if teams are close in quality, more likely both score
    # Smaller gap in stats = more competitive = higher score here
    prob_gap       = abs(stats["home_win_prob"] - stats["away_win_prob"])
    competiveness  = _clamp(100 - prob_gap * 2)  # 0 gap = 100, 50 gap = 0
    contribution   = competiveness * 0.10
    score += contribution
    reasons.append(f"Competitiveness (prob gap {prob_gap:.0f}%) → {competiveness:.0f}/100 → +{contribution:.1f}pts")

    # Pick the stronger team to back
    if stats["home_win_prob"] >= stats["away_win_prob"]:
        backing = home_name
    else:
        backing = away_name

    confidence = min(100, home_p["games"] * 8 + away_p["games"] * 8 + h2h["confidence"] // 5)

    return BetProfile(
        bet_type="WIN_BTTS",
        team=backing,
        score=round(_clamp(score), 1),
        confidence=confidence,
        reasoning=reasons,
    )


def print_bet_profiles(bets: list[BetProfile], home_name: str, away_name: str):
    """Pretty print bet profiles for a match."""
    print(f"\n  {'─'*55}")
    print(f"  BET PROFILES: {home_name} vs {away_name}")
    print(f"  {'─'*55}")

    labels = {
        "AWAY_WIN":     "Away Win",
        "AWAY_MINUS15": "Away -1.5",
        "WIN_OVER25":   "Win + Over 2.5",
        "WIN_BTTS":     "Win + BTTS",
    }

    for bet in bets:
        bar   = "█" * int(bet.score // 5)
        label = labels.get(bet.bet_type, bet.bet_type)
        print(f"\n  [{label}] — Back: {bet.team}")
        print(f"  Score      : {bar} {bet.score}/100")
        print(f"  Confidence : {bet.confidence}/100")
        print(f"  Reasoning  :")
        for r in bet.reasoning:
            print(f"    · {r}")


# --- Test ---
if __name__ == "__main__":
    # Mock data to test scoring logic without API calls
    home_profile = {
        "form_string": "WWDLW", "form_score": 67,
        "wins": 6, "draws": 2, "losses": 2,
        "goals_pg": 1.8, "conceded_pg": 1.2,
        "clean_sheet_rate": 30, "btts_rate": 60, "games": 10,
        "away_form_score": 50, "away_goals_pg": 1.2,
        "away_conceded_pg": 1.5, "away_games": 5, "away_wins": 2,
        "home_form_score": 80, "home_goals_pg": 2.2,
        "home_conceded_pg": 0.8, "home_games": 5, "home_wins": 4,
    }
    away_profile = {
        "form_string": "WWWDW", "form_score": 87,
        "wins": 8, "draws": 1, "losses": 1,
        "goals_pg": 2.2, "conceded_pg": 0.9,
        "clean_sheet_rate": 50, "btts_rate": 40, "games": 10,
        "away_form_score": 80, "away_goals_pg": 2.0,
        "away_conceded_pg": 1.0, "away_games": 5, "away_wins": 4,
        "home_form_score": 90, "home_goals_pg": 2.4,
        "home_conceded_pg": 0.8, "home_games": 5, "home_wins": 5,
    }
    h2h = {
        "wins": 1, "draws": 1, "losses": 3,
        "weighted_score": 30.0, "confidence": 75,
        "avg_goals": 2.8, "btts_rate": 60,
        "summary": "H2H last 5: 1W 1D 3L | Avg goals: 2.8 | BTTS: 60%",
    }
    stats = {
        "home_win_prob": 38.0,
        "away_win_prob": 62.0,
        "confidence": 85,
        "breakdown": {},
    }

    bets = profile_bets("Arsenal FC", "Manchester City FC",
                        home_profile, away_profile, h2h, stats)

    print("=" * 60)
    print("  BET PROFILER — TEST RUN (Mock Data)")
    print("=" * 60)
    print_bet_profiles(bets, "Arsenal FC", "Manchester City FC")