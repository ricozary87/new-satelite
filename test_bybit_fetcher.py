# test_bybit_fetcher.py
from data_sources.bybit_candle_fetcher import fetch_bybit_candles
from pprint import pprint

data = fetch_bybit_candles("SOLUSDT", "15", 3)
pprint(data)
