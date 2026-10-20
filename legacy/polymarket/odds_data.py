"""
odds_data.py

Fetches real bookmaker odds from The-Odds-API and converts them
into clean probability estimates.

The core idea:
  - Sharp bookmakers (Pinnacle, Bet365, etc.) price lines very accurately
  - When their consensus probability differs from Polymarket's price,
    that gap is our edge
  - We use this as our "external view" to compare against the market

The-Odds-API docs: https://the-odds-api.com/liveapi/guides/v4/
Free tier: 500 requests/month
"""

import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
ODDS_API_KEY  = os.getenv("ODDS_API_KEY")
BASE_URL      = "https://api.the-odds-api.com/v4"
CACHE_DIR     = Path("logs/cache")
CACHE_TTL     = 1800  # Cache odds for 30 minutes (they change more often)

# Minimum edge gap to consider a signal worth trading
# If books say 65% and Polymarket says 55%, gap = 10% → worth flagging
MIN_EDGE_GAP  = 0.07  # 7% minimum gap

# Sports slugs from The-Odds-API
# These are the sport identifiers their API uses
TARGET_SPORTS = [
    "soccer_epl",                    # Premier League
    "soccer_spain_la_liga",          # La Liga
    "soccer_italy_serie_a",          # Serie A
    "soccer_germany_bundesliga",     # Bundesliga
    "soccer_france_ligue_one",       # Ligue 1
    "soccer_turkey_super_league",       # Super Lig
    "soccer_netherlands_eredivisie", # Eredivisie
    "soccer_portugal_primeira_liga", # Primeira Liga
    "soccer_uefa_champs_league",     # Champions League
    "soccer_uefa_europa_league",     # Europa League
    "soccer_usa_mls",                # MLS
]

# Which bookmakers to include in our consensus
# Pinnacle is the sharpest (most accurate) book in the world
# We weight their lines most heavily
SHARP_BOOKS = ["pinnacle", "betfair_ex_eu", "betfair_ex_uk"]
ALL_BOOKS   = []  # Empty = use all available books


# --- Cache helpers (same pattern as sports_data.py) ---

def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace("?", "_").replace("&", "_")
    return CACHE_DIR / f"odds_{safe_key}.json"


def _cache_get(key: str) -> list | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > CACHE_TTL:
        return None
    with open(path) as f:
        return json.load(f)


def _cache_set(key: str, data: list) -> None:
    with open(_cache_path(key), "w") as f:
        json.dump(data, f, indent=2)


# --- API client ---

def _api_get(endpoint: str, params: dict = {}) -> list | None:
    """
    Make a GET request to The-Odds-API with caching.

    Parameters:
        endpoint (str): e.g. "/sports/soccer_epl/odds"
        params (dict):  Query parameters

    Returns:
        list: API response data, or None on failure
    """
    if not ODDS_API_KEY:
        print("[ERROR] ODDS_API_KEY not found in .env file")
        return None

    param_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    cache_key = f"{endpoint.strip('/')}_{param_str}"

    cached = _cache_get(cache_key)
    if cached is not None:
        print(f"  [CACHE] {endpoint}")
        return cached

    # Add API key to params
    params["apiKey"] = ODDS_API_KEY

    try:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            params=params,
            timeout=10
        )

        # The-Odds-API tells us how many requests we have left
        remaining = response.headers.get("x-requests-remaining", "?")
        used      = response.headers.get("x-requests-used", "?")

        response.raise_for_status()
        data = response.json()

        print(f"  [API] {endpoint} → {len(data)} events "
              f"(used: {used}, remaining: {remaining})")

        _cache_set(cache_key, data)
        return data

    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Odds API call failed: {e}")
        return None


# --- Probability helpers ---

def decimal_to_prob(decimal_odds: float) -> float:
    """
    Convert decimal odds to implied probability.

    Decimal odds of 2.0 = 50% (1 / 2.0 = 0.5)
    Decimal odds of 1.5 = 66.7% (1 / 1.5 = 0.667)

    Parameters:
        decimal_odds (float): e.g. 2.5

    Returns:
        float: Implied probability 0.0 to 1.0
    """
    if decimal_odds <= 0:
        return 0.0
    return 1.0 / decimal_odds


def remove_vig(probs: list[float]) -> list[float]:
    """
    Remove the bookmaker's margin (vig) from a set of probabilities.

    Raw implied probs from a book always sum to MORE than 1.0
    because they build in a profit margin. e.g. [0.52, 0.52] sums to 1.04.

    We normalize them so they sum to exactly 1.0 — this gives us
    the book's TRUE probability estimate without their margin.

    Parameters:
        probs (list[float]): Raw implied probabilities that sum to > 1.0

    Returns:
        list[float]: Normalized probabilities that sum to 1.0
    """
    total = sum(probs)
    if total == 0:
        return probs
    return [p / total for p in probs]


# --- Main data fetchers ---

def get_odds_for_sport(sport_slug: str) -> list[dict]:
    """
    Fetch current odds for all upcoming events in a sport.

    Parameters:
        sport_slug (str): e.g. "soccer_epl"

    Returns:
        list[dict]: Raw event odds from The-Odds-API
    """
    return _api_get(
        f"/sports/{sport_slug}/odds",
        {
            "regions":  "eu,uk,us",      # European + US bookmakers
            "markets":  "h2h",           # Head-to-head (win/draw/win) markets
            "oddsFormat": "decimal",     # We want decimal odds (easiest to convert)
        }
    ) or []


def parse_event_odds(event: dict) -> dict | None:
    """
    Parse a raw odds event into a clean structure with consensus probability.

    This is the core function — it takes raw bookmaker odds and produces
    a single consensus probability for each outcome.

    Parameters:
        event (dict): Raw event from The-Odds-API

    Returns:
        dict with home_prob, away_prob, draw_prob, and metadata
        or None if we can't parse it
    """
    home_team    = event.get("home_team", "")
    away_team    = event.get("away_team", "")
    sport        = event.get("sport_key", "")
    commence     = event.get("commence_time", "")
    bookmakers   = event.get("bookmakers", [])

    if not bookmakers:
        return None

    # Collect implied probabilities from each bookmaker
    # Structure: {"Home Team": [prob1, prob2, ...], "Away Team": [...]}
    outcome_probs: dict[str, list[float]] = {}

    for book in bookmakers:
        book_name = book.get("key", "")
        markets   = book.get("markets", [])

        for market in markets:
            if market.get("key") != "h2h":
                continue

            outcomes = market.get("outcomes", [])

            # Get raw implied probs for this book
            raw_probs = []
            names     = []

            for outcome in outcomes:
                name  = outcome.get("name", "")
                price = outcome.get("price", 0)
                prob  = decimal_to_prob(price)
                raw_probs.append(prob)
                names.append(name)

            # Remove vig so probs sum to 1.0
            clean_probs = remove_vig(raw_probs)

            # Store each outcome's prob from this book
            for name, prob in zip(names, clean_probs):
                if name not in outcome_probs:
                    outcome_probs[name] = []
                outcome_probs[name].append(prob)

    if not outcome_probs:
        return None

    # Consensus = average probability across all books
    consensus = {
        name: round(sum(probs) / len(probs), 4)
        for name, probs in outcome_probs.items()
    }

    # Identify home, away, draw
    home_prob = consensus.get(home_team, 0)
    away_prob = consensus.get(away_team, 0)

    # Draw only exists in soccer
    draw_prob = 0.0
    for name, prob in consensus.items():
        if name not in [home_team, away_team]:
            draw_prob = prob
            break

    return {
        "event_id":   event.get("id", ""),
        "sport":      sport,
        "home_team":  home_team,
        "away_team":  away_team,
        "commence":   commence,
        "home_prob":  home_prob,
        "away_prob":  away_prob,
        "draw_prob":  draw_prob,
        "consensus":  consensus,
        "num_books":  len(bookmakers),
    }


def get_all_upcoming_odds() -> list[dict]:
    """
    Fetch and parse odds for all upcoming events across all target sports.

    Returns:
        list[dict]: Clean parsed events with consensus probabilities
    """
    all_events = []

    for sport in TARGET_SPORTS:
        print(f"\n  Fetching odds for {sport}...")
        raw_events = get_odds_for_sport(sport)
        time.sleep(1)

        for event in raw_events:
            parsed = parse_event_odds(event)
            if parsed:
                all_events.append(parsed)

    return all_events


def find_edge_vs_polymarket(
    odds_event: dict,
    polymarket_prob: float,
    outcome: str,  # "home", "away", or "draw"
) -> dict | None:
    """
    Compare our consensus bookmaker probability against a Polymarket price.
    If the gap is large enough, return an edge signal.

    Parameters:
        odds_event      : Parsed event from get_all_upcoming_odds()
        polymarket_prob : Polymarket's implied probability (0.0 to 1.0)
        outcome         : Which outcome to compare ("home"/"away"/"draw")

    Returns:
        dict with edge details, or None if no significant edge
    """
    if outcome == "home":
        our_prob = odds_event["home_prob"]
        team     = odds_event["home_team"]
    elif outcome == "away":
        our_prob = odds_event["away_prob"]
        team     = odds_event["away_team"]
    else:
        our_prob = odds_event["draw_prob"]
        team     = "Draw"

    # Edge = difference between what books think and what Polymarket prices
    edge = our_prob - polymarket_prob

    if abs(edge) < MIN_EDGE_GAP:
        return None  # Gap too small to be meaningful

    direction = "BUY" if edge > 0 else "FADE"
    # BUY  = books think it's more likely than Polymarket → buy the YES token
    # FADE = books think it's less likely than Polymarket → buy the NO token

    return {
        "team":           team,
        "our_prob":       round(our_prob * 100, 1),
        "polymarket_prob": round(polymarket_prob * 100, 1),
        "edge":           round(abs(edge) * 100, 1),
        "direction":      direction,
        "num_books":      odds_event["num_books"],
        "home_team":      odds_event["home_team"],
        "away_team":      odds_event["away_team"],
        "commence":       odds_event["commence"],
    }


# --- Test run ---
if __name__ == "__main__":
    print("=" * 60)
    print("ODDS INTELLIGENCE LAYER — TEST RUN")
    print("=" * 60)

    print("\nFetching odds across all target sports...")
    events = get_all_upcoming_odds()

    print(f"\nTotal events with odds: {len(events)}")
    print("\nSample — first 5 events with consensus probabilities:\n")

    for event in events[:5]:
        print(f"  {event['home_team']} vs {event['away_team']}")
        print(f"  Sport    : {event['sport']}")
        print(f"  Books    : {event['num_books']}")
        print(f"  Home     : {event['home_prob']*100:.1f}%")
        if event['draw_prob'] > 0:
            print(f"  Draw     : {event['draw_prob']*100:.1f}%")
        print(f"  Away     : {event['away_prob']*100:.1f}%")
        print(f"  Kickoff  : {event['commence']}")
        print()

    # Save all events for inspection
    with open("logs/odds_events.json", "w") as f:
        json.dump(events, f, indent=2)
    print(f"\n[INFO] Full odds data saved to logs/odds_events.json")