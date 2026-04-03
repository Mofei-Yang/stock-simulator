# Market Simulator

A market simulation based on the principle that **random traders with no strategy** still produce realistic support/resistance patterns — proving they emerge from pure mathematics, not human psychology.

## How It Works

- **200 Random Traders** place taker-only orders ±1% from current price
- **Order Book** accumulates depth at visited prices
- **Resistance emerges** because previously-traded prices have lingering orders
- No psychology, no strategy — just math

## Running

```bash
cd simulator
pip install -r requirements.txt
python main.py
```

Then open **http://localhost:8888** in your browser.

## Controls

| Button | Action |
|--------|--------|
| Start | Start the simulation |
| Pause | Pause the simulation |
| Buy 10 | Place a manual buy order (quantity 10) |
| Sell 10 | Place a manual sell order (quantity 10) |

## Architecture

```
simulator/
├── main.py                 # FastAPI app + WebSocket + REST API
├── engine/
│   ├── order_book.py       # OrderBook: bid/ask levels, order matching
│   ├── trader.py           # Trader base + RandomTrader (±1% taker-only)
│   └── simulation.py       # SimulationEngine: time step loop, tick streaming
└── static/
    ├── index.html          # Frontend UI
    └── app.js              # WebSocket client + Canvas charting
```

## Extensibility

The codebase is designed for extension:
- **New trader types**: subclass `Trader` and implement `generate_orders()`
- **Technical analysis**: read `sim.price_history` for indicator calculation
- **Order book visualization**: `sim.get_order_book_snapshot()` provides depth data
- **Parameter tuning**: adjust `NUM_TRADERS`, `INITIAL_PRICE`, `TICK_INTERVAL_MS` in `main.py`
