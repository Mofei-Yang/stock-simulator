def cmd_generate(args):
    """Generate N ticks instantly (no sleep needed)."""
    count = args.count
    price = args.price

    import time
    import threading
    import urllib.parse

    done = threading.Event()
    last_printed = 0

    def poll_progress():
        nonlocal last_printed
        while not done.is_set():
            try:
                url = f"{BASE_URL}/api/generate/progress"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    prog = json.loads(resp.read())
                current = prog.get("current", 0)
                target = prog.get("target", 0)
                if current > 0 and (current - last_printed) >= 1000:
                    last_printed = current
                    pct = (current / target * 100) if target else 0
                    print(f"\r  {current:,} / {target:,} ticks ({pct:.0f}%)", end="", flush=True)
            except Exception:
                pass
            done.wait(0.5)

    def do_export():
        url = f"{BASE_URL}/api/generate/csv?count={count}&initial_price={price}"
        req = urllib.request.Request(url, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.read().decode()

    t0 = time.time()
    poller = threading.Thread(target=poll_progress, daemon=True)
    poller.start()

    try:
        if args.export:
            csv_data = do_export()
            elapsed = time.time() - t0
            ticks_generated = csv_data.count("\n") - 1
            rate = ticks_generated / max(elapsed, 0.001)
            print(f"\r  {ticks_generated:,} / {count:,} ticks (100%)")
            with open(args.export, "w") as f:
                f.write(csv_data)
            print(f"  Time: {elapsed:.1f}s  ({rate:,.0f} ticks/sec)")
            print(f"  Saved to {args.export}")
        else:
            data = _post("/api/generate", {"count": count, "initial_price": price})
            elapsed = time.time() - t0
            rate = data['count'] / max(elapsed, 0.001)
            print(f"\r  {data['count']:,} / {count:,} ticks (100%)")
            print(f"  Final price: {data['final_price']:.4f}")
            print(f"  Time: {elapsed:.1f}s  ({rate:,.0f} ticks/sec)")
    finally:
        done.set()
        poller.join(timeout=2)
