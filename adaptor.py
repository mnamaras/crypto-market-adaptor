import time
import curses
import requests
import numpy as np
from datetime import datetime
from config import KEY_NAME
from concurrent.futures import ThreadPoolExecutor, as_completed
from coinbase.rest import RESTClient

BASE = "ETH"
CURR = "USD"

# -------------------- COINBASE  --------------------
KEY_FILE = "key.pem"
COINBASE_PRODUCT = f"{BASE}-{CURR}"

def load_key():
    with open(KEY_FILE, "r") as f:
        return f.read()

def c_fetch_bid_ask(client):
    response = client.get_best_bid_ask(product_ids=[COINBASE_PRODUCT])
    entry = response["pricebooks"][0]
    bid = float(entry["bids"][0]["price"])
    ask = float(entry["asks"][0]["price"])
    mid = (bid + ask) / 2
    return bid, ask, mid

# -------------------- KRAKEN  --------------------
KRAKEN_PRODUCT = f"X{BASE}Z{CURR}"
K_URL = "https://api.kraken.com/0/public/Ticker"

def k_fetch_bid_ask():
    response = requests.get(K_URL, params={"pair": KRAKEN_PRODUCT}, timeout=5)
    response.raise_for_status()
    data = response.json()
    ticker = data["result"][KRAKEN_PRODUCT]
    bid = float(ticker["b"][0])
    ask = float(ticker["a"][0])
    mid = (bid + ask) / 2
    return bid, ask, mid

# -------------------- BINANCE  --------------------
BINANCE_PRODUCT = f"{BASE}{CURR}T"
B_URL = "https://api.binance.com/api/v3/ticker/bookTicker"

def b_fetch_bid_ask():
    response = requests.get(B_URL, params={"symbol": BINANCE_PRODUCT}, timeout=5)
    response.raise_for_status()
    data = response.json()
    bid = float(data["bidPrice"])
    ask = float(data["askPrice"])
    mid = (bid + ask) / 2
    return bid, ask, mid

# -------------------- DISPLAY  --------------------
def main(stdscr):
    api_secret = load_key()
    client = RESTClient(api_key=KEY_NAME, api_secret=api_secret)

    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)   # normal
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)     # down
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)    # best bid/ask
    curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)   # up

    stdscr.addstr(1, 1, f"Polling {BASE}-{CURR} bid/ask every 1 second. Ctrl+C to stop.")
    stdscr.addstr(4, 1, f" {'Source':<12} {'Bid':>14} {'Ask':>16} {'Mid':>16} {'Spread':>11}")
    stdscr.addstr(5, 1, "=" * 75)

    prev_comp_mid = None
    executor = ThreadPoolExecutor(max_workers=3)

    while True:
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            stdscr.addstr(2, 1, f"Time: {timestamp}")

            # fetch all three in parallel
            f_coinbase = executor.submit(c_fetch_bid_ask, client)
            f_kraken   = executor.submit(k_fetch_bid_ask)
            f_binance  = executor.submit(b_fetch_bid_ask)

            c_bid, c_ask, c_mid = f_coinbase.result()
            k_bid, k_ask, k_mid = f_kraken.result()
            b_bid, b_ask, b_mid = f_binance.result()

            c_spread = c_ask - c_bid
            k_spread = k_ask - k_bid
            b_spread = b_ask - b_bid

            best_bid = max(c_bid, k_bid, b_bid)
            best_ask = min(c_ask, k_ask, b_ask)

            # COINBASE
            stdscr.addstr(6, 1,  f" {'COINBASE':<12}")
            stdscr.addstr(6, 14, f"${c_bid:>14,.3f}", curses.color_pair(3) if c_bid == best_bid else curses.color_pair(1))
            stdscr.addstr(6, 31, f"${c_ask:>14,.3f}", curses.color_pair(3) if c_ask == best_ask else curses.color_pair(1))
            stdscr.addstr(6, 48, f"${c_mid:>14,.3f} ${c_spread:>10,.3f}", curses.color_pair(1))

            # KRAKEN
            stdscr.addstr(7, 1,  f" {'KRAKEN':<12}")
            stdscr.addstr(7, 14, f"${k_bid:>14,.3f}", curses.color_pair(3) if k_bid == best_bid else curses.color_pair(1))
            stdscr.addstr(7, 31, f"${k_ask:>14,.3f}", curses.color_pair(3) if k_ask == best_ask else curses.color_pair(1))
            stdscr.addstr(7, 48, f"${k_mid:>14,.3f} ${k_spread:>10,.3f}", curses.color_pair(1))

            # BINANCE
            stdscr.addstr(8, 1,  f" {'BINANCE':<12}")
            stdscr.addstr(8, 14, f"${b_bid:>14,.3f}", curses.color_pair(3) if b_bid == best_bid else curses.color_pair(1))
            stdscr.addstr(8, 31, f"${b_ask:>14,.3f}", curses.color_pair(3) if b_ask == best_ask else curses.color_pair(1))
            stdscr.addstr(8, 48, f"${b_mid:>14,.3f} ${b_spread:>10,.3f}", curses.color_pair(1))

            # COMPOSITE
            comp_bid    = np.mean([c_bid, b_bid, k_bid])
            comp_ask    = np.mean([c_ask, b_ask, k_ask])
            comp_mid    = np.mean([c_mid, b_mid, k_mid])
            comp_spread = comp_ask - comp_bid

            if prev_comp_mid is None:
                comp_color = curses.color_pair(1)
            elif comp_mid > prev_comp_mid:
                comp_color = curses.color_pair(4)
            elif comp_mid < prev_comp_mid:
                comp_color = curses.color_pair(2)
            else:
                comp_color = curses.color_pair(1)

            stdscr.addstr(10, 1,  f" {'COMPOSITE':<12}")
            stdscr.addstr(10, 14, f"${comp_bid:>14,.3f}", curses.color_pair(1))
            stdscr.addstr(10, 31, f"${comp_ask:>14,.3f}", curses.color_pair(1))
            stdscr.addstr(10, 48, f"${comp_mid:>14,.3f}", comp_color)
            stdscr.addstr(10, 64, f"${comp_spread:>10,.3f}", curses.color_pair(1))

            prev_comp_mid = comp_mid

        except Exception as e:
            stdscr.addstr(11, 1, f"Error: {str(e)[:60]}")

        stdscr.refresh()
        time.sleep(1)

if __name__ == "__main__":
    curses.wrapper(main)