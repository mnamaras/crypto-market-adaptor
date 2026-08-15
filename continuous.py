import time
import curses
import json
import threading
import numpy as np
from datetime import datetime
from config import KEY_NAME
from coinbase.websocket import WSClient
import websocket

BASE = "ETH"
CURR = "USD"
KEY_FILE = "key.pem"

lock = threading.Lock()
prices = {
    "coinbase": {"bid": None, "ask": None, "mid": None},
    "kraken":   {"bid": None, "ask": None, "mid": None},
    "binance":  {"bid": None, "ask": None, "mid": None},
}

def set_price(exchange, bid, ask):
    with lock:
        prices[exchange] = {"bid": bid, "ask": ask, "mid": (bid + ask) / 2}

def get_prices():
    with lock:
        return {k: dict(v) for k, v in prices.items()}

# -------------------- COINBASE --------------------
COINBASE_PRODUCT = f"{BASE}-{CURR}"

def load_key():
    with open(KEY_FILE, "r") as f:
        return f.read()

def on_coinbase_message(msg):
    try:
        data = json.loads(msg)
        if data.get("channel") != "ticker":
            return
        events = data.get("events", [])
        if not events:
            return
        tickers = events[0].get("tickers", [])
        if not tickers:
            return
        ticker = tickers[0]
        bid = float(ticker["best_bid"])
        ask = float(ticker["best_ask"])
        set_price("coinbase", bid, ask)
    except Exception:
        pass

def start_coinbase():
    api_secret = load_key()
    client = WSClient(api_key=KEY_NAME, api_secret=api_secret, on_message=on_coinbase_message)
    client.open()
    client.subscribe(product_ids=[COINBASE_PRODUCT], channels=["ticker"])
    client.run_forever_with_exception_check()

# ─-------------------- KRAKEN --------------------
KRAKEN_WS_URL = "wss://ws.kraken.com/v2"
KRAKEN_PRODUCT = f"{BASE}/{CURR}"

def on_kraken_message(ws, msg):
    try:
        data = json.loads(msg)
        if data.get("channel") != "ticker":
            return
        if data.get("type") not in ("snapshot", "update"):
            return
        ticker = data["data"][0]
        bid = float(ticker["bid"])
        ask = float(ticker["ask"])
        set_price("kraken", bid, ask)
    except Exception:
        pass

def on_kraken_open(ws):
    sub = {
        "method": "subscribe",
        "params": {
            "channel": "ticker",
            "symbol": [KRAKEN_PRODUCT],
        }
    }
    ws.send(json.dumps(sub))

def start_kraken():
    while True:
        try:
            ws = websocket.WebSocketApp(
                KRAKEN_WS_URL,
                on_open=on_kraken_open,
                on_message=on_kraken_message,
            )
            ws.run_forever()
        except Exception:
            pass
        time.sleep(2)

# -------------------- BINANCE --------------------
BINANCE_PRODUCT = f"{BASE}{CURR}T".lower()
BINANCE_WS_URL = f"wss://stream.binance.com:9443/ws/{BINANCE_PRODUCT}@bookTicker"

def on_binance_message(ws, msg):
    try:
        data = json.loads(msg)
        bid = float(data["b"])
        ask = float(data["a"])
        set_price("binance", bid, ask)
    except Exception:
        pass

def start_binance():
    while True:
        try:
            ws = websocket.WebSocketApp(
                BINANCE_WS_URL,
                on_message=on_binance_message,
            )
            ws.run_forever()
        except Exception:
            pass
        time.sleep(2)

# -------------------- DISPLAY --------------------
def main(stdscr):
    for fn in (start_coinbase, start_kraken, start_binance):
        t = threading.Thread(target=fn, daemon=True)
        t.start()

    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED,   curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_CYAN,  curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)

    stdscr.addstr(1, 1, f"Streaming {BASE}-{CURR} via WebSocket. Ctrl+C to stop.")
    stdscr.addstr(4, 1, f" {'Source':<12} {'Bid':>14} {'Ask':>16} {'Mid':>16} {'Spread':>11}")
    stdscr.addstr(5, 1, "=" * 75)

    prev_comp_mid = None

    while True:
        timestamp = datetime.now().strftime("%H:%M:%S")
        stdscr.addstr(2, 1, f"Time: {timestamp}")

        p = get_prices()
        c = p["coinbase"]
        k = p["kraken"]
        b = p["binance"]

        bids = [r["bid"] for r in p.values() if r["bid"] is not None]
        asks = [r["ask"] for r in p.values() if r["ask"] is not None]
        best_bid = max(bids) if bids else None
        best_ask = min(asks) if asks else None

        for line in (6, 7, 8, 10):
            stdscr.move(line, 1)
            stdscr.clrtoeol()

        # COINBASE
        c_spread = c["ask"] - c["bid"] if c["bid"] else None
        stdscr.addstr(6, 1,  f" {'COINBASE':<12}")
        stdscr.addstr(6, 14, f"${c['bid']:>14,.3f}" if c["bid"] else f" {'waiting...':>14}", curses.color_pair(3) if c["bid"] == best_bid else curses.color_pair(1))
        stdscr.addstr(6, 31, f"${c['ask']:>14,.3f}" if c["ask"] else "", curses.color_pair(3) if c["ask"] == best_ask else curses.color_pair(1))
        stdscr.addstr(6, 48, f"${c['mid']:>14,.3f} ${c_spread:>10,.3f}" if c["mid"] else "", curses.color_pair(1))

        # KRAKEN
        k_spread = k["ask"] - k["bid"] if k["bid"] else None
        stdscr.addstr(7, 1,  f" {'KRAKEN':<12}")
        stdscr.addstr(7, 14, f"${k['bid']:>14,.3f}" if k["bid"] else f" {'waiting...':>14}", curses.color_pair(3) if k["bid"] == best_bid else curses.color_pair(1))
        stdscr.addstr(7, 31, f"${k['ask']:>14,.3f}" if k["ask"] else "", curses.color_pair(3) if k["ask"] == best_ask else curses.color_pair(1))
        stdscr.addstr(7, 48, f"${k['mid']:>14,.3f} ${k_spread:>10,.3f}" if k["mid"] else "", curses.color_pair(1))

        # BINANCE
        b_spread = b["ask"] - b["bid"] if b["bid"] else None
        stdscr.addstr(8, 1,  f" {'BINANCE':<12}")
        stdscr.addstr(8, 14, f"${b['bid']:>14,.3f}" if b["bid"] else f" {'waiting...':>14}", curses.color_pair(3) if b["bid"] == best_bid else curses.color_pair(1))
        stdscr.addstr(8, 31, f"${b['ask']:>14,.3f}" if b["ask"] else "", curses.color_pair(3) if b["ask"] == best_ask else curses.color_pair(1))
        stdscr.addstr(8, 48, f"${b['mid']:>14,.3f} ${b_spread:>10,.3f}" if b["mid"] else "", curses.color_pair(1))

        # COMPOSITE
        all_vals = [r for r in p.values() if r["bid"] is not None]
        if len(all_vals) == 3:
            comp_bid    = np.mean([c["bid"], k["bid"], b["bid"]])
            comp_ask    = np.mean([c["ask"], k["ask"], b["ask"]])
            comp_mid    = np.mean([c["mid"], k["mid"], b["mid"]])
            comp_spread = comp_ask - comp_bid

            if prev_comp_mid is None:       comp_color = curses.color_pair(1)
            elif comp_mid > prev_comp_mid:  comp_color = curses.color_pair(4)
            elif comp_mid < prev_comp_mid:  comp_color = curses.color_pair(2)
            else:                           comp_color = curses.color_pair(1)

            stdscr.addstr(10, 1,  f" {'COMPOSITE':<12}")
            stdscr.addstr(10, 14, f"${comp_bid:>14,.3f}", curses.color_pair(1))
            stdscr.addstr(10, 31, f"${comp_ask:>14,.3f}", curses.color_pair(1))
            stdscr.addstr(10, 48, f"${comp_mid:>14,.3f}", comp_color)
            stdscr.addstr(10, 64, f"${comp_spread:>10,.3f}", curses.color_pair(1))
            prev_comp_mid = comp_mid
        else:
            stdscr.addstr(10, 1, f" {'COMPOSITE':<12} waiting ({len(all_vals)}/3)...", curses.color_pair(1))

        stdscr.refresh()
        time.sleep(0.1)

if __name__ == "__main__":
    curses.wrapper(main)