"""
parser.py

Takes raw market data from the Polymarket API and converts it into
clean, structured Python objects.

This is our "translation layer" — the rest of the codebase should
never have to deal with raw API strings or missing fields.
Everything messy gets handled here, once.
"""

import json
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# --- Data Classes ---
# A dataclass is a clean way to define a structured object in Python.
# Think of it like a template for what a "market" looks like in our system.
# It's better than a plain dict because:
#   - Fields are named and typed (easier to read)
#   - Your editor can autocomplete field names
#   - It's harder to accidentally misspell a key

@dataclass
class Outcome:
    """
    Represents one possible outcome in a market.
    Example: YES at $0.67 (67% implied probability)
    """
    name: str            # "Yes" or "No"
    price: float         # 0.0 to 1.0 — this IS the implied probability
    probability: float   # Same as price, expressed as 0-100 for readability


@dataclass
class ParsedMarket:
    """
    A clean, structured representation of one Polymarket market.
    All fields are proper Python types — no raw strings masquerading as lists.
    """
    id: str
    question: str
    slug: str
    outcomes: list[Outcome]          # List of Outcome objects (YES, NO, etc.)
    volume: float                    # Total $ traded in this market
    liquidity: float                 # $ available to trade against right now
    active: bool
    closed: bool
    end_date: Optional[str]          # When the market resolves (can be None)
    raw: dict = field(repr=False)    # Store the original data, hidden from prints


def parse_outcome_prices(outcomes_str: str, prices_str: str) -> list[Outcome]:
    """
    Convert the raw outcomes and prices strings into a list of Outcome objects.

    The API returns these as JSON strings inside a JSON response, e.g.:
        outcomes_str = '["Yes", "No"]'
        prices_str   = '["0.67", "0.33"]'

    We need to:
    1. Parse the strings into actual Python lists
    2. Pair each outcome name with its price
    3. Convert price strings to floats

    Parameters:
        outcomes_str (str): JSON string of outcome names
        prices_str (str):   JSON string of price values

    Returns:
        list[Outcome]: Clean list of Outcome objects
    """
    try:
        # json.loads() parses a JSON string into a Python object
        # '["Yes", "No"]' becomes ["Yes", "No"]
        outcome_names = json.loads(outcomes_str)
        outcome_prices = json.loads(prices_str)
    except (json.JSONDecodeError, TypeError):
        # If parsing fails for any reason, return empty list rather than crash
        return []

    outcomes = []

    # zip() pairs up two lists element by element:
    # zip(["Yes","No"], ["0.67","0.33"]) → [("Yes","0.67"), ("No","0.33")]
    for name, price_str in zip(outcome_names, outcome_prices):
        price = float(price_str)

        outcomes.append(Outcome(
            name=name,
            price=round(price, 4),
            probability=round(price * 100, 2),  # 0.67 → 67.0%
        ))

    return outcomes


def parse_market(raw: dict) -> Optional[ParsedMarket]:
    """
    Convert one raw API market dictionary into a clean ParsedMarket object.

    Parameters:
        raw (dict): One market object directly from the API response

    Returns:
        ParsedMarket if parsing succeeds, None if the data is too broken to use
    """

    # Pull out the raw outcome/price strings
    outcomes_str = raw.get("outcomes", "[]")
    prices_str = raw.get("outcomePrices", "[]")

    outcomes = parse_outcome_prices(outcomes_str, prices_str)

    # If we couldn't parse outcomes, this market isn't useful to us
    if not outcomes:
        return None

    # Safely convert volume and liquidity to floats
    # The 'or 0' handles None values — float(None) would crash
    volume = float(raw.get("volume", 0) or 0)
    liquidity = float(raw.get("liquidity", 0) or 0)

    return ParsedMarket(
        id=str(raw.get("id", "")),
        question=raw.get("question", "Unknown"),
        slug=raw.get("slug", ""),
        outcomes=outcomes,
        volume=volume,
        liquidity=liquidity,
        active=bool(raw.get("active", False)),
        closed=bool(raw.get("closed", False)),
        end_date=raw.get("endDate"),
        raw=raw,  # Keep the original in case we need fields later
    )


def parse_markets(raw_markets: list[dict]) -> list[ParsedMarket]:
    """
    Parse a list of raw market dicts into a list of ParsedMarket objects.
    Skips any markets that fail to parse instead of crashing.

    Parameters:
        raw_markets (list[dict]): Raw list from the API

    Returns:
        list[ParsedMarket]: Clean, usable market objects
    """
    parsed = []

    for raw in raw_markets:
        market = parse_market(raw)
        if market is not None:
            parsed.append(market)

    return parsed


def print_parsed_market(market: ParsedMarket) -> None:
    """
    Pretty-print a ParsedMarket in a readable format.
    """
    print("-" * 60)
    print(f"Question  : {market.question}")
    print(f"ID        : {market.id}")
    print(f"Volume    : ${market.volume:,.2f}")
    print(f"Liquidity : ${market.liquidity:,.2f}")
    print(f"Ends      : {market.end_date or 'Unknown'}")
    print(f"Outcomes  :")

    for outcome in market.outcomes:
        # Build a simple visual probability bar
        bar_length = int(outcome.probability / 5)  # scale to 20 chars max
        bar = "█" * bar_length

        print(f"   {outcome.name:<6} | {bar:<20} | {outcome.probability:>6.2f}%  (${outcome.price:.4f})")


# --- Test it directly ---
if __name__ == "__main__":
    # We import our existing market_reader to get live data
    # This shows how modules connect — reader fetches, parser cleans
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

    from src.data.market_reader import fetch_markets

    print("Fetching and parsing markets...\n")

    raw_markets = fetch_markets(limit=5)
    parsed_markets = parse_markets(raw_markets)

    print(f"Successfully parsed {len(parsed_markets)} markets:\n")

    for market in parsed_markets:
        print_parsed_market(market)