# coinglass_tester.py

import asyncio
from data_sources.coinglass_fetcher import _fetch

# List endpoint yang akan diuji
ENDPOINTS_TO_TEST = [
    ("/futures/fundingRate/latest", {"symbol": "BTC", "exchange": "Binance"}),
    ("/futures/openInterest/ohlc-aggregated-history", {"symbol": "BTC", "exchange": "Binance", "interval": "1h", "limit": 3}),
    ("/futures/global-long-short-account-ratio/history", {"symbol": "BTC", "exchange": "Binance", "interval": "1h", "limit": 3}),
    ("/futures/taker-buy-sell-volume/history", {"symbol": "BTC", "exchange": "Binance", "interval": "1h", "limit": 3}),
    ("/futures/orderbook/ask-bids-history", {"symbol": "BTC", "exchange": "Binance"}),
    ("/futures/liquidation/history", {"symbol": "BTC", "exchange": "Binance", "interval": "1h", "limit": 3}),
    ("/futures/fundingRate/ohlc-history", {"symbol": "BTC", "exchange": "Binance", "interval": "1h", "limit": 3}),  # Expected to fail
    ("/futures/openInterest/ohlc-history", {"symbol": "BTC", "exchange": "Binance", "interval": "1h", "limit": 3}),  # Expected to fail
]

async def test_endpoints():
    print("🚀 Testing CoinGlass Endpoints...\n")
    for path, params in ENDPOINTS_TO_TEST:
        print(f"🔍 Testing: {path}")
        try:
            data = await _fetch(path, params)
            status = "✅ OK" if data else "⚠️ Empty or Error"
            print(f"   → {status} | Result: {str(data)[:100]}\n")
        except Exception as e:
            print(f"   ❌ ERROR: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
