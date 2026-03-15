"""
simulator.py

A paper trading simulator for Polymarket.

This module pretends to place trades with fake money so we can
test our strategy without risking real capital.

How Polymarket payouts work:
- You buy a YES token at $0.30 (meaning market says 30% chance)
- If the event happens → your token pays out $1.00 → profit of $0.70
- If the event doesn't happen → your token pays out $0.00 → loss of $0.30
- This means prices ARE probabilities, and payouts are always $0 or $1

Key concept: We're not buying/selling like stocks.
We're buying tokens that either pay $1 or $0 at resolution.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.strategy.engine import Signal


# --- Configuration ---
STARTING_BALANCE  = 1_000.0   # Fake dollars we start with
MAX_POSITION_SIZE = 50.0      # Max $ we'll put on any single trade
MIN_CONFIDENCE    = 20.0      # Only trade signals above this confidence score


@dataclass
class Trade:
    """
    Represents a single paper trade we've placed.

    Fields:
        id          : Unique trade identifier
        market_id   : Which market we traded
        question    : Human readable market question
        outcome     : Which outcome we bought (YES/NO/etc)
        price       : Price per token when we bought ($0.00 - $1.00)
        num_tokens  : How many tokens we bought
        cost        : Total $ spent (price × num_tokens)
        timestamp   : When we placed the trade
        resolved    : Has this market settled yet?
        payout      : How much we got back (0 if not resolved)
        result      : "WIN", "LOSS", or "PENDING"
    """
    id: str
    market_id: str
    question: str
    outcome: str
    price: float
    num_tokens: float
    cost: float
    timestamp: str
    resolved: bool = False
    payout: float = 0.0
    result: str = "PENDING"

    @property
    def unrealized_pnl(self) -> float:
        """
        How much we'd make/lose if we closed right now at current price.
        For paper trading we'll use a simplified version.
        """
        if self.resolved:
            return self.payout - self.cost
        # Unrealized: assume current value is cost (no price change tracked yet)
        return 0.0

    @property
    def realized_pnl(self) -> float:
        """How much we actually made/lost after resolution."""
        if not self.resolved:
            return 0.0
        return self.payout - self.cost


@dataclass
class Portfolio:
    """
    Tracks our overall paper trading account.

    Fields:
        balance       : Current available cash (starts at STARTING_BALANCE)
        trades        : List of all trades we've placed
        total_invested: Total $ currently tied up in open positions
    """
    balance: float = STARTING_BALANCE
    trades: list[Trade] = field(default_factory=list)

    @property
    def open_trades(self) -> list[Trade]:
        """Trades that haven't resolved yet."""
        return [t for t in self.trades if not t.resolved]

    @property
    def closed_trades(self) -> list[Trade]:
        """Trades that have resolved."""
        return [t for t in self.trades if t.resolved]

    @property
    def total_invested(self) -> float:
        """Total $ currently sitting in open positions."""
        return sum(t.cost for t in self.open_trades)

    @property
    def realized_pnl(self) -> float:
        """Total profit/loss from all closed trades."""
        return sum(t.realized_pnl for t in self.closed_trades)

    @property
    def total_value(self) -> float:
        """
        Total account value = available cash + money in open positions.
        This is what our account is 'worth' right now.
        """
        return self.balance + self.total_invested

    @property
    def win_rate(self) -> float:
        """Percentage of closed trades that were profitable."""
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for t in self.closed_trades if t.result == "WIN")
        return round((wins / len(self.closed_trades)) * 100, 1)


class PaperTrader:
    """
    The main paper trading engine.

    This class:
    1. Receives signals from our strategy engine
    2. Decides whether to place a trade (based on confidence + balance)
    3. Records the trade in our portfolio
    4. Allows us to manually resolve trades to see P&L
    """

    def __init__(self):
        self.portfolio = Portfolio()
        self._trade_counter = 0  # Simple incrementing ID for trades

    def _generate_trade_id(self) -> str:
        """Generate a simple unique ID for each trade."""
        self._trade_counter += 1
        return f"TRADE-{self._trade_counter:04d}"  # e.g. TRADE-0001

    def _calculate_position_size(self, signal: Signal) -> float:
        """
        Decide how much $ to put on this trade.

        This is called "position sizing" — one of the most important
        concepts in trading. Never put all your money on one trade.

        Our simple rule: bet a % of MAX_POSITION_SIZE based on confidence.
        Higher confidence signal = larger bet, up to MAX_POSITION_SIZE.

        Parameters:
            signal (Signal): The signal we're considering

        Returns:
            float: Dollar amount to invest
        """
        # Scale position size by confidence (0-100)
        # confidence=100 → full MAX_POSITION_SIZE
        # confidence=50  → half MAX_POSITION_SIZE
        size = MAX_POSITION_SIZE * (signal.confidence / 100)

        # Never bet more than we have available
        size = min(size, self.portfolio.balance)

        return round(size, 2)

    def process_signal(self, signal: Signal) -> Optional[Trade]:
        """
        Look at a signal and decide whether to place a paper trade.

        Parameters:
            signal (Signal): A signal from the strategy engine

        Returns:
            Trade if we placed one, None if we passed on it
        """

        # --- Pre-trade checks ---

        # Skip if confidence is too low
        if signal.confidence < MIN_CONFIDENCE:
            print(f"  [PASS] Confidence too low ({signal.confidence} < {MIN_CONFIDENCE})")
            return None

        # Skip if we're out of money
        if self.portfolio.balance < 10.0:
            print(f"  [PASS] Insufficient balance (${self.portfolio.balance:.2f})")
            return None

        # --- Calculate position size ---
        position_size = self._calculate_position_size(signal)

        if position_size <= 0:
            return None

        # --- Calculate how many tokens we're buying ---
        # If YES token costs $0.30, and we have $30 to spend:
        # num_tokens = $30 / $0.30 = 100 tokens
        # If YES wins, we get 100 × $1.00 = $100 back
        price = signal.outcome.price
        num_tokens = position_size / price

        # --- Create the trade record ---
        trade = Trade(
            id=self._generate_trade_id(),
            market_id=signal.market.id,
            question=signal.market.question,
            outcome=signal.outcome.name,
            price=price,
            num_tokens=round(num_tokens, 4),
            cost=position_size,
            timestamp=datetime.now().isoformat(),
        )

        # --- Deduct from balance ---
        self.portfolio.balance -= position_size
        self.portfolio.trades.append(trade)

        print(f"  [TRADE] {trade.id} | {trade.outcome} @ ${trade.price:.4f} "
              f"| {trade.num_tokens:.2f} tokens | Cost: ${trade.cost:.2f}")

        return trade

    def resolve_trade(self, trade_id: str, outcome_won: bool) -> Optional[Trade]:
        """
        Resolve a trade — simulate the market settling.

        Parameters:
            trade_id    : The ID of the trade to resolve (e.g. "TRADE-0001")
            outcome_won : Did the outcome we bet on actually happen?

        Returns:
            The resolved Trade object
        """
        # Find the trade
        trade = next((t for t in self.portfolio.trades if t.id == trade_id), None)

        if not trade:
            print(f"[ERROR] Trade {trade_id} not found")
            return None

        if trade.resolved:
            print(f"[ERROR] Trade {trade_id} already resolved")
            return None

        # Calculate payout
        # WIN  → each token pays $1.00 → payout = num_tokens × $1.00
        # LOSS → each token pays $0.00 → payout = $0.00
        if outcome_won:
            trade.payout = round(trade.num_tokens * 1.0, 2)
            trade.result = "WIN"
        else:
            trade.payout = 0.0
            trade.result = "LOSS"

        trade.resolved = True

        # Return winnings to balance
        self.portfolio.balance += trade.payout

        pnl = trade.realized_pnl
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"

        print(f"  [RESOLVED] {trade_id} → {trade.result} | Payout: ${trade.payout:.2f} | P&L: {pnl_str}")

        return trade

    def print_portfolio(self) -> None:
        """Print a full summary of our paper trading portfolio."""

        print(f"\n{'='*60}")
        print(f"  PAPER TRADING PORTFOLIO")
        print(f"{'='*60}")
        print(f"  Starting Balance : ${STARTING_BALANCE:,.2f}")
        print(f"  Current Balance  : ${self.portfolio.balance:,.2f}")
        print(f"  Total Invested   : ${self.portfolio.total_invested:,.2f}")
        print(f"  Account Value    : ${self.portfolio.total_value:,.2f}")
        print(f"  Realized P&L     : ${self.portfolio.realized_pnl:,.2f}")
        print(f"  Win Rate         : {self.portfolio.win_rate}%")
        print(f"  Open Trades      : {len(self.portfolio.open_trades)}")
        print(f"  Closed Trades    : {len(self.portfolio.closed_trades)}")

        if self.portfolio.open_trades:
            print(f"\n  --- Open Positions ---")
            for trade in self.portfolio.open_trades:
                print(f"  {trade.id} | {trade.outcome:<10} | "
                      f"${trade.cost:.2f} invested | "
                      f"{trade.num_tokens:.2f} tokens @ ${trade.price:.4f}")

        if self.portfolio.closed_trades:
            print(f"\n  --- Closed Positions ---")
            for trade in self.portfolio.closed_trades:
                pnl = trade.realized_pnl
                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                print(f"  {trade.id} | {trade.outcome:<10} | "
                      f"{trade.result:<4} | P&L: {pnl_str}")


# --- Run directly for testing ---
if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

    from src.data.market_reader import fetch_markets
    from src.data.parser import parse_markets
    from src.strategy.engine import analyze_markets

    print("Fetching markets...\n")
    raw = fetch_markets(limit=20)
    markets = parse_markets(raw)

    print(f"Parsed {len(markets)} markets. Running strategy...\n")
    signals = analyze_markets(markets)

    print(f"\nProcessing {len(signals)} signals...\n")
    trader = PaperTrader()

    for signal in signals:
        trader.process_signal(signal)

    # Print portfolio before any resolutions
    trader.print_portfolio()

    # --- Simulate resolving one trade manually ---
    # If we have any open trades, let's pretend the first one won
    if trader.portfolio.open_trades:
        first_trade = trader.portfolio.open_trades[0]
        print(f"\n--- Simulating resolution of {first_trade.id} as a WIN ---")
        trader.resolve_trade(first_trade.id, outcome_won=True)

        print(f"\n--- Simulating resolution of next trade as a LOSS ---")
        if len(trader.portfolio.open_trades) > 0:
            next_trade = trader.portfolio.open_trades[0]
            trader.resolve_trade(next_trade.id, outcome_won=False)

    # Print final portfolio
    trader.print_portfolio()