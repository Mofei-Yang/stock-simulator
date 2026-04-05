# Market Simulator

An agent-based market simulator that generates realistic price data from first principles. No historical candles, no APIs, no rate limits — just random traders placing orders into an order book, watching support/resistance emerge organically.

## Core Insight

**1000 random traders with no strategy, placing taker-only orders ±1% from current price, are enough to produce realistic support/resistance patterns.**

This isn't a model of any real market. It's a mathematical structure that happens to look like one. Support and resistance don't come from human psychology or chart patterns — they come from the order book accumulating depth at previously-visited prices.

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Open http://localhost:8888 in your browser. The UI shows a live candlestick chart, order book depth, and manual trading controls.

## How It Works

### The Engine

```
1000 RandomTraders
       ↓ (each tick)
random buy/sell @ ±1% of current price
       ↓
Order Book (taker-only execution)
       ↓
price moves + depth accumulates at visited prices
       ↓
support/resistance emerges from order book "memory"
```

### Key Mechanism

Every tick, resting liquidity is added at `price × 0.999` and `price × 1.001`. Prices that have been visited recently accumulate depth in the order book. When price revisits those levels, the accumulated depth absorbs random taker orders, creating the mathematical basis for support/resistance.

This means S/R isn't painted on after the fact — it's generated endogenously by the market structure itself.

## Architecture

```
simulator/
├── main.py                 # FastAPI app + WebSocket + REST API + frontend serving
├── engine/
│   ├── simulation.py       # SimulationEngine: main loop, tick generation, subscriptions
│   ├── order_book.py       # OrderBook: bid/ask levels, taker order matching, depth tracking
│   └── trader.py           # Trader base class + RandomTrader (±1% taker-only orders)
├── cli/
│   ├── sim.py              # CLI wrapper for all API commands (scripting/automation)
│   └── sim_generate.py     # Bulk generation with progress polling
└── static/
    ├── index.html          # Frontend UI (dark terminal-style interface)
    └── app.js              # WebSocket client + Canvas candlestick charting
```

### Data Flow

```
RandomTrader.generate_orders(current_price, price_history)
         ↓
SimulationEngine._step_once()
  - collects orders from all traders
  - executes against OrderBook
  - adds liquidity at ±0.1% of current price
  - records Tick(step, price, volume)
  - notifies WebSocket subscribers
         ↓
FastAPI serves tick stream via WebSocket
  + REST endpoints for history, status, export
         ↓
Frontend renders live candlestick chart + order book depth
```

## CLI Reference

The CLI (`cli/sim.py`) provides programmatic access to all simulator functions without the GUI. Designed for scripting, data collection, and AI training pipelines.

```bash
# View status
python cli/sim.py status

# Generate data (instant, no sleep)
python cli/sim.py generate -c 100000 -e dataset.csv

# Export with custom initial price
python cli/sim.py generate -c 50000 -e data.csv -p 50.0

# Adjust market parameters
python cli/sim.py traders -c 2000      # change trader count
python cli/sim.py speed -p 60          # 60 ticks/sec
python cli/sim.py reset -p 100.0       # reset simulation

# Live monitoring
python cli/sim.py price                # current price
python cli/sim.py ticks -l 100         # last 100 ticks
watch -n 1 "python cli/sim.py price"   # watch price live
```

### CLI Commands

| Command | Description | Flags |
|---|---|---|
| `status` | Show simulation status | — |
| `price` | Show current price | — |
| `ticks` | View accumulated ticks | `-l, --limit N` |
| `generate` | Generate N ticks instantly | `-c COUNT, -e EXPORT, -p PRICE` |
| `start` | Start live simulation | — |
| `stop` | Pause simulation | — |
| `reset` | Reset simulation | `-p, --price` |
| `buy` | Manual buy order | `-q, --quantity` |
| `sell` | Manual sell order | `-q, --quantity` |
| `speed` | Set tick rate | `-p, --prices-per-second` |
| `traders` | Set trader count | `-c, --count` |

## REST API

All endpoints at `http://localhost:8888`.

### Data Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Full simulation status |
| `/api/price` | GET | Current price |
| `/api/history` | GET | Price history (`?limit=500`) |
| `/api/ticks` | GET | Raw tick data (`?limit=0` for all) |
| `/api/orderbook` | GET | Order book depth snapshot |
| `/api/export/csv` | GET | Download all ticks as CSV |

### Control Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/control/start` | POST | Start simulation |
| `/api/control/stop` | POST | Stop simulation |
| `/api/control/reset` | POST | Reset (`?initial_price=100`) |
| `/api/control/buy` | POST | Manual buy (`?quantity=10`) |
| `/api/control/sell` | POST | Manual sell (`?quantity=10`) |
| `/api/control/speed` | POST | Set rate (`?prices_per_second=10`) |
| `/api/control/traders` | POST | Set count (`?count=1000`) |

### Bulk Generation

| Endpoint | Method | Description |
|---|---|---|
| `/api/generate/csv` | POST | Generate N ticks, return CSV (`?count=100000&initial_price=100`) |
| `/api/generate/progress` | GET | Poll generation progress |

### WebSocket

Connect to `ws://localhost:8888/ws` for real-time streaming.

**Messages received (from client):**
```json
{"command": "get_history", "limit": 500}
{"command": "get_book"}
```

**Messages sent (from server):**
```json
{"type": "tick", "step": 12345, "price": 100.42, "volume": 7.5}
{"type": "history", "prices": [100.1, 100.2, ...]}
{"type": "orderbook", "bids": {...}, "asks": {...}, "last_price": 100.42}
```

## Python API (Direct Import)

Skip the HTTP layer entirely and use the engine classes directly:

```python
import sys
sys.path.insert(0, "simulator")
from engine.simulation import SimulationEngine
from engine.trader import RandomTrader

# Create 1000 random traders
traders = [RandomTrader(trader_id=i) for i in range(1000)]

# Create engine (tick_interval_ms=0 means instant, no sleep)
sim = SimulationEngine(
    traders=traders,
    initial_price=100.0,
    tick_interval_ms=0,
)

# Generate ticks instantly
ticks = sim.generate_ticks(100000)

# Access data
print(f"Last price: {sim.current_price}")
print(f"Total ticks: {len(sim.ticks)}")
print(f"Order book bids: {len(sim.order_book.bids)} levels")
```

### Progress Callback

For large generations, track progress in real-time:

```python
def progress(current, total):
    pct = current / total * 100
    print(f"\r  {current:,} / {total:,} ({pct:.1f}%)", end="", flush=True)

ticks = sim.generate_ticks(1_000_000, progress_callback=progress)
```

### Live Simulation with Subscribers

```python
import asyncio

async def on_tick(tick):
    print(f"Step {tick.step}: price={tick.price:.2f} vol={tick.volume:.1f}")

sim = SimulationEngine(traders=traders, initial_price=100.0, tick_interval_ms=100)
sim.subscribe(on_tick)
await sim.start()  # runs in background
```

## Data Generation

### Generating Datasets

```bash
# Quick 100k ticks
python cli/sim.py generate -c 100000 -e data_100k.csv

# Large dataset
python cli/sim.py generate -c 1000000 -e data_1m.csv

# Custom initial price
python cli/sim.py generate -c 50000 -e data.csv -p 50.0
```

### CSV Format

```csv
step,price,volume
0,100.00,5.23
1,100.01,3.87
2,99.99,7.12
...
```

### Converting to OHLCV

```python
import pandas as pd

ticks = pd.read_csv("data_100k.csv")
ticks_per_candle = 60

prices = ticks["price"].values
volumes = ticks["volume"].values
n = len(prices)
nc = n // ticks_per_candle

candles = []
for i in range(nc):
    s = i * ticks_per_candle
    e = s + ticks_per_candle
    candles.append({
        "open": prices[s],
        "high": prices[s:e].max(),
        "low": prices[s:e].min(),
        "close": prices[e - 1],
        "volume": volumes[s:e].sum(),
    })

df = pd.DataFrame(candles)
```

## Extending

### Adding New Trader Types

Subclass `Trader` and implement `generate_orders()`:

```python
from engine.trader import Trader
from engine.order_book import Order

class MomentumTrader(Trader):
    def __init__(self, trader_id, lookback=20):
        super().__init__(trader_id)
        self.lookback = lookback

    def generate_orders(self, current_price, price_history):
        if len(price_history) < self.lookback:
            return []

        recent = price_history[-self.lookback:]
        trend = recent[-1] - recent[0]

        if trend > 0:
            # Bullish → buy above current
            price = round(current_price * 1.005, 2)
            return [Order(price=price, quantity=5.0, is_buy=True)]
        else:
            # Bearish → sell below current
            price = round(current_price * 0.995, 2)
            return [Order(price=price, quantity=5.0, is_buy=False)]

# Mix into the pool
traders = [RandomTrader(trader_id=i) for i in range(900)]
traders += [MomentumTrader(trader_id=i) for i in range(900, 1000)]
```

### Adjusting Market Regimes

The character of generated data depends on these parameters (all in `engine/trader.py` and `main.py`):

| Parameter | Effect | Default |
|---|---|---|
| `RandomTrader.deviation` | Order spread around current price | 0.01 (±1%) |
| `RandomTrader.min_quantity` | Minimum order size | 1.0 |
| `RandomTrader.max_quantity` | Maximum order size | 10.0 |
| `num_traders` (main.py) | Trader pool size | 200 (UI), 1000 (engine) |
| `liquidity_quantity` | Resting orders per tick | 50.0 |
| `tick_interval_ms` | Speed of live simulation | 100 |

**Regime examples:**
- **Thin market** (high vol): 100 traders, deviation=0.02
- **Thick market** (low vol): 5000 traders, deviation=0.005
- **Wide swings**: deviation=0.05 (±5% orders)
- **Tight range**: deviation=0.002 (±0.2% orders)

### Reproducible Markets

Set the RNG seed before creating traders for exact reproducibility:

```python
import random
random.seed(42)

traders = [RandomTrader(trader_id=i) for i in range(1000)]
sim = SimulationEngine(traders=traders, initial_price=100.0, tick_interval_ms=0)
ticks = sim.generate_ticks(100000)
# Identical ticks every run
```

## Performance

| Metric | Value |
|---|---|
| Generation speed (1000 traders) | ~400-500 ticks/sec |
| Generation speed (100 traders) | ~2000 ticks/sec |
| Generation speed (5000 traders) | ~100 ticks/sec |
| 100k ticks | ~3-4 minutes |
| 1M ticks | ~30-40 minutes |
| Memory per 1M ticks | ~50MB |

For fast iteration during development, use fewer traders. The S/R structure is similar across trader counts — only the noise level changes.

## Use Cases

**Learning market microstructure:** Adjust trader count, deviation, and liquidity to see how market structure changes. Fewer traders = more volatility. More traders = smoother price action.

**Strategy development:** Generate unlimited training data. Develop against one dataset, validate against another generated with different seeds.

**AI/ML pipelines:** Generate millions of ticks for model training. Save as parquet for fast loading.

**Backtesting infrastructure testing:** Test your backtest against known market conditions with reproducible data.

**Live trading dashboard:** Run the server, watch price via CLI, place manual orders, export data in real-time.
