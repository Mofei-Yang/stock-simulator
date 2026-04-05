"""
SimulationEngine: Orchestrates the market simulation.

Runs discrete time steps where:
1. Traders generate orders
2. Orders are executed against the order book
3. Order book depth accumulates (creating resistance)
4. Price history is recorded for visualization
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from .order_book import OrderBook
from .trader import Trader

logger = logging.getLogger(__name__)


@dataclass
class Tick:
    """Single simulation tick data for streaming."""
    step: int
    price: float
    volume: float  # total volume executed this step


class SimulationEngine:
    """
    Core simulation loop.

    Architecture notes for future extensibility:
    - Trader types can be added by subclassing Trader
    - Technical analysis can read price_history
    - Order book snapshots enable depth visualization
    """

    def __init__(
        self,
        traders: list[Trader],
        initial_price: float = 100.0,
        liquidity_quantity: float = 50.0,
        tick_interval_ms: int = 100,
    ):
        self.traders = traders
        self.order_book = OrderBook(last_price=initial_price)
        self.liquidity_quantity = liquidity_quantity

        # Recording
        self.price_history: list[float] = []
        self.volume_history: list[float] = []
        self.ticks: list[Tick] = []

        # Control
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._tick_interval = tick_interval_ms / 1000.0
        self._step = 0

        # WebSocket subscribers (set by FastAPI layer)
        self._subscribers: list = []

    async def start(self):
        """Start the simulation loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Simulation started")

    async def stop(self):
        """Stop the simulation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Simulation stopped")

    async def _run_loop(self):
        """Main simulation loop."""
        while self._running:
            tick = self._step_once()
            self._step += 1

            # Notify subscribers
            for callback in self._subscribers:
                try:
                    await callback(tick)
                except Exception as e:
                    logger.warning(f"Subscriber error: {e}")

            await asyncio.sleep(self._tick_interval)

    def _step_once(self) -> Tick:
        """
        Execute one simulation step:
        1. Each trader generates orders
        2. Orders execute against the book
        3. Liquidity is added around current price (order book memory)
        4. Record the resulting price
        """
        step_volume = 0.0
        current_price = self.order_book.last_price

        # Phase 1: Collect all orders from traders
        all_orders = []
        for trader in self.traders:
            orders = trader.generate_orders(current_price, self.price_history)
            all_orders.extend(orders)

        # Phase 2: Execute orders against the book
        for order in all_orders:
            executed_price = self.order_book.place_order(order)
            step_volume += order.quantity

        # Phase 3: Add resting liquidity around current price
        # This simulates the order book "memory" - previously visited prices
        # accumulate depth, creating the mathematical basis for resistance
        new_price = self.order_book.last_price
        buy_price = round(new_price * 0.999, 2)   # slightly below
        sell_price = round(new_price * 1.001, 2)  # slightly above
        self.order_book.add_liquidity(buy_price, sell_price, self.liquidity_quantity)

        # Cleanup negligible levels periodically
        if self._step % 50 == 0:
            self.order_book.cleanup_empty_levels()

        # Phase 4: Record
        self.price_history.append(new_price)
        self.volume_history.append(step_volume)
        tick = Tick(step=self._step, price=new_price, volume=step_volume)
        self.ticks.append(tick)

        return tick

    def subscribe(self, callback):
        """Register a callback for tick updates."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        """Remove a subscriber callback."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def get_price_history(self, limit: Optional[int] = None) -> list[float]:
        """Get recorded price history, optionally limited to last N."""
        if limit is None:
            return self.price_history[:]
        return self.price_history[-limit:]

    def get_order_book_snapshot(self) -> dict:
        """Get current order book depth for visualization."""
        return self.order_book.get_depth_snapshot()

    @property
    def current_price(self) -> float:
        return self.order_book.last_price

    @property
    def is_running(self) -> bool:
        return self._running

    def set_tick_interval_ms(self, ms: int):
        """Dynamically change simulation speed."""
        self._tick_interval = max(1, ms) / 1000.0

    def reset(self, initial_price: float = 100.0):
        """Reset the entire simulation state: order book, history, ticks."""
        self.order_book = OrderBook(last_price=initial_price)
        self.price_history = []
        self.volume_history = []
        self.ticks = []
        self._step = 0

    def generate_ticks(self, count: int, progress_callback=None) -> list[dict]:
        """Synchronously generate N ticks without waiting.

        Useful for data generation / AI training pipelines where
        we need bulk data instantly instead of waiting for the
        async timer loop.

        Args:
            count: number of ticks to generate
            progress_callback: optional callable(current, total) for progress

        Returns list of dicts with step, price, volume.
        """
        count = max(0, int(count))
        results = []
        for i in range(count):
            tick = self._step_once()
            self._step += 1
            self.ticks.append(tick)
            self.price_history.append(tick.price)
            if tick.volume > 0:
                self.volume_history.append(tick.volume)
            self.order_book.last_price = tick.price
            results.append({"step": tick.step, "price": tick.price, "volume": tick.volume})
            if progress_callback:
                progress_callback(i + 1, count)
        return results
