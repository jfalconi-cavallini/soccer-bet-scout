"""
engine.py

The strategy engine. Takes parsed market data and applies rules
to identify markets worth paying attention to.

Right now our "strategy" is just filters — we're eliminating
bad markets rather than finding good ones. This is actually
how real quant strategies start: first cut out the junk,
then find the edge.

Later we'll add:
- External probability estimates (our own view vs market view)
- Scoring / ranking of signals
- Position sizing logic
"""

from dataclasses import dataclass
from src.data.parser import ParsedMarket, Outcome


# --- Configuration ---
MIN_LIQUIDITY        = 1_000.0   # Minimum $ liquidity to consider a market
MIN_PROBABILITY      = 5.0       # Ignore outcomes below this % (too unlikely)
MAX_PROBABILITY      = 95.0      # Ignore outcomes above this % (too certain)
MIN_VOLUME           = 500.0     # Minimum $ total volume (low volume = low interest)
MIN_SIGNAL_CONFIDENCE = 25.0     # Minimum confidence score to generate a signal


# --- Signal ---
@dataclass
class Signal:
    """
    Represents a market that our strategy has flagged as interesting.

    Fields:
        market    : The full ParsedMarket object
        outcome   : The specific outcome we're interested in (YES or NO)
        reason    : Human-readable explanation of why we flagged it
        confidence: A simple 0-100 score of how interesting this signal is
    """
    market: ParsedMarket
    outcome: Outcome
    reason: str
    confidence: float


def passes_filters(market: ParsedMarket) -> tuple[bool, str]:
    """
    Check if a market passes our basic quality filters.

    Think of this as a bouncer at the door — most markets don't get in.
    We only want markets that are liquid, active, and tradeable.

    Parameters:
        market (ParsedMarket): The market to check

    Returns:
        tuple[bool, str]: (passed, reason_if_failed)
    """

    if market.closed:
        return False, "Market is closed"

    if not market.active:
        return False, "Market is not active"

    if market.liquidity < MIN_LIQUIDITY:
        return False, f"Liquidity too low (${market.liquidity:,.2f} < ${MIN_LIQUIDITY:,.2f})"

    if market.volume < MIN_VOLUME:
        return False, f"Volume too low (${market.volume:,.2f} < ${MIN_VOLUME:,.2f})"

    if len(market.outcomes) < 2:
        return False, "Not enough outcomes to analyze"

    # --- Keyword filtering ---
    # IMPORTANT: define question_lower FIRST before any keyword checks
    question_lower = market.question.lower()

    # Block list — these keywords mean it's definitely NOT sports
    # Check this BEFORE the sports list to avoid false positives
    BLOCK_KEYWORDS = [
        "inflation", "interest rate", "gdp", "earnings", "ipo",
        "token", "crypto", "bitcoin", "ethereum", "price of",
        "temperature", "celsius", "fahrenheit", "°c", "°f",
        "election", "president", "minister", "senator", "nominee",
        "academy award", "oscar", "emmy", "survivor", "reality",
    ]

    if any(kw in question_lower for kw in BLOCK_KEYWORDS):
        return False, "Blocked keyword detected"

    # Sports allow-list — question must contain at least one of these
    SPORTS_KEYWORDS = [
        # Basketball
        "nba", "basketball", "lakers", "celtics", "warriors", "knicks",
        # Football
        "nfl", "football", "touchdown", "super bowl",
        # Soccer
        "soccer", "fc ", " fc", "uefa", "fifa", "premier league",
        "champions league", "mls", "bundesliga", "serie a", "la liga",
        "win on ", "match", "friendly",
        # Baseball / Hockey
        "mlb", "baseball", "nhl", "hockey",
        # Combat / Racket
        "ufc", "mma", "tennis", "wimbledon",
        # Esports
        "esports", "cs2", "counter-strike", "dota", "league of legends",
        # Generic sports terms
        "championship", "playoff", "tournament", "cup", "league",
        "game 1", "game 2", "game 3", "game 4", "game 5",
        "series", "season", "roster", "draft",
        # Team patterns
        "vs.", " vs ", "spread:", "o/u ", "moneyline",
        # Hockey league
        "ahl", "ahl:",
    ]

    is_sports = any(keyword in question_lower for keyword in SPORTS_KEYWORDS)

    if not is_sports:
        return False, "Not a sports market"

    # Passed all filters
    return True, ""


def find_interesting_outcomes(market: ParsedMarket) -> list[tuple[Outcome, str, float]]:
    """
    Find the single best outcome to trade in a market.

    Instead of flagging both YES and NO, we pick ONE side only —
    the outcome whose probability is closest to 50% (most uncertain).

    Parameters:
        market (ParsedMarket): A market that already passed filters

    Returns:
        list with at most ONE (Outcome, reason, confidence) tuple
    """
    # Filter to only outcomes in our tradeable probability range
    tradeable = [
        o for o in market.outcomes
        if MIN_PROBABILITY <= o.probability <= MAX_PROBABILITY
    ]

    if not tradeable:
        return []

    # Pick the single outcome closest to 50% (highest uncertainty = most edge potential)
    best = min(tradeable, key=lambda o: abs(o.probability - 50.0))

    distance_from_50 = abs(best.probability - 50.0)
    confidence = round(100 - (distance_from_50 * 2), 1)

    reason = (
        f"{best.name} at {best.probability:.1f}% — "
        f"closest to 50/50 ({distance_from_50:.1f}pts away)"
    )

    return [(best, reason, confidence)]


def analyze_markets(markets: list[ParsedMarket]) -> list[Signal]:
    """
    Run all markets through our strategy and return a list of signals.

    Parameters:
        markets (list[ParsedMarket]): All parsed markets from the API

    Returns:
        list[Signal]: Markets/outcomes worth paying attention to
    """
    signals = []

    for market in markets:

        # Step 1: Apply quality filters
        passed, fail_reason = passes_filters(market)
        if not passed:
            print(f"  [SKIP] {market.question[:50]}... → {fail_reason}")
            continue

        # Step 2: Find the best outcome in this market
        interesting = find_interesting_outcomes(market)

        # Step 3: Filter out low-confidence signals
        interesting = [(o, r, c) for o, r, c in interesting if c >= MIN_SIGNAL_CONFIDENCE]

        if not interesting:
            print(f"  [SKIP] {market.question[:50]}... → No outcomes in tradeable range")
            continue

        # Step 4: Create a Signal for each interesting outcome
        for outcome, reason, confidence in interesting:
            signal = Signal(
                market=market,
                outcome=outcome,
                reason=reason,
                confidence=confidence,
            )
            signals.append(signal)
            print(f"  [SIGNAL] {market.question[:50]}... → {reason}")

    return signals


def print_signals(signals: list[Signal]) -> None:
    """Pretty-print all signals in a readable format."""
    if not signals:
        print("\nNo signals generated. Try adjusting your filters.")
        return

    print(f"\n{'='*60}")
    print(f"  {len(signals)} SIGNAL(S) FOUND")
    print(f"{'='*60}")

    for i, signal in enumerate(signals, start=1):
        print(f"\n[{i}] {signal.market.question}")
        print(f"    Outcome    : {signal.outcome.name}")
        print(f"    Probability: {signal.outcome.probability:.2f}%")
        print(f"    Confidence : {signal.confidence}/100")
        print(f"    Liquidity  : ${signal.market.liquidity:,.2f}")
        print(f"    Volume     : ${signal.market.volume:,.2f}")
        print(f"    Reason     : {signal.reason}")


# --- Run directly for testing ---
if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

    from src.data.market_reader import fetch_markets
    from src.data.parser import parse_markets

    print("Fetching markets...\n")
    raw = fetch_markets(limit=100)
    markets = parse_markets(raw)
    print(f"Parsed {len(markets)} markets. Running strategy...\n")

    signals = analyze_markets(markets)
    print_signals(signals)