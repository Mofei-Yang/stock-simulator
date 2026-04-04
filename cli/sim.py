#!/usr/bin/env python3
"""
CLI wrapper for the Market Simulator.

All GUI actions are available here. Designed for scripting,
data collection, and AI training pipelines.

Usage:
    python cli/sim.py status
    python cli/sim.py price
    python cli/sim.py ticks                  # live accumulated ticks
    python cli/sim.py ticks -l 100           # last 100 live ticks
    python cli/sim.py generate -c 10000      # instant 10k ticks (no sleep)
    python cli/sim.py generate -c 10000 -e ticks.csv  # instant export
    python cli/sim.py buy -q 50
    python cli/sim.py sell -q 50
    python cli/sim.py start
    python cli/sim.py stop
    python cli/sim.py reset
    python cli/sim.py speed -p 60
    python cli/sim.py traders -c 2000

Examples:
    # Instant 100k tick dataset — no waiting, no GUI
    python cli/sim.py generate -c 100000 -e dataset.csv

    # Multiple datasets with different trader counts
    python cli/sim.py traders -c 500 && python cli/sim.py generate -c 50000 -e traders_500.csv
    python cli/sim.py traders -c 2000 && python cli/sim.py generate -c 50000 -e traders_2000.csv

    # Watch price live
    watch -n 1 "python cli/sim.py price"
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.parse

BASE_URL = "http://localhost:8888"


def _get(path: str, params: dict | None = None) -> dict:
    if params:
        qs = urllib.parse.urlencode(params)
        url = f"{BASE_URL}{path}?{qs}"
    else:
        url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"Error: Cannot connect to simulator at {BASE_URL}. Is it running?", file=sys.stderr)
        print(f"  {e.reason}", file=sys.stderr)
        sys.exit(1)


def _post(path: str, params: dict | None = None) -> dict:
    if params:
        qs = urllib.parse.urlencode(params)
        url = f"{BASE_URL}{path}?{qs}"
    else:
        url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"Error: Cannot connect to simulator at {BASE_URL}. Is it running?", file=sys.stderr)
        print(f"  {e.reason}", file=sys.stderr)
        sys.exit(1)


def _download(url: str) -> str:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=600) as resp:
        return resp.read().decode()


def cmd_status(_):
    data = _get("/api/status")
    print(f"  Running:        {data['running']}")
    print(f"  Price:          {data['current_price']:.2f}")
    print(f"  Ticks:          {data['tick_count']}")
    print(f"  Traders:        {data['trader_count']}")
    print(f"  Tick interval:  {data['tick_interval_ms']:.1f} ms")


def cmd_price(_):
    data = _get("/api/price")
    print(f"{data['price']:.2f}")


def cmd_ticks(args):
    if args.limit:
        data = _get("/api/ticks", {"limit": args.limit})
    else:
        data = _get("/api/ticks", {"limit": 0})
    print(f"Total ticks: {data['total']}")
    for t in data["ticks"]:
        print(f"  step={t['step']}  price={t['price']:.4f}  volume={t['volume']:.2f}")


def cmd_generate(args):
    """Generate N ticks instantly (no sleep needed)."""
    count = args.count
    price = args.price

    if args.export:
        # POST to CSV endpoint — instant generation + download
        print(f"  Generating {count:,} ticks... ", end="", flush=True)
        import time
        t0 = time.time()
        url = f"{BASE_URL}/api/generate/csv?count={count}&initial_price={price}"
        req = urllib.request.Request(url, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=600) as resp:
            csv_data = resp.read().decode()
        elapsed = time.time() - t0

        # Write to file
        lines = csv_data.count("\n")
        ticks_generated = lines - 1  # minus header
        rate = ticks_generated / max(elapsed, 0.001)

        with open(args.export, "w") as f:
            f.write(csv_data)
        print(f"done — {ticks_generated:,} ticks → {args.export}")
        print(f"  Time: {elapsed:.1f}s  ({rate:,.0f} ticks/sec)")
    else:
        import time
        print(f"  Generating {count:,} ticks... ", end="", flush=True)
        t0 = time.time()
        data = _post("/api/generate", {"count": count, "initial_price": price})
        elapsed = time.time() - t0
        rate = data['count'] / max(elapsed, 0.001)
        print(f"done")
        print(f"  Generated {data['count']:,} ticks  final_price={data['final_price']:.4f}")
        print(f"  Time: {elapsed:.1f}s  ({rate:,.0f} ticks/sec)")


def cmd_start(_):
    data = _post("/api/control/start")
    print(f"Started: {data['status']}")


def cmd_stop(_):
    data = _post("/api/control/stop")
    print(f"Paused: {data['status']}")


def cmd_reset(args):
    data = _post("/api/control/reset", {"initial_price": args.price or 100.0})
    print(f"Reset: price={data['initial_price']:.2f}")


def cmd_buy(args):
    data = _post("/api/control/buy", {"quantity": args.quantity})
    print(f"Bought: {data['status']}  price={data['price']:.2f}")


def cmd_sell(args):
    data = _post("/api/control/sell", {"quantity": args.quantity})
    print(f"Sold: {data['status']}  price={data['price']:.2f}")


def cmd_speed(args):
    data = _post("/api/control/speed", {"prices_per_second": args.prices_per_second})
    print(f"Velocity: {data['prices_per_second']} prices/s ({data['interval_ms']} ms/tick)")


def cmd_traders(args):
    data = _post("/api/control/traders", {"count": args.count})
    print(f"Traders: {data['trader_count']}")


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Market Simulator CLI")
sub = parser.add_subparsers(dest="command")

sub.add_parser("status", help="Show simulation status")
sub.add_parser("price", help="Show current price")

# ticks — view live accumulated data
p_ticks = sub.add_parser("ticks", help="View live accumulated ticks")
p_ticks.add_argument("-l", "--limit", type=int, default=0, help="Limit ticks (0=all)")

# generate — instant bulk data, no waiting
p_gen = sub.add_parser("generate", help="Generate N ticks instantly (no sleep)")
p_gen.add_argument("-c", "--count", type=int, default=10000, help="Number of ticks to generate")
p_gen.add_argument("-e", "--export", type=str, default="", help="Export CSV to file")
p_gen.add_argument("-p", "--price", type=float, default=100.0, help="Initial price")

sub.add_parser("start", help="Start simulation")
sub.add_parser("stop", help="Pause simulation")
p_reset = sub.add_parser("reset", help="Reset simulation")
p_reset.add_argument("-p", "--price", type=float, default=100.0, help="Initial price")

p_buy = sub.add_parser("buy", help="Place buy order")
p_buy.add_argument("-q", "--quantity", type=float, default=10.0)
p_sell = sub.add_parser("sell", help="Place sell order")
p_sell.add_argument("-q", "--quantity", type=float, default=10.0)

p_speed = sub.add_parser("speed", help="Set tick rate")
p_speed.add_argument("-p", "--prices-per-second", type=int, default=10)
p_traders = sub.add_parser("traders", help="Set trader count")
p_traders.add_argument("-c", "--count", type=int, default=1000)


def main():
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "status": cmd_status,
        "price": cmd_price,
        "ticks": cmd_ticks,
        "generate": cmd_generate,
        "start": cmd_start,
        "stop": cmd_stop,
        "reset": cmd_reset,
        "buy": cmd_buy,
        "sell": cmd_sell,
        "speed": cmd_speed,
        "traders": cmd_traders,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
