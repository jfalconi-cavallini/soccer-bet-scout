"""
football_stats.py - Football data + team profiling for bet scoring
"""

import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY   = os.getenv("FOOTBALL_DATA_KEY")
BASE_URL  = "https://api.football-data.org/v4"
CACHE_DIR = Path("logs/cache")
CACHE_TTL = 3600

LEAGUE_CODES = {
    "PL": "Premier League", "PD": "La Liga", "SA": "Serie A",
    "BL1": "Bundesliga", "FL1": "Ligue 1", "PPL": "Primeira Liga",
    "DED": "Eredivisie", "CL": "Champions League", "EL": "Europa League",
}

SPORT_SLUG_TO_CODE = {
    "soccer_epl":                    "PL",
    "soccer_spain_la_liga":          "PD",
    "soccer_italy_serie_a":          "SA",
    "soccer_germany_bundesliga":     "BL1",
    "soccer_france_ligue_one":       "FL1",
    "soccer_portugal_primeira_liga": "PPL",
    "soccer_netherlands_eredivisie": "DED",
    "soccer_uefa_champs_league":     "CL",
    "soccer_uefa_europa_league":     "EL",
}


# --- Cache ---

def _cache_path(key):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = key.replace("/", "_").replace("?", "_").replace("&", "_")
    return CACHE_DIR / f"fd_{safe}.json"

def _cache_get(key):
    path = _cache_path(key)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_TTL:
        return None
    with open(path) as f:
        return json.load(f)

def _cache_set(key, data):
    with open(_cache_path(key), "w") as f:
        json.dump(data, f, indent=2)


# --- API ---

def _api_get(endpoint):
    if not API_KEY:
        print("[ERROR] FOOTBALL_DATA_KEY not found in .env")
        return None
    cache_key = endpoint.strip("/").replace("/", "_")
    cached = _cache_get(cache_key)
    if cached is not None:
        print(f"  [CACHE] {endpoint}")
        return cached
    try:
        r = requests.get(f"{BASE_URL}{endpoint}",
                         headers={"X-Auth-Token": API_KEY}, timeout=10)
        r.raise_for_status()
        data = r.json()
        _cache_set(cache_key, data)
        print(f"  [API] {endpoint}")
        return data
    except Exception as e:
        print(f"  [ERROR] {endpoint} → {e}")
        return None


# --- Standings ---

def get_standings(competition_code):
    data = _api_get(f"/competitions/{competition_code}/standings")
    if not data:
        return []
    standings = []
    for table in data.get("standings", []):
        if table.get("type") != "TOTAL":
            continue
        for entry in table.get("table", []):
            team = entry.get("team", {})
            raw_form = entry.get("form") or ""
            standings.append({
                "team_id":       team.get("id"),
                "team_name":     team.get("name", ""),
                "tla":           team.get("tla", ""),
                "position":      entry.get("position"),
                "points":        entry.get("points"),
                "played":        entry.get("playedGames"),
                "won":           entry.get("won"),
                "drawn":         entry.get("draw"),
                "lost":          entry.get("lost"),
                "goals_for":     entry.get("goalsFor"),
                "goals_against": entry.get("goalsAgainst"),
                "goal_diff":     entry.get("goalDifference"),
                "form":          raw_form.replace(",", ""),
            })
    return standings


def find_team_in_standings(team_name, standings):
    name_lower = team_name.lower()
    for entry in standings:
        entry_name = entry["team_name"].lower()
        tla        = entry["tla"].lower()
        if name_lower == entry_name:
            return entry
        if name_lower in entry_name or entry_name in name_lower:
            return entry
        if name_lower == tla:
            return entry
    return None


# --- Team Profile ---

def get_team_profile(team_id, last=10):
    """
    Fetch last N matches and compute a full profile for bet scoring.
    Covers overall, home-specific, and away-specific stats.
    """
    data = _api_get(f"/teams/{team_id}/matches?status=FINISHED&limit={last}")
    if not data:
        return _empty_profile()

    matches = data.get("matches", [])[-last:]
    if not matches:
        return _empty_profile()

    wins = draws = losses = 0
    goals_scored = goals_conceded = 0
    clean_sheets = btts_count = 0
    form_chars = []

    h_wins = h_draws = h_losses = h_scored = h_conceded = h_games = 0
    a_wins = a_draws = a_losses = a_scored = a_conceded = a_games = 0

    for match in matches:
        score     = match.get("score", {})
        full_time = score.get("fullTime", {})
        is_home   = match.get("homeTeam", {}).get("id") == team_id
        winner    = score.get("winner")

        hg = full_time.get("home", 0) or 0
        ag = full_time.get("away", 0) or 0

        scored   = hg if is_home else ag
        conceded = ag if is_home else hg

        goals_scored   += scored
        goals_conceded += conceded

        if conceded == 0:
            clean_sheets += 1
        if scored > 0 and conceded > 0:
            btts_count += 1

        if winner == "DRAW":
            draws += 1
            form_chars.append("D")
        elif (winner == "HOME_TEAM" and is_home) or \
             (winner == "AWAY_TEAM" and not is_home):
            wins += 1
            form_chars.append("W")
        else:
            losses += 1
            form_chars.append("L")

        if is_home:
            h_games += 1; h_scored += scored; h_conceded += conceded
            if winner == "HOME_TEAM": h_wins += 1
            elif winner == "DRAW":   h_draws += 1
            else:                    h_losses += 1
        else:
            a_games += 1; a_scored += scored; a_conceded += conceded
            if winner == "AWAY_TEAM": a_wins += 1
            elif winner == "DRAW":    a_draws += 1
            else:                     a_losses += 1

    n = len(matches)

    def form_score(w, d, games):
        mp = games * 3
        return round(((w * 3 + d) / mp) * 100) if mp > 0 else 50

    return {
        "form_string":      "".join(form_chars),
        "form_score":       form_score(wins, draws, n),
        "wins": wins, "draws": draws, "losses": losses,
        "goals_pg":         round(goals_scored / n, 2)   if n > 0 else 1.2,
        "conceded_pg":      round(goals_conceded / n, 2) if n > 0 else 1.2,
        "clean_sheet_rate": round((clean_sheets / n) * 100) if n > 0 else 30,
        "btts_rate":        round((btts_count / n) * 100)   if n > 0 else 50,
        "games":            n,
        # Away
        "away_form_score":  form_score(a_wins, a_draws, a_games),
        "away_goals_pg":    round(a_scored / a_games, 2)   if a_games > 0 else 1.0,
        "away_conceded_pg": round(a_conceded / a_games, 2) if a_games > 0 else 1.5,
        "away_games":       a_games,
        "away_wins":        a_wins,
        # Home
        "home_form_score":  form_score(h_wins, h_draws, h_games),
        "home_goals_pg":    round(h_scored / h_games, 2)   if h_games > 0 else 1.4,
        "home_conceded_pg": round(h_conceded / h_games, 2) if h_games > 0 else 1.0,
        "home_games":       h_games,
        "home_wins":        h_wins,
    }


def _empty_profile():
    return {
        "form_string": "?????", "form_score": 50,
        "wins": 0, "draws": 0, "losses": 0,
        "goals_pg": 1.2, "conceded_pg": 1.2,
        "clean_sheet_rate": 30, "btts_rate": 50, "games": 0,
        "away_form_score": 50, "away_goals_pg": 1.0,
        "away_conceded_pg": 1.5, "away_games": 0, "away_wins": 0,
        "home_form_score": 50, "home_goals_pg": 1.4,
        "home_conceded_pg": 1.0, "home_games": 0, "home_wins": 0,
    }


# --- H2H ---

def get_h2h(team_id, opponent_id, last=10):
    data = _api_get(f"/teams/{team_id}/matches?status=FINISHED&limit=50")
    if not data:
        return _empty_h2h()

    matches = data.get("matches", [])
    h2h_matches = [
        m for m in matches
        if m.get("homeTeam", {}).get("id") == opponent_id
        or m.get("awayTeam", {}).get("id") == opponent_id
    ][-last:]

    if not h2h_matches:
        return _empty_h2h()

    wins = draws = losses = 0
    ww = wd = wl = 0.0
    total_goals = btts_count = 0
    now = datetime.now(timezone.utc)

    for match in h2h_matches:
        score     = match.get("score", {})
        full_time = score.get("fullTime", {})
        winner    = score.get("winner")
        is_home   = match.get("homeTeam", {}).get("id") == team_id

        hg = full_time.get("home", 0) or 0
        ag = full_time.get("away", 0) or 0
        total_goals += hg + ag
        if hg > 0 and ag > 0:
            btts_count += 1

        try:
            md = datetime.fromisoformat(match.get("utcDate","").replace("Z","+00:00"))
            ya = (now - md).days / 365.25
            w  = 1.0 if ya<=1 else 0.7 if ya<=2 else 0.4 if ya<=3 else 0.2
        except Exception:
            w = 0.5

        if winner == "DRAW":
            draws += 1; wd += w
        elif (winner == "HOME_TEAM" and is_home) or \
             (winner == "AWAY_TEAM" and not is_home):
            wins += 1; ww += w
        else:
            losses += 1; wl += w

    total = wins + draws + losses
    wt    = ww + wd + wl
    ws    = ((ww + wd * 0.5) / wt * 100) if wt > 0 else 50

    return {
        "wins": wins, "draws": draws, "losses": losses,
        "weighted_score": round(ws, 1),
        "confidence":     min(100, total * 15),
        "avg_goals":      round(total_goals / total, 2) if total > 0 else 2.4,
        "btts_rate":      round((btts_count / total) * 100) if total > 0 else 50,
        "summary": f"H2H last {total}: {wins}W {draws}D {losses}L "
                   f"| Avg goals: {round(total_goals/total,2) if total>0 else 'N/A'} "
                   f"| BTTS: {round((btts_count/total)*100) if total>0 else 'N/A'}% "
                   f"(weighted: {ws:.0f}/100)",
    }


def _empty_h2h():
    return {
        "wins": 0, "draws": 0, "losses": 0,
        "weighted_score": 50, "confidence": 0,
        "avg_goals": 2.4, "btts_rate": 50,
        "summary": "No H2H data found",
    }


# --- Win Probability ---

def compute_stats_score(home_standing, away_standing,
                        home_profile, away_profile, h2h, num_teams=20):
    if home_standing and away_standing:
        home_pos = ((num_teams - home_standing["position"]) / (num_teams - 1)) * 100
        away_pos = ((num_teams - away_standing["position"]) / (num_teams - 1)) * 100
        pos_conf = 100
    else:
        home_pos = away_pos = 50
        pos_conf = 0

    h2h_score = h2h["weighted_score"]
    h2h_conf  = h2h["confidence"]

    hc = home_pos * 0.35 + home_profile["form_score"] * 0.40 + h2h_score * 0.25
    ac = away_pos * 0.35 + away_profile["form_score"] * 0.40 + (100 - h2h_score) * 0.25

    total = hc + ac
    if total > 0:
        hwp = min(95, max(5, (hc / total) * 100 + 5))
        awp = min(95, max(5, (ac / total) * 100 - 5))
    else:
        hwp = awp = 50

    return {
        "home_win_prob": round(hwp, 1),
        "away_win_prob": round(awp, 1),
        "confidence":    round(pos_conf * 0.35 + 100 * 0.40 + h2h_conf * 0.25),
        "breakdown": {
            "home_position_score": round(home_pos, 1),
            "away_position_score": round(away_pos, 1),
            "home_form_score":     home_profile["form_score"],
            "away_form_score":     away_profile["form_score"],
            "home_form_string":    home_profile["form_string"],
            "away_form_string":    away_profile["form_string"],
            "h2h_score":           round(h2h_score, 1),
            "h2h_confidence":      h2h_conf,
            "h2h_summary":         h2h["summary"],
        }
    }


# --- Test ---
if __name__ == "__main__":
    print("=" * 60)
    print("  FOOTBALL STATS — TEAM PROFILE TEST")
    print("=" * 60)

    standings = get_standings("PL")
    if not standings:
        print("No data. Check API key.")
    else:
        t1, t2 = standings[0], standings[1]
        print(f"\nProfiling {t1['team_name']} vs {t2['team_name']}\n")

        p1  = get_team_profile(t1["team_id"])
        p2  = get_team_profile(t2["team_id"])
        h2h = get_h2h(t1["team_id"], t2["team_id"])

        for label, p in [(t1["team_name"], p1), (t2["team_name"], p2)]:
            print(f"{label}:")
            print(f"  Form        : {p['form_string']} ({p['form_score']}/100)")
            print(f"  Goals/game  : {p['goals_pg']} scored | {p['conceded_pg']} conceded")
            print(f"  Away form   : {p['away_form_score']}/100 | {p['away_goals_pg']} g/g away")
            print(f"  Home form   : {p['home_form_score']}/100 | {p['home_conceded_pg']} conceded/g home")
            print(f"  Clean sheet : {p['clean_sheet_rate']}%")
            print(f"  BTTS rate   : {p['btts_rate']}%\n")

        print(f"H2H: {h2h['summary']}\n")

        stats = compute_stats_score(t1, t2, p1, p2, h2h)
        print(f"Home win prob : {stats['home_win_prob']}%")
        print(f"Away win prob : {stats['away_win_prob']}%")
        print(f"Confidence    : {stats['confidence']}/100")