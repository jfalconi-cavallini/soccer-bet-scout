"""
market_reader.py

This is our first data-fetching module. Its only job right now is to
ask Polymarket's public API for a list of active markets and return
the raw data so we can look at it.

Polymarket is a prediction market — people bet on real-world events
(elections, sports, crypto prices, etc.) as YES/NO outcomes. Each
"market" is one question with a price between $0 and $1.

A price of $0.70 means the crowd thinks there's a 70% chance of YES.
"""

import requests  # The standard Python library for making HTTP requests (API calls)
import json      # Built-in library for working with JSON data


# --- Constants ---
# A constant is a value that won't change while the program runs.
# We put it at the top so it's easy to find and update.
# This is Polymarket's public Gamma API — no account or API key needed.
BASE_URL = "https://gamma-api.polymarket.com"


def fetch_markets(limit: int = 5) -> list[dict]:
    """
    Fetch a list of active markets from Polymarket.

    Parameters:
        limit (int): How many markets to fetch. Default is 5.
                     We start small so the output is readable.

    Returns:
        list[dict]: A list of market objects. Each market is a dictionary
                    with fields like title, id, volume, etc.

    What's a dict? A dictionary maps keys to values, like:
        {"title": "Will it rain tomorrow?", "volume": 50000}
    """

    # Build the URL we want to call.
    # f-strings let us insert variables into strings with {variable_name}.
    url = f"{BASE_URL}/markets"

    # "params" are query parameters — extra filters we add to the URL.
    # This becomes: /markets?active=true&limit=5
    params = {
    "active": "true",
    "closed": "false",    # add this
    "limit": limit,
    "order": "volume",    # sort by trading volume
    "ascending": "false", # highest volume first (most active markets)
    "tag_slug": "sports",
    }

    # Make the GET request. GET means "give me data" (vs POST = "take this data").
    # We wrap it in try/except so a network error doesn't crash everything.
    try:
        response = requests.get(url, params=params, timeout=10)
        # timeout=10 means: if the server doesn't respond in 10 seconds, give up.

        # raise_for_status() will throw an error if the server returned
        # a failure code (like 404 Not Found or 500 Server Error).
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        # If anything goes wrong with the network call, print a friendly message
        # and return an empty list so the rest of the program doesn't crash.
        print(f"[ERROR] Failed to fetch markets: {e}")
        return []

    # .json() converts the raw text response into a Python list or dict.
    # The API returns a list of market objects.
    markets = response.json()

    return markets


def print_market_summary(market: dict) -> None:
    """
    Print a human-readable summary of a single market.

    Parameters:
        market (dict): One market object returned from the API.

    We use this to understand what fields Polymarket gives us.
    """
    # .get("key", "N/A") safely reads a field — if it doesn't exist, returns "N/A"
    # instead of crashing with a KeyError.
    print("-" * 60)
    print(f"Title    : {market.get('question', 'N/A')}")
    print(f"Market ID: {market.get('id', 'N/A')}")
    print(f"Slug     : {market.get('slug', 'N/A')}")
    
    volume = float(market.get('volume', 0) or 0)
    print(f"Volume   : ${volume:,.2f}")
    print(f"Active   : {market.get('active', 'N/A')}")
    print(f"Closed   : {market.get('closed', 'N/A')}")


def search_markets(query: str, limit: int = 10) -> list[dict]:
    """
    Search Polymarket markets by keyword.

    Parameters:
        query (str): Search term e.g. "Arsenal"
        limit (int): Max results to return

    Returns:
        list[dict]: Raw market objects matching the query
    """
    url = f"{BASE_URL}/markets"

    params = {
        "active":    "true",
        "closed":    "false",
        "limit":     limit,
        "order":     "volume",
        "ascending": "false",
        "search":    query,       # ← this is the key new parameter
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Search failed for '{query}': {e}")
        return []


# --- Main entry point ---
# This block only runs if you execute THIS file directly.
# If another file imports this module, this block is skipped.
# It's a Python best practice.
if __name__ == "__main__":
    print("Fetching markets from Polymarket...\n")

    markets = fetch_markets(limit=5)

    if not markets:
        print("No markets returned. Check your internet connection.")
    else:
        print(f"Found {len(markets)} markets:\n")
        for market in markets:
            print_market_summary(market)

    # Bonus: save the raw response to a file so you can study the full structure
    with open("logs/raw_markets.json", "w") as f:
        json.dump(markets, f, indent=2)

    print("\n[INFO] Raw data saved to logs/raw_markets.json")
    print("[INFO] Open that file to see ALL fields Polymarket returns.")
