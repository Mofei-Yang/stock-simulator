"""
FastAPI application that serves the market simulation.

Endpoints:
- GET /          → Frontend UI
- GET /ws        → WebSocket for real-time tick stream
- GET /api/price → Current price
- GET /api/history → Price history
- POST /api/control/start → Start simulation
- POST /api/control/stop  → Stop simulation
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from engine import RandomTrader, SimulationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NUM_TRADERS = 200
INITIAL_PRICE = 100.0
LIQUIDITY_QTY = 50.0
TICK_INTERVAL_MS = 100  # 10 ticks/sec

# ---------------------------------------------------------------------------
# Simulation instance (module-level so lifespan can access it)
# ---------------------------------------------------------------------------
sim: SimulationEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sim
    # Create traders and simulation on startup
    traders = [RandomTrader(trader_id=i) for i in range(NUM_TRADERS)]
    sim = SimulationEngine(
        traders=traders,
        initial_price=INITIAL_PRICE,
        liquidity_quantity=LIQUIDITY_QTY,
        tick_interval_ms=TICK_INTERVAL_MS,
    )
    await sim.start()
    logger.info("Simulation engine initialized")
    yield
    await sim.stop()
    logger.info("Simulation engine shut down")


app = FastAPI(title="Market Simulator", lifespan=lifespan)

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ---------------------------------------------------------------------------
# WebSocket: real-time tick + order book stream
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket client connected")

    async def send_tick(tick):
        """Callback subscribed to simulation ticks."""
        data = {
            "type": "tick",
            "step": tick.step,
            "price": tick.price,
            "volume": tick.volume,
        }
        try:
            await ws.send_json(data)
        except Exception:
            pass  # client may have disconnected

    # Also send order book snapshot periodically
    async def send_book():
        """Send order book depth snapshot."""
        if sim and sim.is_running:
            snapshot = sim.get_order_book_snapshot()
            snapshot["type"] = "orderbook"
            try:
                await ws.send_json(snapshot)
            except Exception:
                pass

    sim.subscribe(send_tick)

    try:
        import asyncio
        book_interval = 1.0  # send book every second
        while True:
            # Wait for messages from client (control commands)
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=book_interval)
            except asyncio.TimeoutError:
                # Timeout is expected - just continue the loop
                continue
            try:
                msg = json.loads(data)
                if msg.get("command") == "get_history":
                    limit = msg.get("limit", 500)
                    history = sim.get_price_history(limit)
                    await ws.send_json({
                        "type": "history",
                        "prices": history,
                    })
                elif msg.get("command") == "get_book":
                    await send_book()
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        pass  # client disconnected
    finally:
        sim.unsubscribe(send_tick)


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------
@app.get("/api/price")
async def get_price():
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    return {"price": sim.current_price, "running": sim.is_running}


@app.get("/api/history")
async def get_history(limit: int = 500):
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    return {"prices": sim.get_price_history(limit)}


@app.get("/api/orderbook")
async def get_orderbook():
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    return sim.get_order_book_snapshot()


@app.post("/api/control/start")
async def start_sim():
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    if not sim.is_running:
        await sim.start()
    return {"status": "running"}


@app.post("/api/control/stop")
async def stop_sim():
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    if sim.is_running:
        await sim.stop()
    return {"status": "stopped"}


@app.post("/api/control/buy")
async def manual_buy(quantity: float = 10.0):
    """Manual buy order from the user."""
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    from engine.order_book import Order
    order = Order(price=sim.current_price * 1.001, quantity=quantity, is_buy=True)
    sim.order_book.place_order(order)
    return {"status": "executed", "price": sim.current_price}


@app.post("/api/control/sell")
async def manual_sell(quantity: float = 10.0):
    """Manual sell order from the user."""
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    from engine.order_book import Order
    order = Order(price=sim.current_price * 0.999, quantity=quantity, is_buy=False)
    sim.order_book.place_order(order)
    return {"status": "executed", "price": sim.current_price}


@app.post("/api/control/speed")
async def set_speed(prices_per_second: int = 10):
    """Change simulation speed. prices_per_second = raw ticks per second."""
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    interval_ms = max(1, int(1000 / max(1, prices_per_second)))
    sim.set_tick_interval_ms(interval_ms)
    return {"status": "updated", "prices_per_second": prices_per_second, "interval_ms": interval_ms}


@app.post("/api/control/reset")
async def reset_sim(initial_price: float = 100.0):
    """Reset simulation: clear order book, price history, candles."""
    if sim is None:
        return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
    sim.reset(initial_price=initial_price)
    return {"status": "reset", "initial_price": initial_price}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8888, reload=False)
