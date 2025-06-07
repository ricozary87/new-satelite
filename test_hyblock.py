from data_sources.hyblock_fetcher import get_hyblock_data

response = get_hyblock_data(
    endpoint="/bidAsk",
    query={
        "coin": "BTC",
        "timeframe": "1m",
        "exchange": "Binance",
        "limit": 5
    }
)

print(response)
