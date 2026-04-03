"""
OrderBook: Maintains bid/ask levels and matches orders.

In this simulation, we use taker-only orders (no maker walls).
Taker orders execute immediately against existing price levels,
which is what creates the support/resistance phenomenon over time.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Order:
    """Represents a single order to buy or sell."""
    price: float
    quantity: float
    is_buy: bool  # True = buy, False = sell


@dataclass
class OrderBook:
    """
    Tracks available orders at each price level.

    Even with taker-only orders, the book accumulates 'depth' because
    not all orders get fully consumed in a single step. Prices that
    have been visited recently tend to have lingering orders, creating
    the mathematical basis for support/resistance.
    """
    last_price: float = 100.0

    def __post_init__(self):
        # Price -> remaining quantity at that level
        self.bids: dict[float, float] = {}  # buy side
        self.asks: dict[float, float] = {}  # sell side

    def place_order(self, order: Order) -> float:
        """
        Place a taker order against the book.
        Returns the actual executed price (or last_price if no match).
        """
        if order.is_buy:
            # Taker buy: consume asks from lowest price upward
            executed_price = self._execute_buy(order)
        else:
            # Taker sell: consume bids from highest price downward
            executed_price = self._execute_sell(order)

        # If execution happened, update last_price
        if executed_price is not None:
            self.last_price = executed_price

        return self.last_price

    def _execute_buy(self, order: Order) -> Optional[float]:
        """Execute a buy taker order against existing asks."""
        remaining = order.quantity
        executed_prices = []

        # Get sorted ask prices (ascending - cheapest first for buyers)
        ask_prices = sorted([p for p, q in self.asks.items() if q > 0])

        for ask_price in ask_prices:
            if remaining <= 0:
                break
            available = self.asks.get(ask_price, 0)
            if available <= 0:
                continue
            fill_qty = min(remaining, available)
            self.asks[ask_price] = available - fill_qty
            remaining -= fill_qty
            executed_prices.append((ask_price, fill_qty))

        if executed_prices:
            # Return volume-weighted average execution price
            total_qty = sum(qty for _, qty in executed_prices)
            vwap = sum(p * qty for p, qty in executed_prices) / total_qty
            return vwap
        return None

    def _execute_sell(self, order: Order) -> Optional[float]:
        """Execute a sell taker order against existing bids."""
        remaining = order.quantity
        executed_prices = []

        # Get sorted bid prices (descending - highest first for sellers)
        bid_prices = sorted([p for p, q in self.bids.items() if q > 0], reverse=True)

        for bid_price in bid_prices:
            if remaining <= 0:
                break
            available = self.bids.get(bid_price, 0)
            if available <= 0:
                continue
            fill_qty = min(remaining, available)
            self.bids[bid_price] = available - fill_qty
            remaining -= fill_qty
            executed_prices.append((bid_price, fill_qty))

        if executed_prices:
            total_qty = sum(qty for _, qty in executed_prices)
            vwap = sum(p * qty for p, qty in executed_prices) / total_qty
            return vwap
        return None

    def add_liquidity(self, buy_price: float, sell_price: float, quantity: float):
        """
        Add resting orders at specified price levels.
        This simulates the 'memory' of the order book - prices that were
        recently visited have lingering orders, creating resistance.
        """
        if buy_price > 0:
            self.bids[buy_price] = self.bids.get(buy_price, 0) + quantity
        if sell_price > 0:
            self.asks[sell_price] = self.asks.get(sell_price, 0) + quantity

    def cleanup_empty_levels(self, threshold: float = 0.001):
        """Remove price levels with negligible quantity to keep the book manageable."""
        self.bids = {p: q for p, q in self.bids.items() if q > threshold}
        self.asks = {p: q for p, q in self.asks.items() if q > threshold}

    def get_depth_snapshot(self) -> dict:
        """Return a snapshot of order book depth for visualization."""
        return {
            "bids": {str(p): q for p, q in sorted(self.bids.items(), reverse=True)[:50]},
            "asks": {str(p): q for p, q in sorted(self.asks.items())[:50]},
            "last_price": self.last_price,
        }
