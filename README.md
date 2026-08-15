# crypto-market-adaptor

# crypto-market-adaptor

After learning that different crypto exchanges showcase different prices for the same asset, I was curious if I could create a simple adaptor + monitor to pull in live bid/ask data from multiple exchanges (Coinbase, Binance, Kraken) and combine it into a single composite feed in a terminal. I tried 2 methods:

1. adaptor.py
Polls each exchange's REST API once per second, fetching all three in parallel via a thread pool

2. continuous.py
Streams prices via WebSocket connections to each exchange, each running in its own background thread and updating a shared in-memory price table.

Both scripts compute a composite bid/ask/mid across the three sources and colour code the display (best price highlighted, mid price colored green/red based on direction)


Requirements:
1. Python
2. coinbase-advanced-py, websocket-client, requests, numpy
3. Coinbase API key (key.pem) and key name in config.py (KEY_NAME)

Next steps:
1. Input validation: Need to check that the constructed symbol is actually valid for a given exchange/base/quote pair 
2. Latency: WebSocket should be faster than the once-per-second REST API method, but it would be worthwhile to actually measure this and compare the two methods
3. More sources: Add Robinhood, etc, to widen the composite price
