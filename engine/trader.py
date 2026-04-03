"""
Trader classes that generate orders for the simulation.

The video's key insight: random traders with no strategy,
placing taker-only orders ±1% from current price, are enough
to produce realistic support/resistance patterns.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .order_book import Order


class Trader(ABC):
    """Base trader class. Subclasses define generate_order()."""

    def __init__(self, trader_id: int):
        self.trader_id = trader_id

    @abstractmethod
    def generate_orders(self, current_price: float, price_history: list[float]) -> list[Order]:
        """Generate orders based on the current market state."""
        ...


@dataclass
class RandomTrader(Trader):
    """
    Places taker-only orders at random prices ±deviation% from current price.

    This is the core trader type from the video. The ±1% deviation ensures
    orders are clustered near the current price, and the taker-only approach
    means no maker walls block price movement. Over time, the order book
    accumulates depth at previously visited prices, creating resistance.
    """
    trader_id: int = 0
    deviation: float = 0.01  # ±1%
    min_quantity: float = 1.0
    max_quantity: float = 10.0
    orders_per_step: int = 1  # orders this trader places per step

    def generate_orders(self, current_price: float, price_history: list[float] | None = None) -> list[Order]:
        """Generate random taker orders around the current price."""
        orders = []
        for _ in range(self.orders_per_step):
            # Random price within ±deviation% of current price
            deviation_factor = random.uniform(-self.deviation, self.deviation)
            order_price = current_price * (1 + deviation_factor)
            order_price = round(order_price, 2)

            # Random buy or sell
            is_buy = random.choice([True, False])

            # Random quantity
            quantity = random.uniform(self.min_quantity, self.max_quantity)
            quantity = round(quantity, 2)

            orders.append(Order(price=order_price, quantity=quantity, is_buy=is_buy))

        return orders
