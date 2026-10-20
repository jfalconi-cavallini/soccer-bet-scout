"""
sports_data.py

Fetches real match data from API-Football to power our edge model.

Data we pull:
- Today's fixtures in our target leagues
- Last 5 form for each team (W/D/L momentum)
- Head-to-head history between two teams
- Injuries and suspensions

We use this to form our OWN probability estimate for each match,
which we then compare against the Polymarket price to find edge.

API-Football docs: https://www.api-football.com/documentation-v3
Free tier: 100 requests/day — we cache aggressively to preserve them.
"""

import os
import json
import time
import requests
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
API_KEY       = os.getenv("API_FOOTBALL_KEY")
BASE_URL      = "https://v3.football.api-sports.io"
CACHE_DIR     = Path("logs/cache")
CACHE_TTL     = 3600  # Cache responses for 1 hour (3600 seconds)

# Your target leagues with their API-Football league IDs
# We hardcode these so we don't waste API calls looking them up
TARGET_LEAGUES = {
    # Europe - Top 5
    39:  "Premier League",
    140: "La Liga",
    135: "Serie A",
    78:  "Bundesliga",
    61:  "Ligue 1",
    # Europe - Other
    203: "Super Lig",       # Turkey
    307: "Saudi Pro League",
    88:  "Eredivisie",      # Netherlands
    94:  "Primeira Liga",   # Portugal
    # European Competitions
    2:   "Champions League",
    3:   "Europa League",
    848: "Europa Conference League",
    # Americas
    253: "MLS",
}

# Current season year
CURRENT_SEASON = 2025


# --- Cache helpers ---
# Caching means: save the API response to a file, and next time
# we need the same data, read from the file instead of calling the API.
# This preserves our 100 daily requests.

def _cache_path(key: str) -> Path:
    """Generate a file path for a cache entry."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Replace characters that can't be in filenames
    safe_key = key.replace("/", "_").replace("?", "_").replace("&", "_")
    return CACHE_DIR / f"{safe_key}.json"


def _cache_get(key: str) -> dict | None:
    """
    Try to load a cached response.
    Returns None if cache doesn't exist or is expired.
    """
    path = _cache_path(key)
    if not path.exists():
        return None

    # Check if cache is still fresh
    age = time.time() - path.stat().st_mtime
    if age > CACHE_TTL:
        return None

    with open(path) as f:
        return json.load(f)


def _cache_set(key: str, data: dict) -> None:
    """Save a response to the cache."""
    with open(_cache_path(key), "w") as f:
        json.dump(data, f, indent=2)


# --- API client ---

def _api_get(endpoint: str, params: dict = {}) -> dict | None:
    """
    Make a GET request to API-Football with caching.

    All API calls go through this function so we have one place
    that handles auth, errors, and caching.

    Parameters:
        endpoint (str): API endpoint e.g. "/fixtures"
        params (dict):  Query parameters e.g. {"league": 39, "season": 2025}

    Returns:
        dict: The "response" array from the API, or None on failure
    """
    if not API_KEY:
        print("[ERROR] API_FOOTBALL_KEY not found in .env file")
        return None

    # Build a cache key from endpoint + params
    param_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    cache_key = f"{endpoint.strip('/')}_{param_str}"

    # Try cache first
    cached = _cache_get(cache_key)
    if cached is not None:
        print(f"  [CACHE] {endpoint} {params}")
        return cached

    # Make the real API call
    headers = {"x-apisports-key": API_KEY}
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # API-Football wraps everything in a "response" key
        result = data.get("response", [])

        # Cache it for next time
        _cache_set(cache_key, result)

        remaining = data.get("parameters", {})
        errors = data.get("errors", {})
        if errors:
            print(f"  [API ERROR] {errors}")
            return None

        print(f"  [API] {endpoint} {params} → {len(result)} results")
        return result

    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] API call failed: {e}")
        return None


# --- Data fetchers ---

def get_todays_fixtures() -> list[dict]:
    """
    Fetch all fixtures happening today across our target leagues.

    Returns:
        list[dict]: List of fixture objects from API-Football
    """
    today = date.today().isoformat()  # e.g. "2026-03-13"
    print(f"\nFetching fixtures for {today}...")

    all_fixtures = []

    for league_id, league_name in TARGET_LEAGUES.items():
        fixtures = _api_get("/fixtures", {
            "league": league_id,
            "season": CURRENT_SEASON,
            "date": today,
        })

        if fixtures:
            print(f"  Found {len(fixtures)} fixtures in {league_name}")
            all_fixtures.extend(fixtures)

    return all_fixtures


def get_team_form(team_id: int, league_id: int, last: int = 5) -> dict:
    """
    Get a team's last N match results to assess momentum.

    Parameters:
        team_id   : API-Football team ID
        league_id : Which league to look at
        last      : How many recent matches to fetch (default 5)

    Returns:
        dict with keys:
            form_string : e.g. "WWDLW" (most recent last)
            wins        : int
            draws       : int
            losses      : int
            goals_scored: int
            goals_conceded: int
            form_score  : 0-100 rating of recent form
    """
    fixtures = _api_get("/fixtures", {
        "team": team_id,
        "league": league_id,
        "season": CURRENT_SEASON,
        "last": last,
        "status": "FT",  # Only finished matches
    })

    if not fixtures:
        return _empty_form()

    wins = draws = losses = 0
    goals_scored = goals_conceded = 0
    form_chars = []

    for fixture in fixtures:
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})

        home_id = teams.get("home", {}).get("id")
        is_home = home_id == team_id

        # Get goals
        home_goals = goals.get("home", 0) or 0
        away_goals = goals.get("away", 0) or 0

        if is_home:
            scored    = home_goals
            conceded  = away_goals
            won       = teams.get("home", {}).get("winner")
        else:
            scored    = away_goals
            conceded  = home_goals
            won       = teams.get("away", {}).get("winner")

        goals_scored    += scored
        goals_conceded  += conceded

        if won is True:
            wins += 1
            form_chars.append("W")
        elif won is False:
            losses += 1
            form_chars.append("L")
        else:
            draws += 1
            form_chars.append("D")

    # Form score: W=3pts, D=1pt, L=0pts out of max 3*last pts
    max_points  = last * 3
    earned      = wins * 3 + draws * 1
    form_score  = round((earned / max_points) * 100) if max_points > 0 else 0

    return {
        "form_string":     "".join(form_chars),
        "wins":            wins,
        "draws":           draws,
        "losses":          losses,
        "goals_scored":    goals_scored,
        "goals_conceded":  goals_conceded,
        "form_score":      form_score,   # 0-100
    }


def _empty_form() -> dict:
    """Return an empty form dict when we can't fetch data."""
    return {
        "form_string":    "?????",
        "wins":           0,
        "draws":          0,
        "losses":         0,
        "goals_scored":   0,
        "goals_conceded": 0,
        "form_score":     50,  # Neutral when unknown
    }


def get_h2h(home_team_id: int, away_team_id: int, last: int = 5) -> dict:
    """
    Get head-to-head results between two teams.

    Parameters:
        home_team_id : ID of the home team
        away_team_id : ID of the away team
        last         : How many recent H2H matches to look at

    Returns:
        dict with home_wins, away_wins, draws, and a summary string
    """
    h2h_str = f"{home_team_id}-{away_team_id}"

    results = _api_get("/fixtures/headtohead", {
        "h2h": h2h_str,
        "last": last,
    })

    if not results:
        return {"home_wins": 0, "away_wins": 0, "draws": 0, "summary": "No H2H data"}

    home_wins = away_wins = draws = 0

    for match in results:
        teams = match.get("teams", {})
        home_id = teams.get("home", {}).get("id")
        home_won = teams.get("home", {}).get("winner")
        away_won = teams.get("away", {}).get("winner")

        # We always count relative to the CURRENT home team
        if home_id == home_team_id:
            if home_won:
                home_wins += 1
            elif away_won:
                away_wins += 1
            else:
                draws += 1
        else:
            # Match was played with sides reversed
            if home_won:
                away_wins += 1
            elif away_won:
                home_wins += 1
            else:
                draws += 1

    summary = f"H2H last {last}: Home {home_wins}W {draws}D {away_wins}L"
    return {
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws":     draws,
        "summary":   summary,
    }


def get_injuries(team_id: int, league_id: int, fixture_id: int) -> list[dict]:
    """
    Get injury/suspension list for a team ahead of a specific fixture.

    Parameters:
        team_id    : Team to check
        league_id  : League context
        fixture_id : The upcoming fixture ID

    Returns:
        list of injured/suspended players as dicts
    """
    results = _api_get("/injuries", {
        "team":    team_id,
        "fixture": fixture_id,
    })

    if not results:
        return []

    injuries = []
    for player in results:
        injuries.append({
            "name":   player.get("player", {}).get("name", "Unknown"),
            "reason": player.get("player", {}).get("reason", "Unknown"),
            "type":   player.get("player", {}).get("type", "Unknown"),
        })

    return injuries


def parse_fixture(fixture: dict) -> dict:
    """
    Extract the fields we care about from a raw API-Football fixture.

    Parameters:
        fixture (dict): Raw fixture from API-Football

    Returns:
        dict: Clean fixture with just the fields we need
    """
    f    = fixture.get("fixture", {})
    home = fixture.get("teams", {}).get("home", {})
    away = fixture.get("teams", {}).get("away", {})
    lg   = fixture.get("league", {})

    return {
        "fixture_id":   f.get("id"),
        "date":         f.get("date"),
        "status":       f.get("status", {}).get("short", "?"),
        "league_id":    lg.get("id"),
        "league_name":  lg.get("name"),
        "home_team":    home.get("name"),
        "home_team_id": home.get("id"),
        "away_team":    away.get("name"),
        "away_team_id": away.get("id"),
    }


# --- Main test ---
if __name__ == "__main__":
    print("=" * 60)
    print("SPORTS DATA FETCHER — TEST RUN")
    print("=" * 60)

    # Step 1: Get today's fixtures
    raw_fixtures = get_todays_fixtures()

    if not raw_fixtures:
        print("\nNo fixtures found today. Try tomorrow or check your API key.")
    else:
        print(f"\nFound {len(raw_fixtures)} total fixtures today\n")

        # Step 2: Parse and display first 3 fixtures with full intel
        for raw in raw_fixtures[:3]:
            fx = parse_fixture(raw)

            print(f"\n{'='*60}")
            print(f"  {fx['league_name']}")
            print(f"  {fx['home_team']} vs {fx['away_team']}")
            print(f"  Kickoff: {fx['date']}")
            print(f"{'='*60}")

            # Get form for both teams
            print(f"\n  Fetching form for {fx['home_team']}...")
            home_form = get_team_form(fx["home_team_id"], fx["league_id"])

            print(f"  Fetching form for {fx['away_team']}...")
            away_form = get_team_form(fx["away_team_id"], fx["league_id"])

            print(f"\n  HOME: {fx['home_team']}")
            print(f"    Last 5: {home_form['form_string']} | "
                  f"Form score: {home_form['form_score']}/100 | "
                  f"GF: {home_form['goals_scored']} GA: {home_form['goals_conceded']}")

            print(f"\n  AWAY: {fx['away_team']}")
            print(f"    Last 5: {away_form['form_string']} | "
                  f"Form score: {away_form['form_score']}/100 | "
                  f"GF: {away_form['goals_scored']} GA: {away_form['goals_conceded']}")

            # Get H2H
            print(f"\n  Fetching H2H...")
            h2h = get_h2h(fx["home_team_id"], fx["away_team_id"])
            print(f"  {h2h['summary']}")

            # Get injuries
            print(f"\n  Fetching injuries...")
            home_inj = get_injuries(fx["home_team_id"], fx["league_id"], fx["fixture_id"])
            away_inj = get_injuries(fx["away_team_id"], fx["league_id"], fx["fixture_id"])

            print(f"  {fx['home_team']} injuries: "
                  f"{len(home_inj)} player(s) out")
            print(f"  {fx['away_team']} injuries: "
                  f"{len(away_inj)} player(s) out")